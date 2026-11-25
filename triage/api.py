"""REST API for the triage service.

Run with:  uvicorn triage.api:app --reload
"""

import logging
import os

from fastapi import FastAPI

from .llm import LlmClassifier
from .models import Ticket, TriageResult
from .service import TriageService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def build_service() -> TriageService:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logging.getLogger(__name__).info("ANTHROPIC_API_KEY not set: using keyword rules only")
        return TriageService()
    model = os.getenv("TRIAGE_MODEL", "claude-haiku-5-5")
    return TriageService(LlmClassifier(api_key=api_key, model=model))


app = FastAPI(title="Service Desk Ticket Triage", version="1.0.0")
service = build_service()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "llm" if service._llm else "rules"}


@app.post("/triage", response_model=TriageResult)
def triage(ticket: Ticket) -> TriageResult:
    return service.triage(ticket)


@app.post("/triage/batch", response_model=list[TriageResult])
def triage_batch(tickets: list[Ticket]) -> list[TriageResult]:
    return [service.triage(t) for t in tickets]


@app.get("/metrics")
def metrics() -> dict:
    return service.metrics.as_dict()
