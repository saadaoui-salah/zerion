"""Context builder: assembles the final prompt for every LLM call with token optimization."""

from __future__ import annotations

from typing import Any

from zerion_core.session.models import Message, MessageRole, SessionState
from zerion_core.session.summarizer import SessionSummarizer

MAX_PROMPT_TOKENS = 12000
CHARS_PER_TOKEN = 4  # rough estimate


class ContextBuilder:
    """Builds the final prompt context from summary + messages + RAG + state."""

    def __init__(
        self,
        summarizer: SessionSummarizer,
        max_chars: int = MAX_PROMPT_TOKENS * CHARS_PER_TOKEN,
    ) -> None:
        self.summarizer = summarizer
        self.max_chars = max_chars

    def build(
        self,
        summary: str,
        messages: list[Message],
        system_prompt: str = "",
        rag_context: str = "",
        project_memory: str = "",
        state: SessionState | None = None,
        user_request: str = "",
    ) -> list[dict[str, str]]:
        """Assemble the full context for an LLM call.

        Returns a list of message dicts ready for llm.chat().
        """
        parts: list[dict[str, str]] = []
        budget = self.max_chars

        # 1. System prompt (highest priority)
        if system_prompt:
            parts.append({"role": "system", "content": system_prompt})
            budget -= len(system_prompt)

        # 2. Project memory (persistent, compact)
        if project_memory:
            sections = [f"## Project Context\n{project_memory}"]
            section_text = "\n".join(sections)
            if len(section_text) < budget * 0.2:
                parts.append({"role": "system", "content": section_text})
                budget -= len(section_text)

        # 3. Session summary (compressed memory)
        if summary:
            summary_block = f"## Session Memory\n{summary}"
            if len(summary_block) < budget * 0.3:
                parts.append({"role": "system", "content": summary_block})
                budget -= len(summary_block)

        # 4. RAG context (retrieved code)
        if rag_context:
            if len(rag_context) < budget * 0.3:
                parts.append({"role": "system", "content": rag_context})
                budget -= len(rag_context)

        # 5. State context (open files, errors, etc.)
        if state:
            state_block = self._format_state(state)
            if state_block and len(state_block) < budget * 0.1:
                parts.append({"role": "system", "content": state_block})
                budget -= len(state_block)

        # 6. Recent messages (raw window)
        raw_window = self.summarizer.get_raw_window(messages)
        for msg in raw_window:
            content = msg.content
            if len(content) > 2000:
                content = content[:2000] + "... (truncated)"
            if len(content) < budget:
                parts.append({"role": msg.role.value, "content": content})
                budget -= len(content)

        # 7. Current user request (always last, always included)
        if user_request:
            parts.append({"role": "user", "content": user_request})

        return parts

    def build_with_summary_update(
        self,
        summary: str,
        messages: list[Message],
        new_messages: list[Message],
        tool_events: list[Any],
        system_prompt: str = "",
        rag_context: str = "",
        project_memory: str = "",
        state: SessionState | None = None,
        user_request: str = "",
    ) -> tuple[list[dict[str, str]], str]:
        """Build context and also return updated summary.

        Returns (context_messages, new_summary).
        """
        # Update summary with new messages
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # We're in async context, but this method is sync
            # So we use a placeholder approach
            new_summary = summary  # Will be updated async separately
        except RuntimeError:
            new_summary = summary

        ctx = self.build(
            summary=new_summary,
            messages=messages,
            system_prompt=system_prompt,
            rag_context=rag_context,
            project_memory=project_memory,
            state=state,
            user_request=user_request,
        )
        return ctx, new_summary

    def _format_state(self, state: SessionState) -> str:
        lines: list[str] = ["## Current State"]
        if state.active_task:
            lines.append(f"Active task: {state.active_task}")
        if state.current_goal:
            lines.append(f"Current goal: {state.current_goal}")
        if state.open_files:
            lines.append(f"Open files: {', '.join(state.open_files[-10:])}")
        if state.last_errors:
            recent_errors = state.last_errors[-3:]
            lines.append(f"Recent errors: {'; '.join(recent_errors)}")
        if state.applied_patches:
            recent_patches = state.applied_patches[-5:]
            patch_files = [p.get("file", "?") for p in recent_patches]
            lines.append(f"Recently modified: {', '.join(patch_files)}")
        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def estimate_tokens(self, context: list[dict[str, str]]) -> int:
        total_chars = sum(len(m.get("content", "")) for m in context)
        return total_chars // CHARS_PER_TOKEN
