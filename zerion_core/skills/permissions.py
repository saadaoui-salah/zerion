"""Skill permissions: enforces tool access restrictions per skill."""

from __future__ import annotations

from typing import Any

from zerion_core.skills.models import Skill


class SkillPermissions:
    """Manages and enforces tool permissions for skills."""

    # Built-in tool names
    KNOWN_TOOLS = {
        "read_file", "write_file", "edit_file", "grep", "glob",
        "bash", "curl", "git", "web_fetch", "web_search",
        "list_dir", "create_dir", "delete_file", "move_file",
        "memory_read", "memory_write", "rag_query",
        "ask_user", "skill_activate", "skill_deactivate",
    }

    def __init__(self) -> None:
        self._enforce = True
        self._overrides: dict[str, list[str]] = {}

    def set_enforcement(self, enabled: bool) -> None:
        self._enforce = enabled

    def add_override(self, skill_name: str, tools: list[str]) -> None:
        """Grant additional tools to a specific skill."""
        self._overrides.setdefault(skill_name, []).extend(tools)

    def check_permission(self, skill: Skill, tool_name: str) -> bool:
        """Check if a skill is allowed to use a tool."""
        if not self._enforce:
            return True

        if tool_name in skill.manifest.tools.denied:
            return False

        if tool_name in skill.manifest.tools.required:
            return True

        if tool_name in skill.manifest.tools.optional:
            return True

        if tool_name in self._overrides.get(skill.manifest.name, []):
            return True

        # If skill has no tool restrictions, allow all
        if not skill.manifest.tools.required and not skill.manifest.tools.denied:
            return True

        # If skill has required list but tool not in it, deny
        if skill.manifest.tools.required and tool_name not in skill.manifest.tools.required:
            return False

        return True

    def get_allowed_tools(self, skill: Skill) -> list[str]:
        """Get list of tools allowed for a skill."""
        if not skill.manifest.tools.required:
            allowed = list(self.KNOWN_TOOLS)
        else:
            allowed = list(skill.manifest.tools.required)

        allowed.extend(self._overrides.get(skill.manifest.name, []))

        for denied in skill.manifest.tools.denied:
            if denied in allowed:
                allowed.remove(denied)

        return allowed

    def get_denied_tools(self, skill: Skill) -> list[str]:
        """Get list of tools denied for a skill."""
        return list(skill.manifest.tools.denied)

    def filter_tools(
        self,
        skill: Skill,
        available_tools: list[str],
    ) -> list[str]:
        """Filter available tools by skill permissions."""
        return [t for t in available_tools if self.check_permission(skill, t)]

    def validate_skill_permissions(self, skill: Skill) -> list[str]:
        """Validate skill permission declarations. Returns warnings."""
        warnings = []

        for tool in skill.manifest.tools.required:
            if tool not in self.KNOWN_TOOLS:
                warnings.append(f"Unknown required tool: {tool}")

        for tool in skill.manifest.tools.denied:
            if tool not in self.KNOWN_TOOLS:
                warnings.append(f"Unknown denied tool: {tool}")

        for tool in skill.manifest.tools.optional:
            if tool not in self.KNOWN_TOOLS:
                warnings.append(f"Unknown optional tool: {tool}")

        # Check for conflicts
        required_set = set(skill.manifest.tools.required)
        denied_set = set(skill.manifest.tools.denied)
        conflicts = required_set & denied_set
        if conflicts:
            warnings.append(f"Conflicting tool declarations: {conflicts}")

        return warnings

    def format_permissions(self, skill: Skill) -> str:
        """Format skill permissions for display."""
        lines = [f"Permissions for {skill.manifest.name}:"]

        if skill.manifest.tools.required:
            lines.append(f"  Required: {', '.join(skill.manifest.tools.required)}")
        if skill.manifest.tools.optional:
            lines.append(f"  Optional: {', '.join(skill.manifest.tools.optional)}")
        if skill.manifest.tools.denied:
            lines.append(f"  Denied: {', '.join(skill.manifest.tools.denied)}")

        if not any([skill.manifest.tools.required, skill.manifest.tools.optional, skill.manifest.tools.denied]):
            lines.append("  All tools allowed")

        return "\n".join(lines)
