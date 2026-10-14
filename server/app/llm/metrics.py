"""Prometheus metrics for language-model calls (exposed on /metrics with the HTTP metrics)."""
from prometheus_client import Counter, Gauge, Histogram

CALLS = Counter("indusmind_llm_calls_total", "Language-model calls", ["kind", "outcome"])
SECONDS = Histogram("indusmind_llm_call_seconds", "Language-model call duration, including queueing", ["kind"],
                    buckets=(0.5, 1, 2, 4, 8, 15, 30, 60, 120))
TOKENS = Counter("indusmind_llm_tokens_total", "Tokens processed by the language model", ["direction"])
WAITING = Gauge("indusmind_llm_queue_waiting", "Questions waiting for a model slot")
BREAKER_OPEN = Gauge("indusmind_llm_circuit_open", "1 while the circuit breaker is open")
