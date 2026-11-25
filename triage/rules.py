"""Keyword rules: the fallback when no LLM is configured or the LLM call fails.

They are deliberately simple and predictable. The LLM handles the nuance;
the rules make sure every ticket still gets a sensible category and priority.
"""

from .models import Category, Priority, Ticket, TriageResult

_CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.ACCESS: ["password", "passwort", "locked", "gesperrt", "login", "anmelden", "permission",
                      "berechtigung", "access", "zugriff", "mfa", "2fa", "account"],
    Category.EMAIL: ["outlook", "email", "e-mail", "mailbox", "postfach", "teams", "calendar", "kalender"],
    Category.NETWORK: ["vpn", "wifi", "wlan", "network", "netzwerk", "internet", "lan", "dns"],
    Category.ERP: ["sap", "erp", "order", "auftrag", "invoice", "rechnung", "material"],
    Category.HARDWARE: ["laptop", "printer", "drucker", "monitor", "keyboard", "tastatur", "mouse",
                        "maus", "docking", "screen", "bildschirm", "headset", "phone"],
    Category.SOFTWARE: ["install", "update", "excel", "word", "license", "lizenz", "crash", "absturz",
                        "application", "programm", "software"],
}

_P1_KEYWORDS = ["production down", "produktion steht", "everyone", "alle mitarbeiter", "all users",
                "outage", "ausfall", "server down", "ransomware", "virus"]
_P2_KEYWORDS = ["urgent", "dringend", "asap", "sofort", "cannot work", "kann nicht arbeiten",
                "blocked", "whole team", "ganze team", "abteilung", "customer", "kunde"]
_REQUEST_KEYWORDS = ["request", "anfrage", "please order", "bitte bestellen", "new employee",
                     "neuer mitarbeiter", "question", "frage", "how do i", "wie kann ich"]

_REPLIES: dict[Category, str] = {
    Category.ACCESS: "Thanks, we have your access request. We will check your account and get back to you shortly.",
    Category.EMAIL: "Thanks, we are looking into the Outlook/Teams issue. Please let us know if the error message changes.",
    Category.NETWORK: "Thanks, we are checking the connection problem. Please tell us your location and whether a cable connection works.",
    Category.ERP: "Thanks, we have forwarded this to the ERP team. Please send the transaction or document number if you have it.",
    Category.HARDWARE: "Thanks, we have your hardware request. Please let us know the device's inventory number.",
    Category.SOFTWARE: "Thanks, we are looking into the software issue. A screenshot of the error message would help.",
    Category.OTHER: "Thanks for your message. A colleague from IT will take a look and get back to you.",
}


def _score(text: str, keywords: list[str]) -> int:
    return sum(1 for k in keywords if k in text)


def is_p1(text: str) -> bool:
    return _score(text.lower(), _P1_KEYWORDS) > 0


def classify(ticket: Ticket) -> TriageResult:
    text = f"{ticket.subject} {ticket.body}".lower()

    scores = {cat: _score(text, words) for cat, words in _CATEGORY_KEYWORDS.items()}
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    category = best if best_score > 0 else Category.OTHER

    if is_p1(text):
        priority = Priority.P1
    elif _score(text, _P2_KEYWORDS) > 0:
        priority = Priority.P2
    elif _score(text, _REQUEST_KEYWORDS) > 0:
        priority = Priority.P4
    else:
        priority = Priority.P3

    reasons = [f"keyword match: {category.value}" if best_score else "no category keywords matched"]
    return TriageResult(
        category=category,
        priority=priority,
        summary=ticket.subject[:300],
        suggested_reply=_REPLIES[category],
        needs_human=category == Category.OTHER or priority == Priority.P1,
        source="rules",
        reasons=reasons,
    )
