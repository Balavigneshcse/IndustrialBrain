"""Async Ollama client.

- Timeouts: 3 s to connect, LLM_TIMEOUT_SECONDS between streamed chunks. One retry on connection
  errors and 5xx responses, but never after text has already been streamed.
- Circuit breaker: after LLM_BREAKER_FAILURES consecutive failures, calls fail fast for
  LLM_BREAKER_COOLDOWN_SECONDS (callers fall back to extractive answers), then calls are tried again.
- Gate: at most LLM_CONCURRENCY generations at once (= OLLAMA_NUM_PARALLEL), first come first served,
  with visible queue positions; more than LLM_MAX_QUEUE waiting -> LLMBusy (HTTP 429). The gate lives in
  this process, so run one API process per GPU.
"""
import asyncio
import json
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from ..core.config import Settings, get_settings
from . import metrics


class LLMUnavailable(Exception):
    """Ollama is unreachable or failing, the model is missing, or the circuit breaker is open."""


class LLMBusy(Exception):
    """Too many questions are already waiting for the model."""


class _Retryable(Exception):
    pass


@dataclass
class Completion:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    done_reason: str = ""


class CircuitBreaker:
    def __init__(self, threshold: int, cooldown: float):
        self.threshold, self.cooldown = threshold, cooldown
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half-open" if time.monotonic() - self.opened_at >= self.cooldown else "open"

    def success(self) -> None:
        self.failures, self.opened_at = 0, None
        metrics.BREAKER_OPEN.set(0)

    def failure(self) -> None:
        self.failures += 1
        if self.opened_at is not None or self.failures >= self.threshold:
            self.opened_at = time.monotonic()  # open, or re-open after a failed trial call
            metrics.BREAKER_OPEN.set(1)


class Gate:
    """First-come-first-served limit of `slots` concurrent generations."""

    def __init__(self, slots: int, max_waiting: int):
        self.slots, self.max_waiting = slots, max_waiting
        self.active = 0
        self.waiting: deque[asyncio.Future] = deque()

    def enter(self) -> asyncio.Future:
        """A ticket that resolves when a slot is granted. Always pair with leave()."""
        ticket = asyncio.get_running_loop().create_future()
        if self.active < self.slots and not self.waiting:
            self.active += 1
            ticket.set_result(None)
        elif len(self.waiting) >= self.max_waiting:
            raise LLMBusy()
        else:
            self.waiting.append(ticket)
            metrics.WAITING.set(len(self.waiting))
        return ticket

    def position(self, ticket: asyncio.Future) -> int:
        """1-based place in the queue; 0 once the slot is granted."""
        try:
            return self.waiting.index(ticket) + 1
        except ValueError:
            return 0

    async def wait(self, ticket: asyncio.Future, timeout: float) -> bool:
        """Wait up to `timeout` seconds; True once the slot is granted."""
        if not ticket.done():
            try:
                await asyncio.wait_for(asyncio.shield(ticket), timeout)
            except TimeoutError:
                pass
        return ticket.done()

    def leave(self, ticket: asyncio.Future) -> None:
        """Release a granted slot (handing it to the next in line), or drop a ticket still waiting."""
        if not ticket.done():
            self.waiting.remove(ticket)
            ticket.cancel()
        else:
            while self.waiting:
                following = self.waiting.popleft()
                if not following.done():
                    following.set_result(None)
                    break
            else:
                self.active -= 1
        metrics.WAITING.set(len(self.waiting))


class OllamaClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.ollama_url.rstrip("/")
        self.model = self.settings.llm_model
        self.breaker = CircuitBreaker(self.settings.llm_breaker_failures, self.settings.llm_breaker_cooldown_seconds)
        self.gate = Gate(self.settings.llm_concurrency, self.settings.llm_max_queue)
        self.transport = transport
        self._status: tuple[float, dict] | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def available(self) -> bool:
        """False when generation is disabled or the breaker is open: use the extractive fallback."""
        return self.enabled and self.breaker.state != "open"

    def _http(self, read_timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, transport=self.transport,
                                 timeout=httpx.Timeout(read_timeout, connect=3.0))

    def _payload(self, messages: list[dict], max_tokens: int, schema: dict | None,
                 temperature: float | None) -> dict:
        s = self.settings
        body = {
            "model": self.model, "messages": messages, "stream": True, "keep_alive": s.llm_keep_alive,
            # num_ctx and num_gpu are identical in every call: a different value reloads the model.
            "options": {"num_ctx": s.llm_num_ctx, "num_gpu": s.llm_num_gpu, "num_predict": max_tokens,
                        "temperature": s.llm_temperature if temperature is None else temperature,
                        "top_p": 0.8, "top_k": 20},
        }
        if s.llm_seed is not None:
            body["options"]["seed"] = s.llm_seed
        if schema is not None:
            body["format"] = schema
        return body

    async def stream(self, messages: list[dict], *, max_tokens: int, schema: dict | None = None,
                     temperature: float | None = None, kind: str = "answer") -> AsyncIterator[dict]:
        """Yields {"type": "queued", "position"} while waiting, {"type": "token", "text"} per piece,
        then one {"type": "done", ...Completion fields}. Raises LLMUnavailable or LLMBusy. Close the
        iterator (contextlib.aclosing) to stop generation and free the slot."""
        if not self.available():
            metrics.CALLS.labels(kind, "skipped").inc()
            raise LLMUnavailable("circuit breaker open" if self.enabled else "generation disabled")
        started = time.monotonic()
        ticket = self.gate.enter()
        try:
            shown = None
            while not await self.gate.wait(ticket, 1.0):
                position = self.gate.position(ticket)
                if position != shown:
                    shown = position
                    yield {"type": "queued", "position": position}
                if time.monotonic() - started > self.settings.llm_timeout_seconds:
                    metrics.CALLS.labels(kind, "busy").inc()
                    raise LLMBusy()
            payload = self._payload(messages, max_tokens, schema, temperature)
            for attempt in (1, 2):
                emitted = False
                try:
                    async with self._http(self.settings.llm_timeout_seconds) as http, \
                            http.stream("POST", "/api/chat", json=payload) as response:
                        if response.status_code >= 500:
                            raise _Retryable(f"Ollama HTTP {response.status_code}")
                        if response.status_code >= 400:
                            detail = (await response.aread()).decode(errors="replace")[:200]
                            raise LLMUnavailable(f"Ollama HTTP {response.status_code}: {detail}")
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            data = json.loads(line)
                            if data.get("error"):
                                raise LLMUnavailable(f"Ollama: {data['error']}")
                            piece = (data.get("message") or {}).get("content", "")
                            if piece:
                                emitted = True
                                yield {"type": "token", "text": piece}
                            if data.get("done"):
                                self.breaker.success()
                                done = Completion(
                                    text="", prompt_tokens=data.get("prompt_eval_count", 0),
                                    completion_tokens=data.get("eval_count", 0),
                                    seconds=time.monotonic() - started, done_reason=data.get("done_reason", ""))
                                metrics.CALLS.labels(kind, "ok").inc()
                                metrics.SECONDS.labels(kind).observe(done.seconds)
                                metrics.TOKENS.labels("prompt").inc(done.prompt_tokens)
                                metrics.TOKENS.labels("completion").inc(done.completion_tokens)
                                yield {"type": "done", **done.__dict__}
                                return
                        raise _Retryable("stream ended without a final message")
                except (httpx.TransportError, _Retryable, json.JSONDecodeError) as exc:
                    self.breaker.failure()
                    if emitted or attempt == 2 or self.breaker.state == "open":
                        metrics.CALLS.labels(kind, "error").inc()
                        raise LLMUnavailable(f"{type(exc).__name__}: {exc}") from exc
                except LLMUnavailable:
                    self.breaker.failure()
                    metrics.CALLS.labels(kind, "error").inc()
                    raise
        finally:
            self.gate.leave(ticket)

    async def complete(self, messages: list[dict], *, max_tokens: int, schema: dict | None = None,
                       temperature: float | None = None, kind: str = "answer") -> Completion:
        parts: list[str] = []
        result = Completion(text="")
        async for event in self.stream(messages, max_tokens=max_tokens, schema=schema,
                                       temperature=temperature, kind=kind):
            if event["type"] == "token":
                parts.append(event["text"])
            elif event["type"] == "done":
                result = Completion(**{k: v for k, v in event.items() if k != "type"})
        result.text = "".join(parts)
        return result

    async def status(self, max_age: float = 0.0) -> dict:
        """{"state": "ok" | "missing" | "unreachable" | "disabled", "detail"}, cached for max_age seconds."""
        if not self.enabled:
            return {"state": "disabled", "detail": "LLM_ENABLED=false: answers are extractive"}
        now = time.monotonic()
        if self._status and now - self._status[0] < max_age:
            return self._status[1]
        try:
            async with self._http(3.0) as http:
                loaded = [m for m in (await http.get("/api/ps")).json().get("models") or []
                          if self.model in (m.get("name"), m.get("model"))]
                if loaded:
                    size, vram = loaded[0].get("size") or 0, loaded[0].get("size_vram") or 0
                    share = round(100 * vram / size) if size else 0
                    result = {"state": "ok", "detail": f"{self.model} loaded, {share}% on the GPU"}
                elif any(self.model in (m.get("name"), m.get("model"))
                         for m in (await http.get("/api/tags")).json().get("models") or []):
                    result = {"state": "ok", "detail": f"{self.model} installed; it loads on the first question"}
                else:
                    result = {"state": "missing", "detail": f"model not installed: ollama pull {self.model}"}
        except (httpx.HTTPError, ValueError) as exc:
            result = {"state": "unreachable",
                      "detail": f"Ollama unreachable at {self.base_url} ({type(exc).__name__}); answers are extractive"}
        if result["state"] == "ok" and self.breaker.state == "open":
            result = {"state": "ok", "detail": result["detail"] + "; circuit breaker open after recent failures"}
        self._status = (now, result)
        return result


_client: OllamaClient | None = None


def get_llm() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def set_llm(client: OllamaClient | None) -> None:
    """Replace the process-wide client (tests use a fake Ollama transport)."""
    global _client
    _client = client
