"""Classifies a ticket with an LLM through the Anthropic Messages API.

Uses plain httpx instead of an SDK so the request and the error handling are visible.
The model must answer with JSON that matches LlmTriage; anything else is rejected
and the caller falls back to the keyword rules.
"""

import json
import logging

import httpx
from pydantic import ValidationError

from .models import LlmTriage

log = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You triage IT service desk tickets for a manufacturing company.
Reply with one JSON object and nothing else, with exactly these keys:
  "category": one of "hardware", "software", "access", "network", "email", "erp", "other"
  "priority": one of "P1", "P2", "P3", "P4"
     P1 = business stopped or many users affected, P2 = a team blocked or critical system degraded,
     P3 = one user affected, P4 = a request or question
  "summary": one sentence in English, at most 25 words
  "suggested_reply": a short, friendly first reply to the requester, in the language of the ticket
  "confidence": a number from 0 to 1
Personal data in the ticket has been replaced with placeholders such as [EMAIL]; never invent it."""


class LlmError(Exception):
    """Raised when the LLM cannot give a usable answer."""


class LlmClassifier:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None,
                 timeout: float = 20.0, max_attempts: int = 2):
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)
        self._max_attempts = max_attempts

    def classify(self, subject: str, body: str) -> LlmTriage:
        payload = {
            "model": self._model,
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": f"Subject: {subject}\n\n{body}"}],
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = self._client.post(API_URL, json=payload, headers=headers)
                if response.status_code in (429, 500, 502, 503, 529):
                    raise LlmError(f"temporary API error HTTP {response.status_code}")
                if response.status_code != 200:
                    raise LlmError(f"API error HTTP {response.status_code}: {response.text[:200]}")
                return parse_response(response.json())
            except (httpx.HTTPError, LlmError) as error:
                last_error = error
                log.warning("LLM attempt %d/%d failed: %s", attempt, self._max_attempts, error)
                if isinstance(error, LlmError) and "temporary" not in str(error):
                    break  # permanent errors and bad answers are not retried

        raise LlmError(str(last_error))


def parse_response(data: dict) -> LlmTriage:
    """Extracts and validates the JSON object from a Messages API response."""
    try:
        text = "".join(block["text"] for block in data["content"] if block.get("type") == "text")
    except (KeyError, TypeError) as error:
        raise LlmError(f"unexpected response shape: {error}") from error

    # tolerate a markdown code fence around the JSON
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LlmError("no JSON object in the answer")

    try:
        return LlmTriage.model_validate(json.loads(text[start:end + 1]))
    except (json.JSONDecodeError, ValidationError) as error:
        raise LlmError(f"answer did not match the expected format: {error}") from error
