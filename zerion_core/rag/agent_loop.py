from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter
from zerion_core.rag.context_builder import ContextBuilder
from zerion_core.rag.retriever import CodeRetriever, RetrievalResult


MAX_ITERATIONS = 3
RAG_AGENT_SYSTEM = """You are a code-aware AI assistant with access to the codebase via retrieval.

You receive relevant code chunks as context. Use them to:
- Understand the codebase structure and conventions
- Make precise, minimal changes
- Reference specific files and functions
- Avoid hallucinating code that doesn't exist

When you need more context, ask for it specifically by describing what you need.
Always respond with a clear plan or solution. Reference file paths and line numbers when possible.
"""


@dataclass
class AgentIteration:
    iteration: int
    query: str
    retrieved: list[RetrievalResult]
    response: str


@dataclass
class RAGResponse:
    answer: str
    iterations: list[AgentIteration]
    total_chunks_used: int
    files_referenced: list[str]


class RAGAgent:
    """Iterative agent that retrieves code context and generates responses."""

    def __init__(self, llm: OllamaClient, retriever: CodeRetriever) -> None:
        self.llm = llm
        self.retriever = retriever
        self.context_builder = ContextBuilder()

    async def query(
        self,
        task: str,
        k: int = 8,
        language_filter: str | None = None,
        max_iterations: int = MAX_ITERATIONS,
    ) -> RAGResponse:
        """Run iterative retrieval-augmented generation."""
        iterations: list[AgentIteration] = []
        all_retrieved: list[RetrievalResult] = []
        accumulated_context = ""

        for i in range(max_iterations):
            # Retrieve relevant code
            results = await self.retriever.retrieve(task, k=k, language_filter=language_filter)
            all_retrieved.extend(results)

            # Build context
            context = self.context_builder.build_context(results, task)
            accumulated_context = self._merge_context(accumulated_context, context)

            # Generate response
            prompt = f"{accumulated_context}\n\n## Task\n{task}"
            if i > 0:
                prompt += f"\n\n(Iteration {i + 1}/{max_iterations} - I need more specific information)"

            resp = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=ModelRouter.for_task("research"),
                system=RAG_AGENT_SYSTEM,
            )

            iterations.append(AgentIteration(
                iteration=i + 1,
                query=task,
                retrieved=results,
                response=resp.content,
            ))

            # Check if the response indicates need for more retrieval
            if not self._needs_more_context(resp.content, i, max_iterations):
                break

            # Refine query based on response
            task = self._refine_query(task, resp.content)

        files = list({r.chunk.file_path for r in all_retrieved if r.chunk.file_path})
        return RAGResponse(
            answer=iterations[-1].response if iterations else "",
            iterations=iterations,
            total_chunks_used=len(all_retrieved),
            files_referenced=files,
        )

    async def retrieve_only(self, query: str, k: int = 8, language_filter: str | None = None) -> list[RetrievalResult]:
        """Just retrieve without LLM generation."""
        return await self.retriever.retrieve(query, k=k, language_filter=language_filter)

    def _merge_context(self, existing: str, new: str) -> str:
        if not existing:
            return new
        # Dedup by file references
        existing_files = set()
        for line in existing.splitlines():
            if line.startswith("--- ") and "::" in line:
                existing_files.add(line.split("---")[1].strip().split("::")[0].strip())

        merged_lines = [existing, "\n\n## Additional Context\n"]
        for line in new.splitlines():
            if line.startswith("--- ") and "::" in line:
                fname = line.split("---")[1].strip().split("::")[0].strip()
                if fname in existing_files:
                    continue
            merged_lines.append(line)
        return "\n".join(merged_lines)

    def _needs_more_context(self, response: str, current_iter: int, max_iter: int) -> bool:
        if current_iter >= max_iter - 1:
            return False
        indicators = [
            "I need to see more",
            "I need additional context",
            "could you provide",
            "I need to look at",
            "more information needed",
            "need to examine",
            "please share",
            "insufficient context",
        ]
        return any(ind.lower() in response.lower() for ind in indicators)

    def _refine_query(self, original: str, response: str) -> str:
        """Extract refinement hints from the response to improve the next retrieval."""
        # If response mentions specific files or functions, add them to the query
        import re
        file_refs = re.findall(r"(?:file|module)\s+[`\"']?([/\w.]+\.\w+)[`\"']?", response, re.IGNORECASE)
        func_refs = re.findall(r"(?:function|method|class)\s+[`\"']?(\w+)[`\"']?", response, re.IGNORECASE)

        additions = []
        if file_refs:
            additions.extend(file_refs[:3])
        if func_refs:
            additions.extend(func_refs[:3])

        if additions:
            return f"{original} ({', '.join(additions)})"
        return original
