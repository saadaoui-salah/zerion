from __future__ import annotations

import ast
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from zerion_core.config import settings
from zerion_core.tools.project_map import SKIP_DIRS, SKIP_EXT


CHUNK_MAX_LINES = 80
CHUNK_OVERLAP = 10
MAX_CHUNK_SIZE = 4000


@dataclass
class CodeChunk:
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # "file", "class", "function", "method", "import_group", "section"
    symbol_name: str = ""
    parent_class: str = ""
    docstring: str = ""
    language: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_type": self.chunk_type,
            "symbol_name": self.symbol_name,
            "parent_class": self.parent_class,
            "docstring": self.docstring,
            "language": self.language,
            "metadata": self.metadata,
        }


class CodeIndexer:
    """AST-based code indexer that chunks source files into searchable units."""

    EXT_LANGUAGE = {
        ".py": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".php": "php",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c_header",
        ".cs": "csharp",
    }

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.workspace).resolve()
        self.index_path = settings.memory_root / "rag_index.json"
        self._manifest: dict[str, dict[str, Any]] = {}

    def _load_manifest(self) -> None:
        if self.index_path.exists():
            try:
                self._manifest = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._manifest = {}

    def _save_manifest(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(self._manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _chunk_id(self, file_path: str, chunk_type: str, symbol: str, start: int) -> str:
        raw = f"{file_path}:{chunk_type}:{symbol}:{start}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def _file_hash(self, path: Path) -> str:
        try:
            stat = path.stat()
            return f"{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            return ""

    def _is_source_file(self, path: Path) -> bool:
        if path.suffix not in self.EXT_LANGUAGE:
            return False
        if any(skip in path.parts for skip in SKIP_DIRS):
            return False
        if path.name.startswith("."):
            return False
        return True

    def index_file(self, path: Path) -> list[CodeChunk]:
        """Index a single source file into chunks."""
        rel = path.relative_to(self.root).as_posix()
        file_hash = self._file_hash(path)
        if not file_hash:
            return []

        # Skip if unchanged
        cached = self._manifest.get(rel, {})
        if cached.get("hash") == file_hash and cached.get("chunks"):
            return []

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        language = self.EXT_LANGUAGE.get(path.suffix, "unknown")
        chunks = self._chunk_file(rel, content, language)
        self._manifest[rel] = {
            "hash": file_hash,
            "chunks": len(chunks),
            "indexed_at": time.time(),
        }
        return chunks

    def index_full(self, on_progress: Any = None) -> list[CodeChunk]:
        """Index all source files in the workspace. Returns all chunks."""
        self._load_manifest()
        all_chunks: list[CodeChunk] = []
        files = self._discover_files()

        for i, fpath in enumerate(files):
            chunks = self.index_file(fpath)
            all_chunks.extend(chunks)
            if on_progress:
                on_progress(i + 1, len(files), fpath.relative_to(self.root).as_posix())

        self._save_manifest()
        return all_chunks

    def get_changed_files(self) -> list[Path]:
        """Return files that have changed since last index."""
        self._load_manifest()
        changed = []
        for fpath in self._discover_files():
            rel = fpath.relative_to(self.root).as_posix()
            file_hash = self._file_hash(fpath)
            cached = self._manifest.get(rel, {})
            if cached.get("hash") != file_hash:
                changed.append(fpath)
        return changed

    def _discover_files(self) -> list[Path]:
        files: list[Path] = []
        for fpath in sorted(self.root.rglob("*")):
            if self._is_source_file(fpath):
                files.append(fpath)
        return files

    def _chunk_file(self, file_path: str, content: str, language: str) -> list[CodeChunk]:
        """Chunk a file into semantic units using AST for Python, regex for others."""
        if language == "python":
            return self._chunk_python(file_path, content)
        return self._chunk_regex(file_path, content, language)

    def _chunk_python(self, file_path: str, content: str, language: str = "python") -> list[CodeChunk]:
        """AST-based Python chunking: file header, imports, each class/function as separate chunks."""
        lines = content.splitlines()
        chunks: list[CodeChunk] = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._chunk_by_lines(file_path, content, language)

        # Extract import block range
        import_start = None
        import_end = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if import_start is None:
                    import_start = node.lineno
                import_end = node.end_lineno or node.lineno

        # File header (docstring or comments before imports)
        header_end = (import_start - 1) if import_start else 0
        if header_end > 0:
            header = "\n".join(lines[:header_end])
            if header.strip():
                chunks.append(CodeChunk(
                    id=self._chunk_id(file_path, "header", "", 1),
                    file_path=file_path,
                    content=header,
                    start_line=1,
                    end_line=header_end,
                    chunk_type="file",
                    symbol_name="__header__",
                    language=language,
                ))

        # Import group
        if import_start and import_end:
            import_lines = lines[import_start - 1:import_end]
            import_text = "\n".join(import_lines)
            if import_text.strip():
                chunks.append(CodeChunk(
                    id=self._chunk_id(file_path, "import_group", "", import_start),
                    file_path=file_path,
                    content=import_text,
                    start_line=import_start,
                    end_line=import_end,
                    chunk_type="import_group",
                    symbol_name="__imports__",
                    language=language,
                ))

        # Each class and top-level function
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                chunks.extend(self._extract_class(file_path, lines, node, language))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunk = self._extract_function(file_path, lines, node, language)
                if chunk:
                    chunks.append(chunk)

        # If file has no AST-extracted chunks, fall back to line-based chunking
        if len(chunks) < 2:
            return self._chunk_by_lines(file_path, content, language)

        return chunks

    def _extract_class(self, file_path: str, lines: list[str], node: ast.ClassDef, language: str) -> list[CodeChunk]:
        chunks: list[CodeChunk] = []
        start = node.lineno
        end = node.end_lineno or node.lineno
        docstring = ast.get_docstring(node) or ""

        # Class header + docstring (up to first method or 40 lines)
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if methods:
            class_body_end = min(methods[0].lineno - 1, start + 40)
        else:
            class_body_end = min(end, start + 40)

        class_header = "\n".join(lines[start - 1:class_body_end])
        chunks.append(CodeChunk(
            id=self._chunk_id(file_path, "class", node.name, start),
            file_path=file_path,
            content=class_header,
            start_line=start,
            end_line=class_body_end,
            chunk_type="class",
            symbol_name=node.name,
            docstring=docstring,
            language=language,
            metadata={"bases": [getattr(b, "id", getattr(b, "attr", "?")) for b in node.bases]},
        ))

        # Each method as separate chunk
        for method in methods:
            m_chunk = self._extract_function(file_path, lines, method, language, parent_class=node.name)
            if m_chunk:
                chunks.append(m_chunk)

        return chunks

    def _extract_function(
        self,
        file_path: str,
        lines: list[str],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        language: str,
        parent_class: str = "",
    ) -> CodeChunk | None:
        start = node.lineno
        end = node.end_lineno or node.lineno
        if start > len(lines):
            return None

        content = "\n".join(lines[start - 1:end])
        docstring = ast.get_docstring(node) or ""
        params = [arg.arg for arg in node.args.args if arg.arg != "self"]

        return CodeChunk(
            id=self._chunk_id(file_path, "function", f"{parent_class}.{node.name}" if parent_class else node.name, start),
            file_path=file_path,
            content=content,
            start_line=start,
            end_line=end,
            chunk_type="function" if not parent_class else "method",
            symbol_name=node.name,
            parent_class=parent_class,
            docstring=docstring,
            language=language,
            metadata={"params": params, "is_async": isinstance(node, ast.AsyncFunctionDef)},
        )

    def _chunk_regex(self, file_path: str, content: str, language: str) -> list[CodeChunk]:
        """Regex-based chunking for non-Python files: split on class/function boundaries."""
        lines = content.splitlines()
        patterns = [
            re.compile(r"^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)"),
            re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)"),
            re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\("),
            re.compile(r"^\s*(?:pub\s+)?(?:fn|func)\s+(\w+)"),
        ]

        boundaries: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            for pat in patterns:
                m = pat.match(line)
                if m:
                    boundaries.append((i, m.group(1)))
                    break

        if not boundaries:
            return self._chunk_by_lines(file_path, content, language)

        chunks: list[CodeChunk] = []
        for idx, (start_idx, name) in enumerate(boundaries):
            end_idx = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(lines)
            chunk_text = "\n".join(lines[start_idx:end_idx])
            if chunk_text.strip():
                chunk_type = "class" if "class" in lines[start_idx] else "function"
                chunks.append(CodeChunk(
                    id=self._chunk_id(file_path, chunk_type, name, start_idx + 1),
                    file_path=file_path,
                    content=chunk_text,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    chunk_type=chunk_type,
                    symbol_name=name,
                    language=language,
                ))

        # Add header chunk (before first boundary)
        if boundaries and boundaries[0][0] > 0:
            header = "\n".join(lines[:boundaries[0][0]])
            if header.strip():
                chunks.insert(0, CodeChunk(
                    id=self._chunk_id(file_path, "header", "", 1),
                    file_path=file_path,
                    content=header,
                    start_line=1,
                    end_line=boundaries[0][0],
                    chunk_type="file",
                    symbol_name="__header__",
                    language=language,
                ))

        return chunks

    def _chunk_by_lines(self, file_path: str, content: str, language: str) -> list[CodeChunk]:
        """Fallback: split into fixed-size line-based chunks."""
        lines = content.splitlines()
        chunks: list[CodeChunk] = []
        i = 0
        while i < len(lines):
            end = min(i + CHUNK_MAX_LINES, len(lines))
            chunk_text = "\n".join(lines[i:end])
            if chunk_text.strip():
                chunks.append(CodeChunk(
                    id=self._chunk_id(file_path, "section", "", i + 1),
                    file_path=file_path,
                    content=chunk_text,
                    start_line=i + 1,
                    end_line=end,
                    chunk_type="section",
                    symbol_name=f"lines_{i+1}_{end}",
                    language=language,
                ))
            i += CHUNK_MAX_LINES - CHUNK_OVERLAP
        return chunks
