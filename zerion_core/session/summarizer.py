"""LLM-powered rolling context summarizer for long conversations."""

from __future__ import annotations

import json
from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter
from zerion_core.session.models import Message, MessageRole, ToolEvent

SUMMARIZE_SYSTEM = """You are a conversation summarizer for a coding assistant. Your job is to produce a compact, information-dense summary of a conversation.

RULES:
1. Preserve ALL technical decisions (architecture, patterns, frameworks chosen)
2. Preserve ALL bugs found and their fixes
3. Preserve ALL file paths and code changes mentioned
4. Preserve the CURRENT GOAL and progress toward it
5. Preserve UNRESOLVED issues or questions
6. Remove conversational filler, greetings, clarifications
7. Use bullet points for conciseness
8. Include file paths as-is (never paraphrase file names)
9. Keep the summary under 800 words
10. Structure: ## Goal, ## Key Decisions, ## Changes Made, ## Bugs/Fixes, ## Current State, ## Next Steps"""

MERGE_SYSTEM = """You are merging two conversation summaries into one compact summary.

RULES:
1. Deduplicate overlapping information
2. Preserve ALL technical decisions and file paths from both
3. Keep the most recent state for any contradictory information
4. Maintain the structured format: ## Goal, ## Key Decisions, ## Changes Made, ## Bugs/Fixes, ## Current State, ## Next Steps
5. Stay under 800 words
6. Preserve temporal order (older first, newer after)"""

TITLE_SYSTEM = """Generate a concise 5-10 word title for this coding conversation.
Return ONLY the title text, no quotes, no explanation.
Focus on the main task or topic discussed.
Examples: "Fix auth middleware bug", "Add dark mode to dashboard", "Refactor database layer"
"""


class SessionSummarizer:
    """Rolling summarizer that maintains a compact session memory."""

    def __init__(self, llm: OllamaClient, max_raw_messages: int = 15) -> None:
        self.llm = llm
        self.max_raw_messages = max_raw_messages

    async def summarize_messages(
        self,
        existing_summary: str,
        new_messages: list[Message],
        tool_events: list[ToolEvent] | None = None,
    ) -> str:
        """Merge new messages into existing summary using LLM."""
        if not new_messages and not existing_summary:
            return ""

        # Format new messages
        new_text = self._format_messages(new_messages)
        tool_text = self._format_tool_events(tool_events or [])
        if tool_text:
            new_text += f"\n\n## Tool Activity\n{tool_text}"

        if not new_text.strip():
            return existing_summary

        prompt_parts = []
        if existing_summary:
            prompt_parts.append(f"## Previous Summary\n{existing_summary}")
        prompt_parts.append(f"## New Messages\n{new_text}")
        prompt = "\n\n".join(prompt_parts)

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=ModelRouter.for_task("memory_extraction"),
                system=SUMMARIZE_SYSTEM,
                temperature=0.1,
            )
            return resp.content.strip()
        except Exception:
            # Fallback: prepend recent messages as-is
            return self._fallback_summary(existing_summary, new_messages)

    async def generate_title(self, messages: list[Message]) -> str:
        """Auto-generate a session title from conversation content."""
        preview = self._format_messages(messages[:6])
        if not preview.strip():
            return "Untitled session"

        try:
            resp = await self.llm.chat(
                messages=[{"role": "user", "content": preview}],
                model=ModelRouter.for_task("memory_extraction"),
                system=TITLE_SYSTEM,
                temperature=0.2,
            )
            title = resp.content.strip().strip('"').strip("'")
            return title[:100] if title else "Untitled session"
        except Exception:
            # Fallback: use first user message
            for m in messages:
                if m.role == MessageRole.USER:
                    return m.content[:80].replace("\n", " ")
            return "Untitled session"

    def should_summarize(self, message_count: int) -> bool:
        """Check if it's time to run summarization."""
        return message_count > self.max_raw_messages

    def get_raw_window(self, messages: list[Message], window_size: int | None = None) -> list[Message]:
        """Get the raw message window (most recent N messages)."""
        size = window_size or self.max_raw_messages
        return messages[-size:]

    def get_summary_context(self, summary: str, messages: list[Message]) -> list[dict[str, str]]:
        """Build the context window: summary + recent messages."""
        context: list[dict[str, str]] = []
        if summary:
            context.append({"role": "system", "content": f"## Session Summary\n{summary}"})

        raw = self.get_raw_window(messages)
        for m in raw:
            context.append({"role": m.role.value, "content": m.content})
        return context

    def _format_messages(self, messages: list[Message]) -> str:
        lines: list[str] = []
        for m in messages:
            role = m.role.value.capitalize()
            content = m.content.strip()
            if content:
                lines.append(f"[{role}]: {content[:2000]}")
        return "\n\n".join(lines)

    def _format_tool_events(self, events: list[ToolEvent]) -> str:
        if not events:
            return ""
        lines: list[str] = []
        for e in events[-10:]:
            status = "OK" if e.success else f"FAIL: {e.error}"
            lines.append(f"- {e.tool_name}({e.target}) → {status}")
            if e.summary:
                lines.append(f"  {e.summary[:200]}")
        return "\n".join(lines)

    def _fallback_summary(self, existing: str, messages: list[Message]) -> str:
        """Simple text-based fallback when LLM is unavailable."""
        parts: list[str] = []
        if existing:
            parts.append(existing)
        for m in messages[-self.max_raw_messages:]:
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT):
                snippet = m.content[:300].replace("\n", " ")
                parts.append(f"[{m.role.value}]: {snippet}")
        return "\n".join(parts)
