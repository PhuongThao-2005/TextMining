"""UI integration coverage without configured models, indexes, or remote calls."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from service.qa_service import PreflightCheck, QuestionRequest, SafeError
from service.ui_runtime import DEMO_MODE, ProductionReadiness
from src.ui.i18n import t


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FAILURE = "https://private-service.runpod.net/readyz: HTTP 404"


@pytest.fixture
def product_app(monkeypatch):
    """Run the real entrypoint with only external/runtime boundaries replaced."""
    from service import local_env

    monkeypatch.setattr(local_env, "apply_local_environment", lambda _: None)
    monkeypatch.setenv("SHOW_DEVELOPER_UI", "false")
    monkeypatch.setenv("DENSE_SERVICE_URL", "")
    monkeypatch.setenv("BM25_SERVICE_URL", "")
    spec = importlib.util.spec_from_file_location("lexvn_product_test_app", PROJECT_ROOT / "ui" / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    registry = module.load_ui_config_registry(module.CONFIG_PATH)
    runtime = SimpleNamespace(ready=True, failure=None, response_status=None, requests=[], demo_requests=[])
    monkeypatch.setattr(module, "_cached_registry", lambda *args: registry)
    monkeypatch.setattr(module, "_retrieval_mode_blocker", lambda _: None)
    monkeypatch.setattr(module, "_cached_resources", lambda *args: object())

    def readiness(config_json, config_name, *args):
        return ProductionReadiness(
            runtime.ready, config_name, "fixture-backend", "fixture-embedding",
            (PreflightCheck("fixture-check", "ready" if runtime.ready else "blocked", RAW_FAILURE),),
            () if runtime.ready else (RAW_FAILURE,), (), (), None, json.loads(config_json),
        )

    monkeypatch.setattr(module, "_cached_readiness", readiness)
    demo_type = module.DemoAnswerProvider

    class RecordingDemoProvider:
        def answer(self, request):
            runtime.demo_requests.append(request)
            return demo_type().answer(request)

    def answer(request, **kwargs):
        runtime.requests.append(request)
        if runtime.failure:
            raise RuntimeError(runtime.failure)
        response = demo_type().answer(QuestionRequest("Show a single source example", request.config_name))
        response = replace(
            response, mode="production", is_mock=False, question=request.question,
            contexts=tuple(replace(row, is_mock=False) for row in response.contexts),
            citation_sources=tuple(replace(source, is_mock=False) for source in response.citation_sources),
            warnings=(), citation_warnings=(),
        )
        if runtime.response_status:
            response = replace(
                response, status=runtime.response_status, answer=None,
                error=SafeError("retrieval", "HTTPError", RAW_FAILURE, RAW_FAILURE),
                warnings=(RAW_FAILURE,), citation_sources=(), citation_references=(),
            )
        return response

    monkeypatch.setattr(module, "DemoAnswerProvider", RecordingDemoProvider)
    monkeypatch.setattr(module, "answer_question", answer)
    monkeypatch.setattr(module, "_demo_examples", lambda lang: (("Ví dụ", "Show a single source example"),))

    def start(**state):
        app = AppTest.from_string("import lexvn_product_test_app\nlexvn_product_test_app.main()", default_timeout=15)
        for key, value in state.items():
            app.session_state[key] = value
        app.run()
        assert not app.exception, [item.message for item in app.exception]
        return app

    return SimpleNamespace(start=start, runtime=runtime, module=module)


def visible_text(app) -> str:
    """Include visible copy and controls, excluding injected CSS and state data."""
    values = []
    for element in app:
        for attribute in ("label", "value"):
            value = getattr(element, attribute, None)
            if isinstance(value, str) and not value.startswith("<style>"):
                values.append(value)
    return "\n".join(values)


def click(app, key):
    app.button(key=key).click().run()
    assert not app.exception, [item.message for item in app.exception]
    return app


def submit_landing(app, question="Người lao động được nghỉ phép bao nhiêu ngày?"):
    app.text_area[0].set_value(question)
    next(button for button in app.button if str(button.key).startswith("FormSubmitter:landing-search")).click().run()
    assert not app.exception, [item.message for item in app.exception]
    return app


def test_production_hides_diagnostics_but_keeps_demo_accessible(product_app):
    product_app.runtime.ready = False
    app = product_app.start()
    text = visible_text(app)
    assert app.text_area
    assert RAW_FAILURE not in text
    assert "fixture-backend" not in text
    sidebar_text = visible_text(app.sidebar)
    assert all(label in sidebar_text for label in ("Dense Only", "Dense-Sparse", "Reranker", "gpt-4o-mini"))
    assert "fixture-check" not in sidebar_text
    assert any("demo" in button.label.lower() for button in app.sidebar.button)
    assert not product_app.runtime.requests


def test_demo_submission_never_uses_production_provider(product_app):
    product_app.runtime.ready = False
    app = product_app.start(runtime_mode=DEMO_MODE)
    submit_landing(app)
    turns = app.session_state["conversation"]
    assert len(turns) == 1 and turns[0].response.is_mock
    assert product_app.runtime.demo_requests
    assert not product_app.runtime.requests
    assert app.chat_input


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_request_failures_are_localized_without_raw_endpoint_details(product_app, lang):
    product_app.runtime.failure = RAW_FAILURE
    app = product_app.start(language_choice=lang)
    submit_landing(app)
    text = visible_text(app)
    assert RAW_FAILURE not in text
    assert "runpod.net" not in text and "HTTP 404" not in text
    assert "Unable to complete the request safely:" not in text
    assert not app.session_state["conversation"]
    assert len(product_app.runtime.requests) == 1
    assert t(lang, "request_failed") in text
    assert app.error


def test_scope_applies_to_each_request_and_followups_preserve_turns(product_app):
    app = product_app.start()
    text = visible_text(app)
    assert "Phạm vi tra cứu" in text
    assert "nhóm nguồn dùng cho lượt hỏi này" in text
    assert app.session_state["filter_profile"] == "broad"
    app.selectbox(key="scope-profile-landing").set_value("historical").run()
    assert app.session_state["filter_profile"] == "historical"
    submit_landing(app, "Câu hỏi đầu tiên")
    first_turn = app.session_state["conversation"][0]
    assert product_app.runtime.requests[0].filter_profile == "historical"

    app.selectbox(key="scope-profile-followup").set_value("broad").run()
    assert app.session_state["conversation"] == [first_turn]
    app.chat_input[0].set_value("Có ngoại lệ nào?").run()
    assert not app.exception, [item.message for item in app.exception]
    turns = app.session_state["conversation"]
    assert len(turns) == 2 and turns[0] == first_turn
    assert turns[1].turn_id != turns[0].turn_id
    assert [(request.question, request.filter_profile) for request in product_app.runtime.requests] == [
        ("Câu hỏi đầu tiên", "historical"), ("Có ngoại lệ nào?", "broad"),
    ]


@pytest.mark.parametrize("status", ["failed", "blocked", "deferred"])
def test_service_error_responses_do_not_leak_diagnostics(product_app, status):
    product_app.runtime.response_status = status
    app = product_app.start()
    submit_landing(app)
    text = visible_text(app)
    assert "runpod.net" not in text and "HTTP 404" not in text
    assert app.session_state["conversation"][0].response.status == status
    assert app.chat_input


def test_user_settings_stay_visible_and_backend_overrides_apply_without_developer_ui(product_app, monkeypatch):
    monkeypatch.setenv("SHOW_DEVELOPER_UI", "false")
    app = product_app.start()
    assert "Cài đặt dành cho nhà phát triển" not in visible_text(app.sidebar)
    assert "Dense Only" in visible_text(app.sidebar)
    click(app, "choice_retrieval_base_mode_dense_only_option")
    click(app, "choice_graph_enabled_option")
    click(app, "choice_reranker_enabled_option")
    click(app, "choice_prompt_strategy_reasoning_option")
    app.selectbox(key="developer-model-choice").select("gpt-4o").run()
    expected = {
        "retrieval_base_mode": "dense_only", "graph_enabled": "on",
        "reranker_enabled": "on", "prompt_strategy": "reasoning", "model_choice": "gpt-4o",
    }
    app.run()
    app.run()  # A second rerun exercises Streamlit cleanup of widgets that disappeared.
    assert not app.exception, [item.message for item in app.exception]
    assert {key: app.session_state[key] for key in expected} == expected
    assert all(label in visible_text(app.sidebar) for label in ("Dense Only", "Graph", "Reranker", "gpt-4o"))
    assert "fixture-check" not in visible_text(app.sidebar)
    submit_landing(app)
    request = product_app.runtime.requests[-1]
    assert request.sparse_enabled_override is False
    assert request.graph_enabled_override is True and request.fusion_enabled_override is True
    assert request.reranker_enabled_override is True
    assert request.generation_model_override == "gpt-4o"
    assert request.prompt_strategy_override == "reasoning"


def test_citations_actions_and_cards_share_one_viewer_without_losing_state(product_app):
    app = product_app.start(runtime_mode=DEMO_MODE)
    submit_landing(app, "Show a single source example")
    turn = app.session_state["conversation"][0]
    turn_id = turn.turn_id
    citation_key = next(button.key for button in app.button if str(button.key).startswith(f"citation-{turn_id}-1-"))
    click(app, citation_key)
    selection = dict(app.session_state["selected_source"])
    assert selection["turn_id"] == turn_id and selection["citation_id"] == 1
    close_key = f"close-evidence-panel-{turn_id}-1"
    assert app.button(key=close_key)
    text = visible_text(app)
    assert "Đoạn được trích dẫn" in text
    assert all(label not in text for label in ("Source details", "Exact recorded evidence", "Score", "Rank"))

    previous_theme = app.session_state["theme_choice"]
    click(app, "theme-toggle")
    assert app.session_state["theme_choice"] != previous_theme
    assert app.session_state["selected_source"] == selection
    assert app.session_state["conversation"] == [turn]
    app.selectbox(key="preference-language").select("en").run()
    assert not app.exception, [item.message for item in app.exception]
    assert app.session_state["language_choice"] == "en"
    assert app.session_state["selected_source"] == selection
    assert app.session_state["conversation"] == [turn]

    click(app, close_key)
    assert app.session_state["selected_source"] is None
    click(app, f"evidence-answer-{turn_id}")
    assert app.session_state["selected_source"]["citation_id"] == 1
    assert app.button(key=close_key)
    click(app, close_key)
    click(app, f"view-source-tab-{turn_id}-1")
    assert app.session_state["selected_source"]["citation_id"] == 1
    assert app.button(key=close_key)
    assert app.session_state["conversation"] == [turn]
    click(app, close_key)
    click(app, "new-question")
    assert app.session_state["conversation"] == []
    assert app.session_state["selected_source"] is None
    assert app.session_state["language_choice"] == "en"
    assert app.text_area
