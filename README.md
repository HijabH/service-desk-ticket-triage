# Service Desk Ticket Triage

![tests](https://github.com/HijabH/service-desk-ticket-triage/actions/workflows/ci.yml/badge.svg)

A Python REST service that triages IT service desk tickets with a large language model: it sets the category and priority, writes a one-line summary and drafts a first reply to the user. When no LLM is configured, or the LLM call fails, it falls back to keyword rules, so every ticket is still handled.

The goal is a realistic way to bring an LLM into an existing business process: the model does the language work, while the code stays in control of data protection, validation, safety rules and monitoring.

## What it does

- **Classifies tickets** into hardware, software, access, network, email, ERP or other, and sets a priority from P1 to P4
- **Drafts a first reply** in the language of the ticket (German or English)
- **Redacts personal data** (emails, phone numbers, IBANs, IP addresses, passwords) before any text leaves the company
- **Validates the LLM answer** against a strict schema; free text or invented categories are rejected
- **Falls back to keyword rules** when the LLM is unavailable, with one retry on temporary errors
- **Keeps safety rules in code**: outage keywords such as "production down" always mean P1, whatever the model says
- **Sends unclear cases to a person**: low confidence, P1 or "other" tickets are flagged `needs_human`
- **Reports metrics**: tickets handled, LLM versus rules, failures, categories and average response time

```text
ticket ──> redact personal data ──> LLM (strict JSON) ──valid──> safety rules ──> result
                                        │                                           ^
                                        └── error / invalid answer ──> keyword rules┘
```

## Quick start

```bash
pip install -r requirements-dev.txt

# try it on the sample tickets (keyword rules, no API key needed)
python -m triage.cli samples/tickets.json

# run the API
uvicorn triage.api:app --reload
# then open http://127.0.0.1:8000/docs
```

To use the LLM, set an Anthropic API key (see `.env.example`):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TRIAGE_MODEL=claude-haiku-5-5
```

Or with Docker:

```bash
docker build -t ticket-triage .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY ticket-triage
```

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/triage` | Triage one ticket |
| `POST` | `/triage/batch` | Triage a list of tickets |
| `GET` | `/metrics` | Counters and average response time |
| `GET` | `/health` | Status and mode (`llm` or `rules`) |

```bash
curl -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" \
  -d '{"subject": "VPN does not connect", "body": "Authentication failed from home office"}'
```

```json
{
  "category": "network",
  "priority": "P3",
  "summary": "VPN does not connect",
  "suggested_reply": "Thanks, we are checking the connection problem. ...",
  "needs_human": false,
  "source": "rules",
  "reasons": ["keyword match: network"]
}
```

## Example run (keyword rules)

```text
[P3] access    Account locked after password change                    (rules)
[P1] erp       Produktion steht - SAP Auftrag kann nicht gebucht werde (rules)  -> needs human
[P3] hardware  Printer on 2nd floor not printing                       (rules)
[P3] network   VPN does not connect from home                          (rules)
[P3] email     Outlook calendar not syncing with Teams                 (rules)
[P4] access    New employee starting Monday                            (rules)
[P3] software  Excel crashes when opening large file                   (rules)
[P3] other     Coffee machine broken                                   (rules)  -> needs human
```

## Tests

```bash
pytest
```

34 tests cover the keyword rules, redaction, parsing and validation of LLM answers, retries, the fallback, the P1 safety rule, the confidence threshold and the API. The LLM is replaced with `httpx.MockTransport`, so the tests never call the real API. GitHub Actions runs them on every push.

## Possible next steps

- Connect to a real ticket system (for example the Jira Service Management or ServiceNow API) instead of the REST endpoint
- Send P1 tickets to a Microsoft Teams channel through an incoming webhook
- Collect agent corrections to measure and improve accuracy over time

## License

[MIT](LICENSE)
