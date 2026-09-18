"""
Chat model factory and LLM usage instrumentation.

Every agent obtains its chat model from ``make_chat_model`` so that:
- the backend is chosen in one place (OpenAI, or any OpenAI-compatible server
  such as Ollama at http://localhost:11434/v1, selected via ``config.model.base_url``);
- the determinism policy is applied uniformly (temperature 0 and a fixed seed
  when ``config.model.deterministic`` is set);
- every call is recorded with its agent role, the parameters actually sent,
  token usage, latency and finish reason in ``usage_log``, and routed to the
  global ``token_tracker``;
- transient API failures are retried by ``tracked_invoke``, and each failed
  attempt is recorded.
"""

from __future__ import annotations

import contextvars
import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import openai
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

try:
    from .config import config, token_tracker
except ImportError:
    from src.config import config, token_tracker


OLLAMA_BASE_URL = "http://localhost:11434/v1"

# Label of the unit of work currently executing (e.g. "A1/S07"), attached to
# every usage record so concurrent runs can be separated.
current_run: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_run", default=None)
# Identifier of the artefact-producing call in progress (see tracked_invoke). All
# attempts of a retried call share it, so artefacts can be joined to usage records.
current_call: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_call", default=None)

RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.InternalServerError,
)

# A tokens-per-minute limit clears in minutes, not seconds, so rate limits get
# their own budget: the server's Retry-After when it sends one, else a wait that
# grows to a minute. Without this, a few parallel runs against a per-minute quota
# exhaust the ordinary retries and lose the whole run's work.
RATE_LIMIT_ATTEMPTS = 6
RATE_LIMIT_WAIT_S = 20.0
RATE_LIMIT_MAX_WAIT_S = 60.0


class UsageLog:
    """Thread-safe store of per-call LLM usage records."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []

    def add(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._records.append(record)

    def records(self, run: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if run is None:
                return list(self._records)
            return [r for r in self._records if r.get("run") == run]

    def pop_run(self, run: str) -> List[Dict[str, Any]]:
        """Remove and return the records of one run."""
        with self._lock:
            mine = [r for r in self._records if r.get("run") == run]
            self._records = [r for r in self._records if r.get("run") != run]
            return mine

    def reset(self) -> None:
        with self._lock:
            self._records = []

    def summary_by_agent(self, records: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, float]]:
        """Aggregate calls, tokens and latency per agent role."""
        summary: Dict[str, Dict[str, float]] = {}
        for rec in self.records() if records is None else records:
            agg = summary.setdefault(
                rec["agent"],
                {"calls": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0},
            )
            agg["calls"] += 1
            agg["errors"] += 1 if rec.get("error") else 0
            agg["input_tokens"] += rec.get("input_tokens") or 0
            agg["output_tokens"] += rec.get("output_tokens") or 0
            agg["latency_s"] += rec.get("latency_s") or 0.0
        return summary


usage_log = UsageLog()


def _extract_usage(response) -> Dict[str, Optional[int]]:
    """Read token usage from an LLMResult, whichever field the backend filled."""
    input_tokens = output_tokens = reasoning_tokens = cached_tokens = None
    llm_output = response.llm_output or {}
    resolved_model = llm_output.get("model_name")
    fingerprint = llm_output.get("system_fingerprint")

    token_usage = llm_output.get("token_usage") or {}
    if token_usage:
        input_tokens = token_usage.get("prompt_tokens")
        output_tokens = token_usage.get("completion_tokens")
        reasoning_tokens = (token_usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        cached_tokens = (token_usage.get("prompt_tokens_details") or {}).get("cached_tokens")

    message = None
    if response.generations and response.generations[0]:
        message = getattr(response.generations[0][0], "message", None)
    if message is not None:
        metadata = message.response_metadata or {}
        resolved_model = resolved_model or metadata.get("model_name")
        fingerprint = fingerprint or metadata.get("system_fingerprint")
        usage = getattr(message, "usage_metadata", None) or {}
        if input_tokens is None and usage:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            reasoning_tokens = (usage.get("output_token_details") or {}).get("reasoning")
            cached_tokens = (usage.get("input_token_details") or {}).get("cache_read")

    return {
        "resolved_model": resolved_model,
        "system_fingerprint": fingerprint,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
    }


class UsageCallback(BaseCallbackHandler):
    """Records one usage entry per LLM call, attributed to an agent role."""

    def __init__(
        self,
        agent: str,
        model: str,
        log: UsageLog = usage_log,
        request_params: Optional[Dict[str, Any]] = None,
    ):
        self.agent = agent
        self.model = model
        self.log = log
        self.request_params = request_params or {}
        self._starts: Dict[Any, float] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs) -> None:
        self._starts[run_id] = time.perf_counter()

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs) -> None:
        self._starts[run_id] = time.perf_counter()

    def _base_record(self, run_id) -> Dict[str, Any]:
        start = self._starts.pop(run_id, None)
        return {
            "run": current_run.get(),
            "call_id": current_call.get(),
            "agent": self.agent,
            "model": self.model,
            "base_url": config.model.base_url,
            "request_params": self.request_params,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_s": (time.perf_counter() - start) if start is not None else None,
        }

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        record = self._base_record(run_id)
        record.update(_extract_usage(response))

        finish_reason = None
        if response.generations and response.generations[0]:
            info = response.generations[0][0].generation_info or {}
            finish_reason = info.get("finish_reason")
        record["finish_reason"] = finish_reason
        record["error"] = None
        self.log.add(record)

        token_tracker.add_tokens(
            input_tokens=record["input_tokens"] or 0,
            output_tokens=record["output_tokens"] or 0,
        )

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        record = self._base_record(run_id)
        record.update(
            {
                "resolved_model": None,
                "system_fingerprint": None,
                "cached_input_tokens": None,
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "finish_reason": None,
                "error": f"{type(error).__name__}: {error}",
            }
        )
        self.log.add(record)


class DeterminismError(RuntimeError):
    """The deterministic policy is on but the request would not carry temperature 0."""


def _request_params(chat: ChatOpenAI) -> Optional[Dict[str, Any]]:
    """The sampling parameters the client will actually send (after langchain's own validation)."""
    payload = chat._get_request_payload([HumanMessage(content="ping")])
    if not isinstance(payload, dict):  # a mocked client in tests
        return None
    params = {key: payload.get(key) for key in ("temperature", "seed", "reasoning_effort", "top_p")}
    # langchain sends the cap as max_completion_tokens, which OpenAI accepts and
    # Ollama silently ignores, so both spellings are inspected.
    params["output_cap"] = (payload.get("max_tokens")
                           or payload.get("max_completion_tokens")
                           or (payload.get("extra_body") or {}).get("max_tokens"))
    return params


def make_chat_model(
    agent: str,
    temperature: float,
    model_name: Optional[str] = None,
):
    """
    Build the chat model an agent should use.

    Args:
        agent: Role name used to attribute usage (e.g. "advocate", "instructor")
        temperature: The agent's deployment temperature. Replaced by 0 when
            ``config.model.deterministic`` is set, and omitted entirely when the
            backend does not accept a temperature
        model_name: Override of ``config.model.model_name``

    Returns:
        A ChatOpenAI client pointed at the configured backend. Call it through
        ``tracked_invoke`` to get retries and artefact-to-usage linkage

    Raises:
        DeterminismError: if temperature 0 is required but would not be sent
    """
    model = model_name or config.model.model_name
    kwargs: Dict[str, Any] = {
        "model": model,
        "api_key": config.model.api_key or "not-needed",
        "timeout": config.model.request_timeout,
        "max_retries": 0,  # retried by tracked_invoke, so every attempt is recorded
    }
    # Ollama's OpenAI-compatible endpoint honours max_tokens and ignores
    # max_completion_tokens, which is what langchain renames the field to. The cap
    # is therefore set through model_kwargs for a local backend, verified below.
    if config.model.base_url:
        kwargs["extra_body"] = {"max_tokens": config.model.max_tokens}
    else:
        kwargs["max_tokens"] = config.model.max_tokens
    if config.model.base_url:
        kwargs["base_url"] = config.model.base_url
    if config.model.supports_temperature:
        kwargs["temperature"] = 0.0 if config.model.deterministic else temperature
    if config.model.deterministic:
        kwargs["seed"] = config.model.random_seed

    effort = config.model.reasoning_effort
    chat = ChatOpenAI(**kwargs, **({"reasoning_effort": effort} if effort else {}))
    params = _request_params(chat)
    if params is not None and "temperature" in kwargs and params["temperature"] is None and not effort:
        # langchain-openai drops temperature for gpt-5 models unless reasoning is
        # explicitly off; "none" is the documented default for the mini models
        chat = ChatOpenAI(**kwargs, reasoning_effort="none")
        params = _request_params(chat)
    if params is not None and params.get("output_cap") != config.model.max_tokens:
        raise DeterminismError(
            f"{model}: the output cap of {config.model.max_tokens} tokens would not be sent "
            f"(request carries {params.get('output_cap')!r}). Without it a model that fails to "
            f"terminate generates until it fills its context window."
        )
    if params is not None and "temperature" in kwargs and params["temperature"] != kwargs["temperature"]:
        raise DeterminismError(
            f"{model}: temperature {kwargs['temperature']} would not be sent (request has {params['temperature']})."
        )

    chat.callbacks = [UsageCallback(agent=agent, model=model, request_params=params)]
    return chat


def retry_after_seconds(error: Exception) -> Optional[float]:
    """The server's own Retry-After, if it sent one."""
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
        value = headers.get(name)
        if value:
            try:
                return float(value) * scale
            except (TypeError, ValueError):
                continue
    return None


def tracked_invoke(llm, messages) -> Tuple[Any, str]:
    """
    Invoke a model and return (reply, call_id). Every usage record of this call,
    including failed attempts, carries the same call_id.

    Transient API errors are retried with exponential backoff up to
    config.model.max_retries times. Rate limits are retried separately and for
    longer, because a per-minute quota does not clear in seconds.
    """
    call_id = str(uuid.uuid4())
    token = current_call.set(call_id)
    rate_limited = transient = 0
    try:
        while True:
            try:
                return llm.invoke(messages), call_id
            except openai.RateLimitError as error:
                rate_limited += 1
                if rate_limited > RATE_LIMIT_ATTEMPTS:
                    raise
                wait = retry_after_seconds(error) or min(
                    RATE_LIMIT_MAX_WAIT_S, RATE_LIMIT_WAIT_S * rate_limited
                )
                time.sleep(wait)
            except RETRYABLE_ERRORS:
                transient += 1
                if transient > config.model.max_retries:
                    raise
                time.sleep(config.model.retry_delay * config.model.retry_backoff ** (transient - 1))
    finally:
        current_call.reset(token)


_OUTER_FENCE = re.compile(r"^```[A-Za-z]*\s*\n(.*)\n\s*```$", re.DOTALL)


def parse_json_response(text: str) -> Any:
    """
    Parse a JSON value from a model reply: bare, wrapped in one outer code fence,
    or embedded in prose. Fences inside JSON strings (code in a question) are safe.

    Raises:
        json.JSONDecodeError: if no JSON object can be found
    """
    stripped = text.strip()
    candidates = [stripped]
    fenced = _OUTER_FENCE.match(stripped)
    if fenced:
        candidates.append(fenced.group(1))
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start:end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("no JSON object found", text, 0)
