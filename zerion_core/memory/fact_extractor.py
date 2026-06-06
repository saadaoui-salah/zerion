from __future__ import annotations

import json
import re
from typing import Any

from zerion_core.llm.ollama import OllamaClient
from zerion_core.llm.model_router import ModelRouter


EXTRACTION_PROMPT = """Extract durable facts from the agent output below.
Return JSON only:
{
  "facts": [{"key": "...", "value": "...", "confidence": 0.0-1.0}],
  "decisions": ["..."],
  "preferences": [{"key": "...", "value": "..."}],
  "patterns": ["..."],
  "ignore": true/false
}
Rules:
- ignore=true if content is small talk, temporary, or not worth storing
- Never store raw conversation
- Store architectural choices, fixes, preferences, reusable patterns
"""


class FactExtractor:
    """Mem0-style fact extraction from agent outputs."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    async def extract(self, text: str, context: str = "") -> dict[str, Any]:
        if len(text.strip()) < 20:
            return {"ignore": True, "facts": [], "decisions": [], "preferences": [], "patterns": []}

        heuristic = self._heuristic_extract(text)
        if heuristic.get("facts") or heuristic.get("decisions"):
            return heuristic

        try:
            resp = await self.llm.chat(
                messages=[
                    {
                        "role": "user",
                        "content": f"Context: {context}\n\nOutput:\n{text[:4000]}",
                    }
                ],
                model=ModelRouter.for_task("memory_extraction"),
                system=EXTRACTION_PROMPT,
                json_mode=True,
                temperature=0.0,
            )
            return self._normalize_extracted(json.loads(resp.content))
        except (json.JSONDecodeError, Exception):
            return heuristic

    def _normalize_extracted(self, data: dict[str, Any]) -> dict[str, Any]:
        """Coerce LLM output fields to expected types."""
        from zerion_core.memory.models import coerce_str

        facts = []
        for f in data.get("facts", []):
            if isinstance(f, dict):
                facts.append(
                    {
                        "key": coerce_str(f.get("key", "fact")),
                        "value": coerce_str(f.get("value", "")),
                        "confidence": float(f.get("confidence", 0.8)),
                    }
                )
        prefs = []
        for p in data.get("preferences", []):
            if isinstance(p, dict):
                prefs.append({"key": coerce_str(p.get("key", "preference")), "value": coerce_str(p.get("value", ""))})
        return {
            "ignore": bool(data.get("ignore", False)),
            "facts": facts,
            "decisions": [coerce_str(d) for d in data.get("decisions", []) if d],
            "preferences": prefs,
            "patterns": [coerce_str(p) for p in data.get("patterns", []) if p],
        }

    def _heuristic_extract(self, text: str) -> dict[str, Any]:
        facts: list[dict[str, Any]] = []
        decisions: list[str] = []
        preferences: list[dict[str, str]] = []
        patterns: list[str] = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            if lower.startswith(("decided:", "decision:", "chose ", "using ")):
                decisions.append(line)
            elif "prefer" in lower:
                m = re.search(r"prefer(?:s|red)?\s+(.+)", lower)
                if m:
                    preferences.append({"key": "preference", "value": m.group(1).strip()})
            elif any(k in lower for k in ("framework", "library", "pattern", "architecture")):
                facts.append({"key": "technical", "value": line, "confidence": 0.7})
            elif lower.startswith(("fixed:", "bug:", "solution:")):
                patterns.append(line)

        ignore = not (facts or decisions or preferences or patterns)
        return {
            "ignore": ignore,
            "facts": facts,
            "decisions": decisions,
            "preferences": preferences,
            "patterns": patterns,
        }
