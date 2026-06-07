from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from rich.text import Text

from zerion_core.config import settings


def _detect_language(path: str) -> str:
    """Detect language from file extension for Pygments."""
    ext = Path(path).suffix.lower()
    lang_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "shell",
        ".fish": "shell",
        ".ps1": "powershell",
        ".bat": "batch",
        ".cmd": "batch",
        ".xml": "xml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".conf": "ini",
        ".dockerfile": "dockerfile",
        ".makefile": "makefile",
        ".cmake": "cmake",
        ".vue": "vue",
        ".svelte": "svelte",
    }
    return lang_map.get(ext, "text")


def _highlight_code(code: str, language: str) -> list[tuple[str, str]]:
    """Highlight code and return list of (token, style) pairs.

    Falls back to plain text if Pygments not available.
    """
    try:
        from pygments import highlight
        from pygments.lexers import get_lexer_by_name, TextLexer
        from pygments.token import Token

        try:
            lexer = get_lexer_by_name(language)
        except Exception:
            lexer = TextLexer()

        # Token style map (Monokai-inspired for dark backgrounds)
        token_styles = {
            Token.Keyword: "bold #c678dd",
            Token.Keyword.Namespace: "bold #c678dd",
            Token.Keyword.Declaration: "bold #c678dd",
            Token.Keyword.Type: "bold #e5c07b",
            Token.Name.Function: "bold #61afef",
            Token.Name.Class: "bold #e5c07b",
            Token.Name.Decorator: "bold #d19a66",
            Token.Name.Builtin: "bold #56b6c2",
            Token.Name.Builtin.Pseudo: "bold #56b6c2",
            Token.Name.Constant: "bold #d19a66",
            Token.Name.Variable: "#e06c75",
            Token.Name.Attribute: "#d19a66",
            Token.Name.Tag: "bold #e06c75",
            Token.Name.Entity: "bold #e06c75",
            Token.String: "bold #98c379",
            Token.String.Affix: "bold #c678dd",
            Token.String.Backtick: "bold #98c379",
            Token.String.Char: "bold #98c379",
            Token.String.Double: "bold #98c379",
            Token.String.Single: "bold #98c379",
            Token.String.Regex: "bold #98c379",
            Token.Number: "bold #d19a66",
            Token.Number.Bin: "bold #d19a66",
            Token.Number.Float: "bold #d19a66",
            Token.Number.Hex: "bold #d19a66",
            Token.Number.Integer: "bold #d19a66",
            Token.Number.Oct: "bold #d19a66",
            Token.Operator: "#56b6c2",
            Token.Operator.Word: "bold #c678dd",
            Token.Punctuation: "#abb2bf",
            Token.Comment: "italic #5c6370",
            Token.Comment.Hashbang: "italic #5c6370",
            Token.Comment.Multiline: "italic #5c6370",
            Token.Generic.Heading: "bold #e5c07b",
            Token.Generic.Subheading: "bold #e5c07b",
            Token.Generic.Deleted: "#e06c75",
            Token.Generic.Inserted: "#98c379",
            Token.Generic.Error: "bold #f44747",
            Token.Generic.Output: "#abb2bf",
            Token.Generic.Prompt: "bold #61afef",
            Token.Generic.Emph: "italic",
            Token.Generic.Strong: "bold",
            Token.Generic.Traceback: "bold #f44747",
            Token.Error: "bold #f44747",
        }

        tokens = list(lexer.get_tokens(code))
        result = []
        for token_type, value in tokens:
            style = token_styles.get(token_type, "#abb2bf")
            result.append((value, style))
        return result

    except ImportError:
        # No Pygments - return plain text
        return [(code, "#abb2bf")]


def _render_highlighted_line(
    text_obj: Text,
    code: str,
    language: str,
    base_style: str = "",
) -> None:
    """Render a syntax-highlighted line into a Text object."""
    tokens = _highlight_code(code, language)
    for value, style in tokens:
        if base_style:
            # Combine base background with token foreground
            # Extract foreground color from token style
            fg = style.split()[-1] if style else "#abb2bf"
            combined = f"{fg} on {base_style}"
            text_obj.append(value, style=combined)
        else:
            text_obj.append(value, style=style)


def unified_diff(old: str | None, new: str, path: str) -> list[str]:
    old_lines = (old or "").splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if not old_lines and not old:
        old_lines = []
    return list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def diff_stats(old: str | None, new: str) -> tuple[int, int]:
    old_set = (old or "").splitlines()
    new_set = new.splitlines()
    diff = list(difflib.ndiff(old_set, new_set))
    added = sum(1 for d in diff if d.startswith("+ "))
    removed = sum(1 for d in diff if d.startswith("- "))
    return added, removed


def render_diff_lines(lines: list[str], path: str = "") -> Text:
    """Render unified diff with syntax-aware highlighting and background colors."""
    text = Text()
    language = _detect_language(path) if path else "text"

    for line in lines:
        if line.startswith("+++") or line.startswith("---"):
            text.append(line + "\n", style="bold white")
        elif line.startswith("@@"):
            text.append(line + "\n", style="bold cyan")
        elif line.startswith("+"):
            # Added line: green background with syntax highlighting
            code = line[1:]  # Remove the + prefix
            text.append("+ ", style="bold #3fb950 on #0d2818")
            _render_highlighted_line(text, code, language, base_style="#0d2818")
            text.append("\n")
        elif line.startswith("-"):
            # Removed line: red background with syntax highlighting
            code = line[1:]  # Remove the - prefix
            text.append("- ", style="bold #f85149 on #2d1117")
            _render_highlighted_line(text, code, language, base_style="#2d1117")
            text.append("\n")
        else:
            text.append(line + "\n", style="#8b949e")
    return text


def render_ndiff_preview(old: str | None, new: str, path: str, max_lines: int = 80) -> Text:
    """Compact +/- preview for new or edited files with syntax highlighting."""
    text = Text()
    language = _detect_language(path)
    text.append(f"📄 {path}\n", style="bold white")

    if old is None or old == "":
        # New file: show all lines with green background
        for i, line in enumerate(new.splitlines()[:max_lines]):
            text.append("+ ", style="bold #3fb950 on #0d2818")
            _render_highlighted_line(text, line, language, base_style="#0d2818")
            text.append("\n")
        if new.count("\n") > max_lines:
            text.append(f"  … {new.count(chr(10)) - max_lines} more lines\n", style="dim")
        return text

    lines = unified_diff(old, new, path)
    if not lines:
        text.append("  (no changes)\n", style="dim")
        return text
    for line in lines[:max_lines]:
        if line.startswith("+"):
            code = line[1:]
            text.append("+ ", style="bold #3fb950 on #0d2818")
            _render_highlighted_line(text, code, language, base_style="#0d2818")
            text.append("\n")
        elif line.startswith("-"):
            code = line[1:]
            text.append("- ", style="bold #f85149 on #2d1117")
            _render_highlighted_line(text, code, language, base_style="#2d1117")
            text.append("\n")
        elif line.startswith("@@"):
            text.append(line + "\n", style="cyan")
        elif not line.startswith(("---", "+++")):
            text.append("  " + line + "\n", style="#6e7681")
    return text


def render_side_by_side(old: str | None, new: str, path: str, context_lines: int = 3) -> Text:
    """Render a side-by-side diff with line numbers, syntax highlighting, and colored backgrounds."""
    old_lines = (old or "").splitlines()
    new_lines = new.splitlines()
    language = _detect_language(path)
    text = Text()

    text.append(f"← Edit {path}\n", style="bold #4fc1ff")

    # New file: show all lines as additions
    if old is None or old == "":
        gutter = max(3, len(str(len(new_lines))))
        for i, line in enumerate(new_lines):
            text.append(f" {'':>{gutter}} ", style="#6e7681")
            text.append(f" ", style="#6e7681")
            text.append(f" {i+1:>{gutter}} ", style="#6e7681")
            text.append(f"+", style="bold #3fb950")
            text.append(" ", style="bold #3fb950 on #0d2818")
            _render_highlighted_line(text, line, language, base_style="#0d2818")
            text.append("\n")
        text.append("\n")
        return text

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    opcodes = sm.get_opcodes()

    if not opcodes or (len(opcodes) == 1 and opcodes[0][0] == "equal"):
        text.append("\n", style="dim")
        return text

    # Build hunks: only regions around changes + context
    hunks: list[tuple[int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        start_i = max(0, i1 - context_lines)
        end_i = min(len(old_lines), i2 + context_lines)
        start_j = max(0, j1 - context_lines)
        end_j = min(len(new_lines), j2 + context_lines)
        hunks.append((start_i, end_i, start_j, end_j))

    if not hunks:
        text.append("\n", style="dim")
        return text

    # Merge overlapping hunks
    merged: list[list[int]] = []
    for h in hunks:
        if merged and h[0] <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], h[1])
            merged[-1][3] = max(merged[-1][3], h[3])
        else:
            merged.append(list(h))

    gutter = max(3, len(str(len(old_lines))))

    for h_start_i, h_end_i, h_start_j, h_end_j in merged:
        i = h_start_i
        j = h_start_j

        while i < h_end_i or j < h_end_j:
            # Find opcodes that overlap current position
            matched_op = None
            for tag, i1, i2, j1, j2 in opcodes:
                if tag == "equal":
                    continue
                if i1 <= i < i2 and j1 <= j < j2:
                    matched_op = (tag, i1, i2, j1, j2)
                    break

            if matched_op:
                tag, i1, i2, j1, j2 = matched_op
                # Render all lines in this change block
                while i < i2 and j < j2:
                    old_line = old_lines[i] if i < len(old_lines) else ""
                    new_line = new_lines[j] if j < len(new_lines) else ""

                    # Left side: removed line (red background)
                    text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                    text.append(f"-", style="bold #f85149")
                    text.append(" ", style="bold #f85149 on #2d1117")
                    _render_highlighted_line(text, old_line, language, base_style="#2d1117")
                    text.append("\n")
                    # Right side: added line (green background)
                    text.append(f" {j+1:>{gutter}} ", style="#6e7681")
                    text.append(f"+", style="bold #3fb950")
                    text.append(" ", style="bold #3fb950 on #0d2818")
                    _render_highlighted_line(text, new_line, language, base_style="#0d2818")
                    text.append("\n")
                    i += 1
                    j += 1

                # Handle unequal lengths (delete or insert)
                while i < i2:
                    old_line = old_lines[i] if i < len(old_lines) else ""
                    text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                    text.append(f"-", style="bold #f85149")
                    text.append(" ", style="bold #f85149 on #2d1117")
                    _render_highlighted_line(text, old_line, language, base_style="#2d1117")
                    text.append("\n")
                    text.append(f" {'':>{gutter}} ", style="#6e7681")
                    text.append(f" \n", style="#6e7681")
                    i += 1

                while j < j2:
                    new_line = new_lines[j] if j < len(new_lines) else ""
                    text.append(f" {'':>{gutter}} ", style="#6e7681")
                    text.append(f" \n", style="#6e7681")
                    text.append(f" {j+1:>{gutter}} ", style="#6e7681")
                    text.append(f"+", style="bold #3fb950")
                    text.append(" ", style="bold #3fb950 on #0d2818")
                    _render_highlighted_line(text, new_line, language, base_style="#0d2818")
                    text.append("\n")
                    j += 1
            else:
                # Context line (equal)
                line = old_lines[i] if i < len(old_lines) else ""
                text.append(f" {i+1:>{gutter}} ", style="#6e7681")
                text.append(f"  ", style="#6e7681")
                _render_highlighted_line(text, line, language)
                text.append("\n")
                i += 1
                j += 1

        text.append("\n")

    return text


def git_status_short(workspace: Path | None = None) -> dict[str, str | list[str]]:
    root = (workspace or settings.workspace).resolve()
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        stat = subprocess.check_output(
            ["git", "diff", "--stat", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return {"branch": branch, "status": status.splitlines() if status else [], "stat": stat}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"branch": "", "status": [], "stat": ""}


def git_diff_file(path: str, workspace: Path | None = None) -> str:
    root = (workspace or settings.workspace).resolve()
    try:
        return subprocess.check_output(
            ["git", "diff", "--no-color", "--", path],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
