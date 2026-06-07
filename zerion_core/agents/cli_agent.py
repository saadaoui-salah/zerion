from __future__ import annotations

import asyncio
import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any

from zerion_core.agents.base import Agent, AgentStatus, TaskResult
from zerion_core.cli.diff import diff_stats, git_diff_file
from zerion_core.config import settings
from zerion_core.llm.model_router import ModelRouter
from zerion_core.tools.cli_fix import auto_fix_command, should_skip_command, try_pathlib_fallback
from zerion_core.tools.project_map import format_project_context, is_windows, scan_workspace

CLIEventHandler = Callable[[str, dict[str, Any]], None]

CLI_SYSTEM = """You are the CLI Agent for Zerion-Core. You execute shell commands, create files, and perform surgical edits.

Return JSON only:
{
  "commands": [],
  "files": [{"path": "new_file.py", "content": "complete content here"}],
  "edits": [{"path": "existing_file.py", "old": "exact text to find", "new": "replacement text"}],
  "summary": "what you did"
}

CRITICAL RULES:
1. "files" is for NEW files or COMPLETE rewrites. The "content" field MUST contain the entire file.
2. "edits" is for surgical changes. Use "old" to specify the EXACT string to find (including indentation) and "new" for its replacement.
3. If "edits" fails because the "old" string wasn't found, try to use "files" with the COMPLETE file content instead.
4. READ the PROJECT STRUCTURE section — never mkdir/rmdir paths that already exist or don't exist
5. Prefer "files" or "edits" over "commands" — directories are auto-created when writing files
6. On Windows: never use forward slashes in mkdir; avoid mkdir entirely when possible
7. Do NOT run rmdir/rm unless the path appears in the project tree
"""

FIX_SYSTEM = """A shell command failed. Return JSON: {"fixed_command": "..." or null, "skip": true/false, "reason": "..."}
If the error means the directory already exists or path not found for delete, set skip=true.
On Windows use backslashes or python -c with pathlib for mkdir.
If a command like 'django-admin' fails, try 'python -m django <command>'.
If 'npm' fails, try 'npx' or 'node'.
Prefer skip over repeating the same failing command.
"""

BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\\",
    r"format\s+",
    r"del\s+/[sf]",
    r"shutdown",
    r"mkfs",
    r":\(\)\{\s*:\|:\&\s*\};:",
    r">\s*/dev/sd",
    r"dd\s+if=",
]

MAX_CMD_RETRIES = 2

# Windows reserved device names that cannot be used as file/directory names
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

# Characters forbidden in Windows file paths (beyond what the filesystem enforces)
_WINDOWS_INVALID_CHARS = frozenset('<>:"|?*')


class PathValidationError:
    """Result of a path type validation check."""

    def __init__(self, ok: bool, message: str = "", severity: str = "error") -> None:
        self.ok = ok
        self.message = message
        self.severity = severity  # "error" (blocks), "warning" (log only)

    def __bool__(self) -> bool:
        return self.ok


class CLIAgent(Agent):
    """Executes shell commands and writes files with structure awareness and auto-fix."""

    def __init__(
        self,
        *args: Any,
        on_cli_event: CLIEventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            "CLI",
            "cli",
            *args,
            **kwargs,
            system_prompt=CLI_SYSTEM,
        )
        self.workspace = settings.workspace.resolve()
        self.on_cli_event = on_cli_event or (lambda _t, _d: None)
        self._structure: dict = {}

    def _emit(self, event_type: str, **data: Any) -> None:
        self.on_cli_event(event_type, data)

    def _refresh_structure(self) -> str:
        self._structure = scan_workspace(self.workspace)
        text = format_project_context(self._structure)
        self.memory.working.set("project_structure", text)
        return text

    def _validate_path(self, rel_path: str, expect_file: bool = True) -> PathValidationError:
        """Validate a path for type collisions, reserved names, and Windows-specific issues.

        Args:
            rel_path: Relative path from workspace root.
            expect_file: True if the target should be a file, False for directory.

        Returns:
            PathValidationError with ok=True if valid, or ok=False with a message describing the issue.
        """
        target = (self.workspace / rel_path).resolve()

        # 1. Workspace boundary check
        if not str(target).startswith(str(self.workspace)):
            return PathValidationError(False, f"Blocked path outside workspace: {rel_path}")

        # 2. Windows reserved device names
        name = target.name
        name_stem = target.stem.upper() if "." in target.name else target.name.upper()
        if is_windows() and (name_stem in _WINDOWS_RESERVED or name.upper() in _WINDOWS_RESERVED):
            return PathValidationError(False, f"Reserved Windows device name: {name}")

        # 3. Invalid characters (Windows-only strict check)
        if is_windows():
            bad_chars = set(name) & _WINDOWS_INVALID_CHARS
            if bad_chars:
                return PathValidationError(False, f"Invalid characters in filename {name}: {''.join(bad_chars)}")

        # 4. Trailing dots/spaces (Windows silently strips these, causing confusion)
        if is_windows() and (name.endswith(".") or name.endswith(" ")):
            return PathValidationError(False, f"Filename ends with a dot or space (Windows will strip it): {name}")

        # 5. File/dir collision: target is a directory but we want to write a file
        if expect_file and target.exists() and target.is_dir():
            return PathValidationError(
                False,
                f"Path collision: {rel_path} is a directory, cannot create a file there"
            )

        # 6. File/dir collision: target is a file but we want to create a directory
        if not expect_file and target.exists() and target.is_file():
            return PathValidationError(
                False,
                f"Path collision: {rel_path} is a file, cannot create a directory there"
            )

        # 7. Parent is a file (cannot create child)
        if target.parent.exists() and target.parent.is_file():
            return PathValidationError(
                False,
                f"Path collision: parent {target.parent.relative_to(self.workspace)} is a file, "
                f"cannot create {name} inside it"
            )

        # 8. Case-insensitive collision on Windows: another file/dir with different case exists
        if is_windows() and target.parent.exists():
            try:
                siblings = [entry.name for entry in target.parent.iterdir()]
                target_lower = name.lower()
                for sibling in siblings:
                    if sibling.lower() == target_lower and sibling != name:
                        return PathValidationError(
                            False,
                            f"Case collision on Windows: '{sibling}' already exists, "
                            f"cannot create '{name}' (same path, different case)"
                        )
            except PermissionError:
                pass  # Cannot list directory, skip this check

        # 9. Extension mismatch warning: writing .py but path says .txt
        if expect_file:
            ext = target.suffix.lower()
            content_clues = {
                ".py": ("python", "script"),
                ".js": ("javascript", "node"),
                ".ts": ("typescript", "react"),
                ".tsx": ("tsx", "react"),
                ".jsx": ("jsx", "react"),
                ".json": ("json", "config"),
                ".md": ("markdown", "readme"),
            }
            # This is advisory only — don't block, just note it
            # (actual content validation would require reading the file first)

        return PathValidationError(True)

    def _validate_path_batch(self, paths: list[str], expect_file: bool = True) -> dict[str, PathValidationError]:
        """Validate multiple paths at once, returning a dict of path -> result."""
        results = {}
        for p in paths:
            results[p] = self._validate_path(p, expect_file=expect_file)
        return results

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> TaskResult:
        self.state.status = AgentStatus.WORKING
        self.state.current_task = task
        ctx = context or {}
        self._emit("cli_task", message=task, project=ctx.get("project", ""))
        self._emit("todo_add", message=task)

        project_tree = self._refresh_structure()
        memory_ctx = await self.memory.retrieve_context(task, project=ctx.get("project", ""))

        # Use RAG context if available, otherwise fall back to full project tree
        rag_ctx = ctx.get("rag_context", "")
        if rag_ctx:
            project_context = rag_ctx
        else:
            project_context = f"{project_tree}\n\n{memory_ctx}"

        try:
            resp = await self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Task: {task}\n"
                            f"Workspace: {self.workspace}\n"
                            f"OS: {'windows' if is_windows() else 'posix'}\n"
                            f"Context: {json.dumps({k: v for k, v in ctx.items() if k != 'rag_context'})}\n\n"
                            f"{project_context}"
                        ),
                    }
                ],
                model=ModelRouter.for_task("cli"),
                system=CLI_SYSTEM,
                json_mode=True,
            )
            plan = json.loads(resp.content)
        except (json.JSONDecodeError, Exception):
            plan = self._fallback_plan(task)

        results: list[str] = []
        errors: list[str] = []
        artifacts: dict[str, Any] = {"files_created": [], "files_edited": [], "commands_run": [], "diffs": []}

        for spec in plan.get("files", []):
            path = spec.get("path", "")
            content = spec.get("content", "")
            if not path:
                continue
            
            # PATH TYPE VALIDATION: Comprehensive collision/reserved-name check
            path_check = self._validate_path(path, expect_file=True)
            if not path_check.ok:
                self._emit("file_error", message=path_check.message, path=path)
                errors.append(path_check.message)
                continue

            ok, msg, diff_info = self._write_file(path, content)
            if ok:
                results.append(msg)
                key = "files_edited" if diff_info.get("edited") else "files_created"
                artifacts[key].append(path)
                artifacts["diffs"].append(diff_info)
                self._emit(
                    "file_diff",
                    message=msg,
                    path=path,
                    old=diff_info.get("old"),
                    new=content,
                    added=diff_info.get("added", 0),
                    removed=diff_info.get("removed", 0),
                    edited=diff_info.get("edited", False),
                )
                self._refresh_structure()
            else:
                errors.append(msg)
                self._emit("file_error", message=msg, path=path)

        for spec in plan.get("edits", []):
            path = spec.get("path", "")
            old_str = spec.get("old", "")
            new_str = spec.get("new", "")
            if not path or not old_str:
                continue

            # PATH TYPE VALIDATION: Ensure path is a valid file location
            path_check = self._validate_path(path, expect_file=True)
            if not path_check.ok:
                self._emit("file_error", message=path_check.message, path=path)
                errors.append(path_check.message)
                continue

            ok, msg, diff_info = self._edit_file(path, old_str, new_str)
            if ok:
                results.append(msg)
                if path not in artifacts["files_edited"]:
                    artifacts["files_edited"].append(path)
                artifacts["diffs"].append(diff_info)
                self._emit(
                    "file_diff",
                    message=msg,
                    path=path,
                    old=diff_info.get("old"),
                    new=diff_info.get("new"),
                    added=diff_info.get("added", 0),
                    removed=diff_info.get("removed", 0),
                    edited=True,
                )
                self._refresh_structure()
            else:
                errors.append(msg)
                self._emit("file_error", message=msg, path=path)

        for cmd in plan.get("commands", []):
            if not cmd or not isinstance(cmd, str):
                continue
            ok, msg = await self._run_command_with_retry(cmd)
            # Ensure silent skipping is reported as failure
            if ok and not msg.startswith("[skip]"):
                results.append(msg)
                artifacts["commands_run"].append(cmd)
                self._refresh_structure()
            else:
                errors.append(msg)
                self._emit("cli_error", message=msg, command=cmd)

        summary = plan.get("summary", task)
        # Only declare success if all operations explicitly succeeded
        success = len(errors) == 0
        output = "\n".join(results) if results else summary
        if errors:
            output += "\n\nErrors:\n" + "\n".join(errors)

        self.memory.refresh_project_structure()
        await self.memory.ingest_agent_output(
            output,
            project=ctx.get("project", "default"),
            agent=self.name,
            task_type="cli",
        )

        self._emit("cli_done", message=summary, success=success)
        self.state.status = AgentStatus.IDLE
        self.state.current_task = ""
        return TaskResult(
            success=success,
            output=output,
            artifacts=artifacts,
            errors=errors,
        )

    def _fallback_plan(self, task: str) -> dict[str, Any]:
        t = task.lower()
        if "hello" in t and "python" in t:
            return {
                "commands": [],
                "files": [{"path": "hello.py", "content": "print('Hello, World!')\n"}],
                "summary": "Created hello.py",
            }
        if "file" in t:
            name = "output.txt"
            m = re.search(r"([\w.-]+\.\w+)", task)
            if m:
                name = m.group(1)
            return {
                "commands": [],
                "files": [{"path": name, "content": f"# {task}\n"}],
                "summary": f"Created {name}",
            }
        return {"commands": [], "files": [], "summary": task}

    def _edit_file(self, rel_path: str, old: str, new: str) -> tuple[bool, str, dict[str, Any]]:
        try:
            target = (self.workspace / rel_path).resolve()
            if not str(target).startswith(str(self.workspace)):
                return False, f"Blocked path outside workspace: {rel_path}", {}

            # Defense-in-depth: validate even if caller already checked
            path_check = self._validate_path(rel_path, expect_file=True)
            if not path_check.ok:
                return False, path_check.message, {}

            if not target.exists():
                return False, f"File not found: {rel_path}", {}

            old_content = target.read_text(encoding="utf-8")
            
            # 1. Try exact match
            if old in old_content:
                new_content = old_content.replace(old, new, 1)
            else:
                # 2. Try relaxed match (strip each line and find corresponding sequence)
                old_lines = [l.strip() for l in old.strip().splitlines() if l.strip()]
                if not old_lines:
                    return False, f"Invalid 'old' string (empty) for {rel_path}", {}
                
                content_lines = old_content.splitlines()
                found_at = -1
                for i in range(len(content_lines)):
                    if i + len(old_lines) > len(content_lines):
                        break
                    
                    match = True
                    for j, old_line in enumerate(old_lines):
                        if content_lines[i + j].strip() != old_line:
                            match = False
                            break
                    if match:
                        found_at = i
                        break
                
                if found_at != -1:
                    # Found a relaxed match, reconstruct file
                    indent = ""
                    m = re.match(r"^(\s*)", content_lines[found_at])
                    if m:
                        indent = m.group(1)
                    
                    prefix = content_lines[:found_at]
                    suffix = content_lines[found_at + len(old_lines):]
                    
                    new_lines = new.splitlines()
                    indented_new = []
                    for nl in new_lines:
                        # Apply indentation if missing
                        if nl.strip() and not nl.startswith((" ", "\t")):
                            indented_new.append(indent + nl)
                        else:
                            indented_new.append(nl)
                            
                    new_content = "\n".join(prefix + indented_new + suffix)
                    if old_content.endswith("\n") and not new_content.endswith("\n"):
                        new_content += "\n"
                else:
                    return False, f"Target string not found in {rel_path}. Tip: Use 'files' with COMPLETE content if 'edits' fails.", {}

            target.write_text(new_content, encoding="utf-8")
            added, removed = diff_stats(old_content, new_content)
            msg = f"Edited {rel_path} (+{added} -{removed})"

            self._emit("file_write", message=msg, path=rel_path, edited=True)
            self._git_stage(rel_path)

            git_diff = git_diff_file(rel_path, self.workspace)
            if git_diff:
                self._emit("git_diff", message=rel_path, path=rel_path, diff=git_diff)

            return True, msg, {
                "path": rel_path,
                "old": old_content,
                "new": new_content,
                "added": added,
                "removed": removed,
                "edited": True,
            }
        except OSError as exc:
            return False, f"Failed to edit {rel_path}: {exc}", {}

    def _write_file(self, rel_path: str, content: str) -> tuple[bool, str, dict[str, Any]]:
        try:
            target = (self.workspace / rel_path).resolve()
            if not str(target).startswith(str(self.workspace)):
                return False, f"Blocked path outside workspace: {rel_path}", {}

            # Defense-in-depth: validate even if caller already checked
            path_check = self._validate_path(rel_path, expect_file=True)
            if not path_check.ok:
                return False, path_check.message, {}

            old_content: str | None = None
            edited = target.exists()
            if edited:
                old_content = target.read_text(encoding="utf-8")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            added, removed = diff_stats(old_content, content)
            verb = "Updated" if edited else "Created"
            msg = f"{verb} {rel_path} (+{added} -{removed})"

            self._emit("file_write", message=msg, path=rel_path, edited=edited)
            self._git_stage(rel_path)

            git_diff = git_diff_file(rel_path, self.workspace)
            if git_diff:
                self._emit("git_diff", message=rel_path, path=rel_path, diff=git_diff)

            return True, msg, {
                "path": rel_path,
                "old": old_content,
                "new": content,
                "added": added,
                "removed": removed,
                "edited": edited,
            }
        except OSError as exc:
            return False, f"Failed to write {rel_path}: {exc}", {}

    def _git_stage(self, rel_path: str) -> None:
        git_dir = self.workspace / ".git"
        if not git_dir.exists():
            return
        try:
            subprocess.run(
                ["git", "add", "--", rel_path],
                cwd=self.workspace,
                capture_output=True,
                check=False,
            )
        except OSError:
            pass

    def _is_blocked(self, cmd: str) -> bool:
        lower = cmd.lower().strip()
        return any(re.search(p, lower) for p in BLOCKED_PATTERNS)

    async def _run_command_with_retry(self, cmd: str) -> tuple[bool, str]:
        dirs = self._structure.get("dirs", [])
        skip, skip_msg = should_skip_command(cmd, self.workspace, dirs)
        if skip:
            self._emit("cli_retry", message=skip_msg, command=cmd, auto=True)
            return True, skip_msg

        ok, msg = await self._run_command(cmd)
        if ok:
            return ok, msg

        # Pathlib fallback (mkdir/rmdir)
        fallback = try_pathlib_fallback(cmd, msg, self.workspace)
        if fallback:
            self._emit("cli_retry", message=fallback[1], command=cmd, auto=True)
            return fallback

        # Heuristic command rewrite
        fixed = auto_fix_command(cmd, msg, self.workspace)
        if fixed and fixed != cmd:
            self._emit("cli_retry", message=f"Retry: {fixed}", command=fixed, auto=True)
            ok2, msg2 = await self._run_command(fixed)
            if ok2:
                return True, f"[fixed] {msg2}"
            msg = msg2

        # LLM-assisted fix
        for attempt in range(MAX_CMD_RETRIES):
            llm_fix = await self._llm_fix_command(cmd, msg)
            if llm_fix.get("skip"):
                self._emit("cli_retry", message=llm_fix.get("reason", "skipped"), command=cmd, auto=True)
                return True, f"[skip] {llm_fix.get('reason', cmd)}"
            new_cmd = llm_fix.get("fixed_command")
            if not new_cmd or new_cmd == cmd:
                break
            self._emit("cli_retry", message=f"LLM fix: {new_cmd}", command=new_cmd, auto=True)
            ok3, msg3 = await self._run_command(new_cmd)
            if ok3:
                return True, f"[llm-fix] {msg3}"
            cmd, msg = new_cmd, msg3

        return False, msg

    async def _llm_fix_command(self, cmd: str, error: str) -> dict[str, Any]:
        try:
            resp = await self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Command: {cmd}\nError: {error}\n"
                            f"OS: {'windows' if is_windows() else 'posix'}\n"
                            f"Project dirs: {', '.join(self._structure.get('dirs', [])[:30])}"
                        ),
                    }
                ],
                model=ModelRouter.for_task("cli"),
                system=FIX_SYSTEM,
                json_mode=True,
                temperature=0.0,
            )
            return json.loads(resp.content)
        except (json.JSONDecodeError, Exception):
            return {"skip": False, "fixed_command": None}

    async def _run_command(self, cmd: str) -> tuple[bool, str]:
        if self._is_blocked(cmd):
            self._emit("cli_error", message=f"Blocked: {cmd}", command=cmd)
            return False, f"Blocked command: {cmd}"

        self._emit("cli_command", message=cmd, command=cmd)

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdout and proc.stderr

            out_lines: list[str] = []
            err_lines: list[str] = []

            async def read_stream(stream: asyncio.StreamReader, name: str, bucket: list[str]) -> None:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode(errors="replace").rstrip("\n\r")
                    bucket.append(text)
                    self._emit("cli_output", message=text, command=cmd, stream=name)

            await asyncio.gather(
                read_stream(proc.stdout, "stdout", out_lines),
                read_stream(proc.stderr, "stderr", err_lines),
            )
            exit_code = await proc.wait()

            self._emit("cli_exit", message=cmd, command=cmd, exit_code=exit_code)

            out = "\n".join(out_lines).strip()
            err = "\n".join(err_lines).strip()
            combined = err or out or f"exit {exit_code}"
            if exit_code == 0:
                detail = out or "ok"
                return True, f"$ {cmd}\n{detail}"
            return False, f"$ {cmd}\n{combined}"
        except OSError as exc:
            self._emit("cli_error", message=str(exc), command=cmd)
            return False, f"Command failed: {cmd} — {exc}"


def task_needs_cli(task: dict[str, Any]) -> bool:
    text = (task.get("title", "") + " " + task.get("description", "")).lower()
    keywords = (
        "file", "folder", "directory", "git", "init", "mkdir", "command",
        "run ", "create", "write", "script", "shell", "execute", "repository",
        "hello world", "cli", "terminal", "npm", "pip install",
    )
    return any(k in text for k in keywords)
