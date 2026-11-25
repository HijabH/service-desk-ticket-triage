import json

import httpx
import pytest

from triage.llm import LlmClassifier, LlmError, parse_response
from triage.models import Category, Priority, Ticket
from triage.service import TriageService


def api_answer(obj: dict | str) -> dict:
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return {"content": [{"type": "text", "text": text}]}


GOOD = {"category": "access", "priority": "P3", "summary": "User locked out after password change.",
        "suggested_reply": "We will unlock your account.", "confidence": 0.92}


def classifier(handler) -> tuple[LlmClassifier, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return LlmClassifier(api_key="test-key", model="test-model", client=client), seen


# --- parsing -----------------------------------------------------------------

def test_parses_a_valid_answer():
    result = parse_response(api_answer(GOOD))
    assert result.category == Category.ACCESS
    assert result.confidence == pytest.approx(0.92)


def test_accepts_json_inside_a_code_fence():
    assert parse_response(api_answer("```json\n" + json.dumps(GOOD) + "\n```")).priority == Priority.P3


@pytest.mark.parametrize("bad", [
    "I think this is an access problem.",
    json.dumps({**GOOD, "category": "coffee"}),
    json.dumps({**GOOD, "confidence": 3}),
    json.dumps({k: v for k, v in GOOD.items() if k != "priority"}),
])
def test_rejects_answers_that_do_not_match_the_format(bad):
    with pytest.raises(LlmError):
        parse_response(api_answer(bad))


# --- HTTP behaviour ----------------------------------------------------------

def test_sends_the_ticket_with_the_right_headers():
    llm, seen = classifier(lambda r: httpx.Response(200, json=api_answer(GOOD)))

    llm.classify("Account locked", "after password change")

    request = seen[0]
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == "2023-06-01"
    body = json.loads(request.content)
    assert body["model"] == "test-model"
    assert "Account locked" in body["messages"][0]["content"]


def test_retries_once_on_a_temporary_error():
    responses = iter([httpx.Response(529, text="overloaded"), httpx.Response(200, json=api_answer(GOOD))])
    llm, seen = classifier(lambda r: next(responses))

    assert llm.classify("x", "y").category == Category.ACCESS
    assert len(seen) == 2


def test_does_not_retry_a_permanent_error():
    llm, seen = classifier(lambda r: httpx.Response(401, text="invalid key"))

    with pytest.raises(LlmError, match="401"):
        llm.classify("x", "y")
    assert len(seen) == 1


# --- service -----------------------------------------------------------------

def test_service_uses_the_llm_answer_and_redacts_first():
    llm, seen = classifier(lambda r: httpx.Response(200, json=api_answer(GOOD)))
    service = TriageService(llm)

    result = service.triage(Ticket(subject="Locked out", body="Reach me at max@example.com"))

    assert result.source == "llm"
    assert result.category == Category.ACCESS
    assert not result.needs_human
    assert "max@example.com" not in seen[0].content.decode()
    assert any("redacted" in r for r in result.reasons)


def test_service_falls_back_to_rules_when_the_llm_fails():
    llm, _ = classifier(lambda r: httpx.Response(500, text="boom"))
    service = TriageService(llm)

    result = service.triage(Ticket(subject="VPN does not connect"))

    assert result.source == "rules"
    assert result.category == Category.NETWORK
    assert service.metrics.llm_failures == 1


def test_outage_keywords_force_p1_even_if_the_llm_disagrees():
    llm, _ = classifier(lambda r: httpx.Response(200, json=api_answer({**GOOD, "category": "erp", "priority": "P3"})))

    result = TriageService(llm).triage(Ticket(subject="Production down", body="SAP orders fail for all users"))

    assert result.priority == Priority.P1
    assert result.needs_human


def test_low_confidence_answers_go_to_a_human():
    llm, _ = classifier(lambda r: httpx.Response(200, json=api_answer({**GOOD, "confidence": 0.4})))

    assert TriageService(llm).triage(Ticket(subject="Something odd")).needs_human


def test_metrics_count_sources_and_categories():
    service = TriageService()
    service.triage(Ticket(subject="VPN broken"))
    service.triage(Ticket(subject="Printer jam"))

    m = service.metrics.as_dict()
    assert m["tickets_triaged"] == 2
    assert m["by_source"] == {"rules": 2}
    assert m["by_category"] == {"network": 1, "hardware": 1}
