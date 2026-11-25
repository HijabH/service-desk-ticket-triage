"""Ties redaction, the LLM, the rule fallback and the safety checks together."""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field

from . import rules
from .llm import LlmClassifier, LlmError
from .models import Category, Priority, Ticket, TriageResult
from .redaction import redact

log = logging.getLogger(__name__)

# Below this confidence a person checks the LLM's answer before the reply goes out.
CONFIDENCE_THRESHOLD = 0.7


@dataclass
class Metrics:
    total: int = 0
    by_source: Counter = field(default_factory=Counter)
    by_category: Counter = field(default_factory=Counter)
    llm_failures: int = 0
    total_ms: float = 0.0

    def as_dict(self) -> dict:
        return {
            "tickets_triaged": self.total,
            "by_source": dict(self.by_source),
            "by_category": dict(self.by_category),
            "llm_failures": self.llm_failures,
            "average_ms": round(self.total_ms / self.total, 1) if self.total else 0.0,
        }


class TriageService:
    def __init__(self, llm: LlmClassifier | None = None):
        self._llm = llm
        self.metrics = Metrics()

    def triage(self, ticket: Ticket) -> TriageResult:
        started = time.perf_counter()
        result = self._triage(ticket)
        self.metrics.total += 1
        self.metrics.by_source[result.source] += 1
        self.metrics.by_category[result.category.value] += 1
        self.metrics.total_ms += (time.perf_counter() - started) * 1000
        return result

    def _triage(self, ticket: Ticket) -> TriageResult:
        if self._llm is None:
            return rules.classify(ticket)

        subject, removed_subject = redact(ticket.subject)
        body, removed_body = redact(ticket.body)
        removed = sorted(set(removed_subject + removed_body))

        try:
            answer = self._llm.classify(subject, body)
        except LlmError as error:
            self.metrics.llm_failures += 1
            log.warning("falling back to rules: %s", error)
            result = rules.classify(ticket)
            result.reasons.append("LLM unavailable, used keyword rules")
            return result

        reasons = [f"LLM confidence {answer.confidence:.2f}"]
        if removed:
            reasons.append(f"redacted before sending: {', '.join(removed)}")

        priority = answer.priority
        # safety net: outage keywords always mean P1, whatever the model says
        if rules.is_p1(f"{ticket.subject} {ticket.body}") and priority != Priority.P1:
            priority = Priority.P1
            reasons.append("raised to P1 by outage keyword rule")

        needs_human = (
            answer.confidence < CONFIDENCE_THRESHOLD
            or priority == Priority.P1
            or answer.category == Category.OTHER
        )
        return TriageResult(
            category=answer.category,
            priority=priority,
            summary=answer.summary,
            suggested_reply=answer.suggested_reply,
            needs_human=needs_human,
            source="llm",
            reasons=reasons,
        )
