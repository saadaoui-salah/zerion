from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from zerion_core.config import settings


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    done: bool = True


class OllamaClient:
    """Async Ollama client for chat and embeddings."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client = httpx.AsyncClient(timeout=300.0)
        self.total_usage = TokenUsage()

    async def close(self) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        system: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> LLMResponse:
        model = model or settings.default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["messages"] = [{"role": "system", "content": system}, *messages]
        if json_mode:
            payload["format"] = "json"

        resp = await self._client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        usage = TokenUsage(
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )
        self.total_usage.prompt_tokens += usage.prompt_tokens
        self.total_usage.completion_tokens += usage.completion_tokens
        return LLMResponse(content=data["message"]["content"], model=model, usage=usage)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or settings.default_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["messages"] = [{"role": "system", "content": system}, *messages]

        async with self._client.stream(
            "POST", f"{self.base_url}/api/chat", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if content := chunk.get("message", {}).get("content"):
                    yield content

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or settings.embedding_model
        resp = await self._client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": model, "prompt": text},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return [await self.embed(t, model) for t in texts]

    async def list_models(self) -> list[str]:
        resp = await self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    async def create_model(self, name: str, from_model: str, system: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Create a new model in Ollama using specific parameters."""
        payload = {"name": name, "from": from_model, "stream": True}
        if system:
            payload["system"] = system
            
        async with self._client.stream(
            "POST", f"{self.base_url}/api/create", json=payload
        ) as resp:
            if resp.status_code >= 400:
                error_body = await resp.aread()
                try:
                    error_json = json.loads(error_body)
                    error_msg = error_json.get("error", error_body.decode())
                except Exception:
                    error_msg = error_body.decode()
                raise httpx.HTTPStatusError(
                    f"Ollama creation failed: {error_msg}",
                    request=resp.request,
                    response=resp
                )
            
            async for line in resp.aiter_lines():
                if not line:
                    continue
                yield json.loads(line)

    async def health(self) -> bool:
        try:
            resp = await self._client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
