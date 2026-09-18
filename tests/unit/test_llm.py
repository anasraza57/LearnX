"""
Unit tests for the chat model factory and usage instrumentation (src/llm.py).
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from src.config import config
from src.llm import (
    DeterminismError,
    UsageCallback,
    UsageLog,
    current_call,
    current_run,
    make_chat_model,
    parse_json_response,
    tracked_invoke,
)


@pytest.fixture
def model_config():
    """Snapshot and restore the model settings the factory reads."""
    fields = ("model_name", "base_url", "api_key", "deterministic", "supports_temperature", "reasoning_effort",
              "max_retries", "retry_delay")
    saved = {f: getattr(config.model, f) for f in fields}
    yield config.model
    for f, v in saved.items():
        setattr(config.model, f, v)


def _kwargs(mock_cls):
    return mock_cls.call_args.kwargs


class TestMakeChatModel:
    @patch("src.llm.ChatOpenAI")
    def test_uses_configured_model_and_agent_temperature(self, mock_cls, model_config):
        model_config.model_name = "model-x"
        model_config.deterministic = False
        model_config.supports_temperature = True
        make_chat_model("instructor", temperature=0.7)
        kwargs = _kwargs(mock_cls)
        assert kwargs["model"] == "model-x"
        assert kwargs["temperature"] == 0.7
        assert "seed" not in kwargs

    @patch("src.llm.ChatOpenAI")
    def test_model_name_override(self, mock_cls, model_config):
        model_config.model_name = "model-x"
        make_chat_model("advocate", temperature=0.3, model_name="model-y")
        assert _kwargs(mock_cls)["model"] == "model-y"

    @patch("src.llm.ChatOpenAI")
    def test_deterministic_mode_zeroes_temperature_and_sets_seed(self, mock_cls, model_config):
        model_config.deterministic = True
        model_config.supports_temperature = True
        make_chat_model("designer", temperature=0.4)
        kwargs = _kwargs(mock_cls)
        assert kwargs["temperature"] == 0.0
        assert kwargs["seed"] == config.model.random_seed

    @patch("src.llm.ChatOpenAI")
    def test_temperature_omitted_when_backend_rejects_it(self, mock_cls, model_config):
        model_config.deterministic = True
        model_config.supports_temperature = False
        make_chat_model("designer", temperature=0.4)
        assert "temperature" not in _kwargs(mock_cls)

    @patch("src.llm.ChatOpenAI")
    def test_base_url_routes_to_openai_compatible_server(self, mock_cls, model_config):
        model_config.base_url = "http://localhost:11434/v1"
        make_chat_model("instructor", temperature=0.7)
        assert _kwargs(mock_cls)["base_url"] == "http://localhost:11434/v1"

    @patch("src.llm.ChatOpenAI")
    def test_usage_callback_attached_with_agent_role(self, mock_cls, model_config):
        chat = make_chat_model("assessment", temperature=0.7)
        assert len(chat.callbacks) == 1
        assert isinstance(chat.callbacks[0], UsageCallback)
        assert chat.callbacks[0].agent == "assessment"

    @patch("src.llm.ChatOpenAI")
    def test_client_retries_disabled(self, mock_cls, model_config):
        make_chat_model("assessment", temperature=0.7)
        assert _kwargs(mock_cls)["max_retries"] == 0


class TestRequestParameters:
    """Real clients (no network): the parameters that would actually be sent."""

    @pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-4o-mini", "gpt-3.5-turbo"])
    def test_deterministic_requests_carry_temperature_zero(self, model, model_config):
        model_config.deterministic = True
        model_config.supports_temperature = True
        model_config.reasoning_effort = None
        model_config.api_key = "test"
        chat = make_chat_model("instructor", temperature=0.7, model_name=model)
        payload = chat._get_request_payload([HumanMessage(content="hi")])
        assert payload["temperature"] == 0.0
        assert payload["seed"] == config.model.random_seed
        assert chat.callbacks[0].request_params["temperature"] == 0.0

    @pytest.mark.parametrize("model", ["gpt-5.4-mini", "gpt-4o-mini", "gpt-3.5-turbo"])
    def test_api_requests_carry_the_output_cap(self, model, model_config):
        model_config.api_key = "test"
        model_config.max_tokens = 8192
        chat = make_chat_model("instructor", temperature=0.2, model_name=model)
        payload = chat._get_request_payload([HumanMessage(content="hi")])
        # langchain renames the field; either spelling is the cap arriving
        assert payload.get("max_completion_tokens") or payload.get("max_tokens") == 8192

    def test_local_requests_carry_max_tokens_not_the_renamed_field(self, model_config):
        """
        Ollama's OpenAI-compatible endpoint honours max_tokens and ignores
        max_completion_tokens, which is what langchain renames the field to. Sent
        under the wrong name the cap is a silent no-op, and a model that fails to
        terminate then generates until it fills its context window.
        """
        model_config.api_key = "ollama"
        model_config.base_url = "http://localhost:11434/v1"
        model_config.max_tokens = 8192
        chat = make_chat_model("advocate", temperature=0.2, model_name="mistral-7b-32k")
        payload = chat._get_request_payload([HumanMessage(content="hi")])
        assert payload["extra_body"]["max_tokens"] == 8192
        assert "max_completion_tokens" not in payload

    def test_a_cap_that_would_not_be_sent_is_an_error(self, model_config, monkeypatch):
        model_config.api_key = "test"
        model_config.max_tokens = 8192
        monkeypatch.setattr("src.llm._request_params",
                            lambda chat: {"temperature": 0.2, "seed": None,
                                          "reasoning_effort": None, "top_p": None,
                                          "output_cap": None})
        with pytest.raises(DeterminismError, match="output cap"):
            make_chat_model("instructor", temperature=0.2, model_name="gpt-4o-mini")

    def test_unsendable_temperature_is_an_error(self, model_config):
        model_config.deterministic = True
        model_config.supports_temperature = True
        model_config.reasoning_effort = "low"  # gpt-5 then drops temperature
        model_config.api_key = "test"
        with pytest.raises(DeterminismError):
            make_chat_model("instructor", temperature=0.7, model_name="gpt-5.4-mini")


class TestTrackedInvoke:
    def test_call_id_shared_by_all_attempts_and_retried(self, model_config):
        model_config.max_retries = 2
        model_config.retry_delay = 0
        seen = []
        llm = MagicMock()

        def flaky(messages):
            seen.append(current_call.get())
            if len(seen) == 1:
                raise openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
            return AIMessage(content="ok")

        llm.invoke.side_effect = flaky
        reply, call_id = tracked_invoke(llm, "hi")
        assert reply.content == "ok"
        assert seen == [call_id, call_id]
        assert current_call.get() is None

    def test_rate_limits_are_retried_for_longer_and_honour_retry_after(self, model_config, monkeypatch):
        import src.llm as llm_module
        model_config.max_retries = 1          # the ordinary budget is small
        waits = []
        monkeypatch.setattr(llm_module.time, "sleep", waits.append)

        response = httpx.Response(429, headers={"retry-after": "12"}, request=httpx.Request("POST", "http://x"))
        error = openai.RateLimitError("rate limited", response=response, body=None)
        llm = MagicMock()
        llm.invoke.side_effect = [error, error, AIMessage(content="ok")]

        reply, _ = tracked_invoke(llm, "hi")
        assert reply.content == "ok"
        assert llm.invoke.call_count == 3      # more attempts than max_retries allows
        assert waits == [12.0, 12.0]           # the server's Retry-After, not the short backoff

    def test_rate_limit_without_retry_after_waits_in_tens_of_seconds(self, model_config, monkeypatch):
        import src.llm as llm_module
        waits = []
        monkeypatch.setattr(llm_module.time, "sleep", waits.append)
        error = openai.RateLimitError(
            "rate limited", response=httpx.Response(429, request=httpx.Request("POST", "http://x")), body=None)
        llm = MagicMock()
        llm.invoke.side_effect = [error, AIMessage(content="ok")]
        tracked_invoke(llm, "hi")
        assert waits == [llm_module.RATE_LIMIT_WAIT_S]

    def test_rate_limit_gives_up_eventually(self, model_config, monkeypatch):
        import src.llm as llm_module
        monkeypatch.setattr(llm_module.time, "sleep", lambda _: None)
        error = openai.RateLimitError(
            "rate limited", response=httpx.Response(429, request=httpx.Request("POST", "http://x")), body=None)
        llm = MagicMock()
        llm.invoke.side_effect = error
        with pytest.raises(openai.RateLimitError):
            tracked_invoke(llm, "hi")
        assert llm.invoke.call_count == llm_module.RATE_LIMIT_ATTEMPTS + 1

    def test_non_transient_errors_are_not_retried(self, model_config):
        llm = MagicMock()
        llm.invoke.side_effect = ValueError("bad request")
        with pytest.raises(ValueError):
            tracked_invoke(llm, "hi")
        assert llm.invoke.call_count == 1


class TestParseJsonResponse:
    @pytest.mark.parametrize("text", [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Here you go:\n```json\n{"a": 1}\n```\nEnjoy.',
    ])
    def test_wrappers(self, text):
        assert parse_json_response(text) == {"a": 1}

    def test_code_fence_inside_string(self):
        text = '```json\n{"question_text": "What prints?\\n```python\\nprint(1)\\n```"}\n```'
        assert parse_json_response(text)["question_text"].startswith("What prints?")

    def test_no_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("I cannot help with that.")


def _result(llm_output=None, message=None, finish_reason="stop"):
    message = message or AIMessage(content="hi")
    generation = ChatGeneration(message=message, generation_info={"finish_reason": finish_reason})
    return LLMResult(generations=[[generation]], llm_output=llm_output)


class TestUsageCallback:
    def test_records_openai_token_usage(self):
        log = UsageLog()
        cb = UsageCallback(agent="instructor", model="m", log=log)
        run_id = uuid.uuid4()
        cb.on_chat_model_start({}, [[]], run_id=run_id)
        cb.on_llm_end(
            _result(llm_output={
                "model_name": "m-2026-01-01",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 20,
                    "prompt_tokens_details": {"cached_tokens": 40},
                    "completion_tokens_details": {"reasoning_tokens": 5},
                },
            }),
            run_id=run_id,
        )
        (rec,) = log.records()
        assert rec["agent"] == "instructor"
        assert rec["resolved_model"] == "m-2026-01-01"
        assert (rec["input_tokens"], rec["cached_input_tokens"], rec["output_tokens"]) == (100, 40, 20)
        assert rec["reasoning_tokens"] == 5
        assert rec["finish_reason"] == "stop"
        assert rec["latency_s"] is not None and rec["latency_s"] >= 0
        assert rec["error"] is None

    def test_falls_back_to_usage_metadata(self):
        log = UsageLog()
        cb = UsageCallback(agent="advocate", model="m", log=log)
        message = AIMessage(
            content="hi",
            usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
            response_metadata={"model_name": "local-model"},
        )
        cb.on_llm_end(_result(message=message), run_id=uuid.uuid4())
        (rec,) = log.records()
        assert (rec["input_tokens"], rec["output_tokens"]) == (7, 3)
        assert rec["resolved_model"] == "local-model"
        assert rec["latency_s"] is None  # no start event seen

    def test_records_errors(self):
        log = UsageLog()
        cb = UsageCallback(agent="designer", model="m", log=log)
        cb.on_llm_error(ValueError("boom"), run_id=uuid.uuid4())
        (rec,) = log.records()
        assert rec["error"] == "ValueError: boom"
        assert rec["input_tokens"] is None

    def test_records_are_attributed_to_current_run(self):
        log = UsageLog()
        cb = UsageCallback(agent="instructor", model="m", log=log)
        token = current_run.set("A1/S01")
        try:
            cb.on_llm_end(_result(llm_output={"token_usage": {"prompt_tokens": 1, "completion_tokens": 1}}), run_id=uuid.uuid4())
        finally:
            current_run.reset(token)
        cb.on_llm_end(_result(llm_output={"token_usage": {"prompt_tokens": 1, "completion_tokens": 1}}), run_id=uuid.uuid4())

        assert len(log.pop_run("A1/S01")) == 1
        remaining = log.records()
        assert len(remaining) == 1 and remaining[0]["run"] is None

    def test_summary_by_agent(self):
        log = UsageLog()
        log.add({"agent": "a", "input_tokens": 10, "output_tokens": 5, "latency_s": 1.0, "error": None})
        log.add({"agent": "a", "input_tokens": None, "output_tokens": None, "latency_s": None, "error": "x"})
        log.add({"agent": "b", "input_tokens": 1, "output_tokens": 1, "latency_s": 0.5, "error": None})
        summary = log.summary_by_agent()
        assert summary["a"] == {"calls": 2, "errors": 1, "input_tokens": 10, "output_tokens": 5, "latency_s": 1.0}
        assert summary["b"]["calls"] == 1
