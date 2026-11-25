"""Triage a JSON file of tickets from the command line.

python -m triage.cli samples/tickets.json
"""

import json
import sys
from pathlib import Path

from .api import build_service
from .models import Ticket


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Usage: python -m triage.cli <tickets.json>")
        return 2

    tickets = [Ticket.model_validate(t) for t in json.loads(Path(argv[0]).read_text(encoding="utf-8"))]
    service = build_service()

    for ticket in tickets:
        r = service.triage(ticket)
        flag = "  -> needs human" if r.needs_human else ""
        print(f"[{r.priority.value}] {r.category.value:<9} {ticket.subject[:55]:<55} ({r.source}){flag}")

    print(f"\n{json.dumps(service.metrics.as_dict(), indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
