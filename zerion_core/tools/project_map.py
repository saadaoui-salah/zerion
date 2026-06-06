from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zerion_core.config import settings

SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    "chroma", ".pytest_cache", ".mypy_cache", "egg-info", ".agent_bus",
    ".memory", ".cursor", ".idea",
})

SKIP_EXT = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".avi", ".mov",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".min.js", ".min.css",
    ".lock",
})

MAX_DEPTH = 8
MAX_FILES = 400

TECH_PATTERNS: list[tuple[str, str, list[str]]] = [
    ("python", "Python", ["*.py"]),
    ("javascript", "JavaScript", ["*.js", "*.mjs"]),
    ("typescript", "TypeScript", ["*.ts", "*.tsx"]),
    ("jsx", "React JSX", ["*.jsx"]),
]

FRAMEWORK_DETECTORS: list[tuple[str, str, list[str], list[str]]] = [
    ("django", "django", ["manage.py"], []),
    ("fastapi", "fastapi", [], []),
    ("flask", "flask", [], []),
    ("react", "react", [], ["react-dom"]),
    ("nextjs", "next", ["next.config.js", "next.config.mjs"], []),
    ("express", "express", [], []),
    ("vue", "vue", [], []),
    ("angular", "@angular/core", [], []),
]


def detect_technologies(root: Path) -> list[str]:
    """Detect frameworks and packages from project config files."""
    techs: list[str] = []
    seen: set[str] = set()

    # Check package config files
    config_files = {
        "pyproject.toml": lambda c: _parse_pyproject_toml(c),
        "requirements.txt": lambda c: list(c.read_text(encoding="utf-8", errors="ignore").splitlines()),
        "package.json": lambda c: list(c.read_text(encoding="utf-8", errors="ignore")),
        "Cargo.toml": lambda c: [],
        "Gemfile": lambda c: [],
        "go.mod": lambda c: [],
    }

    deps: list[str] = []
    for fname, handler in config_files.items():
        path = root / fname
        if path.exists():
            pkgs = handler(path)
            if isinstance(pkgs, list):
                deps.extend(pkgs)
            elif isinstance(pkgs, str):
                try:
                    pkg = json.loads(pkgs)
                    deps.extend(list(pkg.get("dependencies", {}).keys()))
                    deps.extend(list(pkg.get("devDependencies", {}).keys()))
                except json.JSONDecodeError:
                    pass

    # Match deps against framework detectors
    for dep in deps:
        dep_lower = dep.lower()
        for name, dep_name, file_markers, extra_deps in FRAMEWORK_DETECTORS:
            if name not in seen:
                if dep_name and dep_name in dep_lower:
                    techs.append(name)
                    seen.add(name)
                    continue
                for ed in extra_deps:
                    if ed and ed in dep_lower:
                        techs.append(name)
                        seen.add(name)
                        break

    # Check for framework marker files (for frameworks missed by dep scan)
    for name, dep_name, file_markers, extra_deps in FRAMEWORK_DETECTORS:
        if name not in seen:
            for marker in file_markers:
                if (root / marker).exists():
                    techs.append(name)
                    seen.add(name)
                    break

    if (root / "vite.config.ts").exists() or (root / "vite.config.js").exists():
        techs.append("vite")
        seen.add("vite")

    # Always detect base language
    for ext, lang in (
        ("*.py", "python"),
        ("*.js", "javascript"),
        ("*.mjs", "javascript"),
        ("*.ts", "typescript"),
        ("*.tsx", "typescript"),
    ):
        if lang not in seen and list(root.rglob(ext)):
            techs.append(lang)
            seen.add(lang)

    return sorted(set(techs))


def _parse_pyproject_toml(path: Path) -> list[str]:
    """Extract dependency names from pyproject.toml (no TOML parser dependency)."""
    deps: list[str] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        in_deps = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("[tool.poetry.dependencies]") or stripped.startswith("[project.dependencies]") or stripped.startswith("[project.optional-dependencies]"):
                in_deps = True
                continue
            if stripped.startswith("[") and in_deps:
                in_deps = False
            if in_deps and "=" in stripped and not stripped.startswith("python"):
                name = stripped.split("=")[0].strip().strip('"').strip("'")
                if name:
                    deps.append(name)
    except Exception:
        pass
    return deps


def _parse_python_file(path: Path) -> dict[str, Any]:
    """Extract classes, methods, functions, and imports from a Python file using AST."""
    result: dict[str, Any] = {"classes": [], "functions": [], "imports": []}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, ast.ClassDef):
            cls: dict[str, Any] = {
                "name": node.name,
                "line_number": node.lineno,
                "docstring": ast.get_docstring(node) or "",
                "methods": [],
            }
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cls["methods"].append({
                        "name": item.name,
                        "line_number": item.lineno,
                        "docstring": ast.get_docstring(item) or "",
                        "params": [arg.arg for arg in item.args.args if arg.arg != "self"],
                    })
            result["classes"].append(cls)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Top-level function
            result["functions"].append({
                "name": node.name,
                "line_number": node.lineno,
                "docstring": ast.get_docstring(node) or "",
                "params": [arg.arg for arg in node.args.args],
            })

    return result


def _parse_js_ts_file(path: Path) -> dict[str, Any]:
    """Extract classes and functions from JS/TS files using regex."""
    result: dict[str, Any] = {"classes": [], "functions": [], "imports": []}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return result

    lines = text.splitlines()

    # Extract imports
    for m in re.finditer(
        r'(?:import\s+.+?\s+from\s+[\'"](.+?)[\'"]|require\([\'"](.+?)[\'"]\))',
        text,
        re.MULTILINE,
    ):
        result["imports"].append(m.group(1) or m.group(2))

    # Extract classes
    cls_pattern = re.compile(r'(?:export\s+)?(?:default\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{')
    for m in cls_pattern.finditer(text):
        cls = {
            "name": m.group(1),
            "line_number": text[:m.start()].count("\n") + 1,
            "docstring": "",
            "methods": [],
        }
        # Find methods inside this class
        cls_start = m.end()
        brace_depth = 1
        cls_end = cls_start
        for j in range(cls_start, len(text)):
            if text[j] == "{":
                brace_depth += 1
            elif text[j] == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    cls_end = j
                    break
        cls_body = text[cls_start:cls_end]
        for fm in re.finditer(
            r'(?:async\s+)?(?:static\s+)?(?:get\s+)?(?:set\s+)?(\w+)\s*\(([^)]*)\)\s*\{',
            cls_body,
        ):
            cls["methods"].append({
                "name": fm.group(1),
                "line_number": text[:cls_start + fm.start()].count("\n") + 1,
                "docstring": "",
                "params": [p.strip() for p in fm.group(2).split(",") if p.strip()],
            })
        result["classes"].append(cls)

    # Extract top-level arrow/anonymous functions
    func_pattern = re.compile(
        r'(?:export\s+)?(?:async\s+)?(?:function\s+)?(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*\w+)?\s*=>|'
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
    )
    seen_funcs: set[str] = set()
    for m in func_pattern.finditer(text):
        name = m.group(1) or m.group(3)
        if name and name not in seen_funcs and name != "function":
            seen_funcs.add(name)
            result["functions"].append({
                "name": name,
                "line_number": text[:m.start()].count("\n") + 1,
                "docstring": "",
                "params": [p.strip() for p in (m.group(2) or m.group(4) or "").split(",") if p.strip()],
            })

    return result


def _generate_description(root: Path, techs: list[str], file_count: int) -> str:
    """Build a short project description from available metadata."""
    readme_paths = [root / "README.md", root / "Readme.md", root / "readme.md"]
    for rp in readme_paths:
        if rp.exists():
            text = rp.read_text(encoding="utf-8", errors="ignore")[:500]
            first_line = text.splitlines()[0] if text.splitlines() else ""
            if first_line and len(first_line) < 200:
                return first_line.strip().lstrip("#").strip()

    if techs:
        return f"A {', '.join(techs[:3])} project with {file_count} files."
    return f"A software project with {file_count} files."


def deep_scan_project(root: Path | None = None) -> dict[str, Any]:
    """Deep scan: detect tech + extract classes/methods from every source file."""
    workspace = (root or settings.workspace).resolve()
    techs = detect_technologies(workspace)
    file_infos: list[dict[str, Any]] = []
    total_files = 0

    EXT_PARSERS = {
        ".py": _parse_python_file,
        ".js": _parse_js_ts_file,
        ".mjs": _parse_js_ts_file,
        ".jsx": _parse_js_ts_file,
        ".ts": _parse_js_ts_file,
        ".tsx": _parse_js_ts_file,
    }

    for ext, parser in EXT_PARSERS.items():
        for fpath in sorted(workspace.rglob(f"*{ext}")):
            if any(skip in fpath.parts for skip in SKIP_DIRS):
                continue
            if fpath.name.startswith("."):
                continue
            if total_files >= MAX_FILES:
                break

            rel = fpath.relative_to(workspace).as_posix()
            parsed = parser(fpath)
            total_files += 1

            file_infos.append({
                "path": rel,
                "type": ext.lstrip("."),
                "size": fpath.stat().st_size,
                "classes": parsed.get("classes", []),
                "functions": parsed.get("functions", []),
                "imports": parsed.get("imports", []),
            })

        if total_files >= MAX_FILES:
            break

    # Limit nested elements to keep the snapshot manageable
    for fi in file_infos:
        fi["classes"] = fi["classes"][:10]
        for cls in fi["classes"]:
            cls["methods"] = cls["methods"][:15]
        fi["functions"] = fi["functions"][:15]
        fi["imports"] = fi["imports"][:20]

    description = _generate_description(workspace, techs, total_files)

    return {
        "project_path": str(workspace),
        "technologies": techs,
        "description": description,
        "files": file_infos,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def format_rich_snapshot(snapshot: dict[str, Any] | None = None) -> str:
    """Format a deep project snapshot into a readable text block for LLM context."""
    snap = snapshot or deep_scan_project()
    lines: list[str] = [
        "## PROJECT DEEP STRUCTURE",
        f"Path: {snap['project_path']}",
        f"Technologies: {', '.join(snap['technologies']) or 'unknown'}",
        f"Description: {snap['description']}",
        "",
    ]

    for fi in snap.get("files", []):
        lines.append(f"  📄 {fi['path']} ({fi['type']}, {fi['size']}b)")
        for cls in fi.get("classes", []):
            lines.append(f"    🏛  {cls['name']} (line {cls['line_number']})")
            if cls.get("docstring"):
                lines.append(f"       {cls['docstring'][:120]}")
            for m in cls.get("methods", []):
                params = ", ".join(m.get("params", []))
                lines.append(f"       └─ {m['name']}({params}) line {m['line_number']}")
        for fn in fi.get("functions", []):
            params = ", ".join(fn.get("params", []))
            lines.append(f"    └─ def {fn['name']}({params}) line {fn['line_number']}")
        if fi.get("imports"):
            for imp in fi["imports"][:5]:
                lines.append(f"       ↳ import {imp}")

    if not snap.get("files"):
        lines.append("  (no source files scanned)")

    lines.append(f"\nScanned at: {snap['indexed_at']}")
    return "\n".join(lines)


def is_windows() -> bool:
    return sys.platform == "win32"


def scan_workspace(root: Path | None = None, max_depth: int = MAX_DEPTH) -> dict:
    """Build a live snapshot of the workspace file structure."""
    workspace = (root or settings.workspace).resolve()
    files: list[str] = []
    dirs: list[str] = []
    tree_lines: list[str] = []

    def walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        visible = [
            e for e in entries
            if not (e.name.startswith(".") and e.name not in (".env.example",))
            and not (e.is_dir() and e.name in SKIP_DIRS)
        ][:80]

        for i, entry in enumerate(visible):
            is_last = i == len(visible) - 1
            branch = "└── " if is_last else "├── "
            rel = entry.relative_to(workspace).as_posix()

            if entry.is_dir():
                dirs.append(rel)
                tree_lines.append(f"{prefix}{branch}{entry.name}/")
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension, depth + 1)
            else:
                files.append(rel)
                tree_lines.append(f"{prefix}{branch}{entry.name}")

    walk(workspace, "", 0)

    return {
        "root": str(workspace),
        "platform": "windows" if is_windows() else "posix",
        "shell_hint": "Use backslashes on Windows; prefer file writes over mkdir",
        "file_count": len(files),
        "dir_count": len(dirs),
        "files": files[:MAX_FILES],
        "dirs": dirs[:200],
        "tree": "\n".join(tree_lines[:300]) or "(empty workspace)",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


def format_project_context(snapshot: dict | None = None) -> str:
    snap = snapshot or scan_workspace()
    lines = [
        "## PROJECT STRUCTURE (live snapshot)",
        f"Root: {snap['root']}",
        f"Platform: {snap['platform']} — {snap.get('shell_hint', '')}",
        f"Dirs ({snap['dir_count']}): {', '.join(snap['dirs'][:40]) or 'none'}",
        "",
        "Tree:",
        snap.get("tree", ""),
    ]
    if snap.get("file_count", 0) > 40:
        lines.append(f"\n… and {snap['file_count'] - 40} more files")
    return "\n".join(lines)


def ensure_dir(rel_path: str, root: Path | None = None) -> tuple[bool, str]:
    workspace = (root or settings.workspace).resolve()
    target = (workspace / rel_path).resolve()
    if not str(target).startswith(str(workspace)):
        return False, f"Blocked path: {rel_path}"
    if target.is_dir():
        return True, f"skip mkdir (exists): {rel_path}"
    target.mkdir(parents=True, exist_ok=True)
    return True, f"mkdir: {rel_path}"


def remove_dir(rel_path: str, root: Path | None = None) -> tuple[bool, str]:
    import shutil

    workspace = (root or settings.workspace).resolve()
    target = (workspace / rel_path).resolve()
    if not str(target).startswith(str(workspace)):
        return False, f"Blocked path: {rel_path}"
    if not target.exists():
        return True, f"skip rmdir (not found): {rel_path}"
    if not target.is_dir():
        return False, f"not a directory: {rel_path}"
    shutil.rmtree(target)
    return True, f"removed: {rel_path}"


def save_snapshot(snapshot: dict, root: Path | None = None) -> Path:
    path = settings.memory_root / "project_structure.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return path
