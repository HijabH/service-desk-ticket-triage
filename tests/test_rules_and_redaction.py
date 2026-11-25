import pytest

from triage import rules
from triage.models import Category, Priority, Ticket
from triage.redaction import redact


@pytest.mark.parametrize("subject, body, category", [
    ("Account locked", "I cannot log in after the password change", Category.ACCESS),
    ("Outlook keeps asking for credentials", "", Category.EMAIL),
    ("VPN does not connect", "from home office", Category.NETWORK),
    ("SAP Auftrag", "Rechnung kann nicht gebucht werden", Category.ERP),
    ("Printer jam", "the printer on floor 2", Category.HARDWARE),
    ("Excel crashes", "when opening a large file", Category.SOFTWARE),
    ("Coffee machine broken", "shows an error", Category.OTHER),
])
def test_rules_pick_the_category_from_keywords(subject, body, category):
    assert rules.classify(Ticket(subject=subject, body=body)).category == category


@pytest.mark.parametrize("text, priority", [
    ("Production down, all users affected", Priority.P1),
    ("Produktion steht seit 7 Uhr", Priority.P1),
    ("Urgent: I cannot work", Priority.P2),
    ("Printer shows paper jam", Priority.P3),
    ("Request: please order a new headset", Priority.P4),
])
def test_rules_set_priority(text, priority):
    assert rules.classify(Ticket(subject=text)).priority == priority


def test_rules_send_p1_and_unknown_tickets_to_a_human():
    assert rules.classify(Ticket(subject="Server down for everyone")).needs_human
    assert rules.classify(Ticket(subject="Coffee machine broken")).needs_human
    assert not rules.classify(Ticket(subject="Printer jam")).needs_human


def test_rules_result_is_marked_as_rules():
    result = rules.classify(Ticket(subject="VPN"))
    assert result.source == "rules"
    assert result.suggested_reply


def test_redaction_removes_personal_and_secret_data():
    text = ("Mail me at anna.schmidt@example.com or call +49 151 2345678. "
            "Server 10.0.0.12, password: Sommer2026! IBAN DE89 3704 0044 0532 0130 00")

    redacted, removed = redact(text)

    assert "anna.schmidt" not in redacted
    assert "2345678" not in redacted
    assert "10.0.0.12" not in redacted
    assert "Sommer2026" not in redacted
    assert "DE89" not in redacted
    assert set(removed) == {"email", "phone", "ip", "password", "iban"}


def test_redaction_leaves_normal_text_alone():
    text = "Excel crashes when I open the monthly report from 2026"
    assert redact(text) == (text, [])
