from __future__ import annotations

from zerion_core.rag.retriever import RetrievalResult


MAX_CONTEXT_CHARS = 12000
MAX_CHUNKS_IN_CONTEXT = 8


class ContextBuilder:
    """Format retrieved code chunks into structured LLM prompts."""

    def __init__(self, max_chars: int = MAX_CONTEXT_CHARS, max_chunks: int = MAX_CHUNKS_IN_CONTEXT) -> None:
        self.max_chars = max_chars
        self.max_chunks = max_chunks

    def build_context(self, results: list[RetrievalResult], query: str = "") -> str:
        """Format retrieval results into a context block for the LLM."""
        if not results:
            return ""

        # Deduplicate by file_path + symbol_name
        seen: set[str] = set()
        deduped: list[RetrievalResult] = []
        for r in results:
            key = f"{r.chunk.file_path}:{r.chunk.symbol_name}:{r.chunk.start_line}"
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        # Take top-N by score
        deduped.sort(key=lambda r: r.final_score, reverse=True)
        selected = deduped[: self.max_chunks]

        # Build context with budget
        lines: list[str] = ["## Retrieved Code Context", ""]
        total_chars = len(lines[0])

        for result in selected:
            chunk_text = result.to_context()
            if total_chars + len(chunk_text) > self.max_chars:
                # Truncate this chunk to fit
                remaining = self.max_chars - total_chars - 100
                if remaining > 200:
                    truncated = chunk_text[:remaining] + "\n... (truncated)"
                    lines.append(truncated)
                break
            lines.append(chunk_text)
            total_chars += len(chunk_text) + 1

        lines.append("")
        lines.append("Use the above code context to inform your response. Reference specific files and symbols when relevant.")
        return "\n".join(lines)

    def build_file_summary(self, results: list[RetrievalResult]) -> str:
        """Build a compact file-level summary from results."""
        if not results:
            return ""

        files: dict[str, list[RetrievalResult]] = {}
        for r in results:
            fp = r.chunk.file_path
            if fp not in files:
                files[fp] = []
            files[fp].append(r)

        lines: list[str] = ["## Relevant Files Summary", ""]
        for fp, chunks in files.items():
            symbols = [c.chunk.symbol_name for c in chunks if c.chunk.symbol_name and not c.chunk.symbol_name.startswith("__")]
            lines.append(f"**{fp}**")
            if symbols:
                lines.append(f"  Symbols: {', '.join(symbols[:10])}")
            lines.append(f"  Chunks retrieved: {len(chunks)}")
            lines.append("")

        return "\n".join(lines)

    def build_structured_prompt(self, results: list[RetrievalResult], task: str) -> str:
        """Build a fully structured prompt with code context and task instructions."""
        context = self.build_context(results)
        file_summary = self.build_file_summary(results)

        parts = []
        if file_summary:
            parts.append(file_summary)
        if context:
            parts.append(context)
        parts.append(f"## Task\n{task}")

        return "\n\n".join(parts)
