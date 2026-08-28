"""Generate the checks-only example bundle.

A team running a PII gate and a jailbreak gate, with no rate card, no baseline
and no policy. This is the case the README describes: asking what your harness
cannot tell you without first inventing economics you do not have.

Every model call carries its real token counts and states no cost, because
nothing priced them. Writing `direct_cost_usd: 0.0` here would be a fabricated
measurement, and a bundle whose whole purpose is declaring absent economics is
the last place to invent one.

Run `make checks-only` to regenerate and byte-compare against the committed
artifact.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agent_economics.adapters import render_normalized_json
from agent_economics.models import Outcome, TraceEvent
from agent_economics.unsupplied import checks_only_bundle

TASKS = (
    ("redact-support-ticket", True, 1_842, 274),
    ("summarise-incident", True, 3_210, 512),
    ("answer-billing-question", False, 964, 188),
    ("classify-abuse-report", True, 1_405, 96),
)


def build():
    events, outcomes = [], {}
    for index, (task_id, acceptable, input_tokens, output_tokens) in enumerate(TASKS):
        events.append(
            TraceEvent(
                task_id=task_id,
                event_id=f"call-{index:02d}",
                timestamp=f"2026-08-27T09:{index:02d}:00Z",
                event_type="model",
                name="completion",
                model="claude-opus-4",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                # No direct_cost_usd. Nothing priced this call.
            )
        )
        outcomes[task_id] = Outcome(task_id=task_id, acceptable=acceptable)
    return checks_only_bundle(
        events=tuple(events),
        outcomes=outcomes,
        source_id="example.checks-only",
    )


if __name__ == "__main__":
    destination = sys.argv[1] if len(sys.argv) > 1 else None
    document = render_normalized_json(build())
    if destination:
        pathlib.Path(destination).write_text(document, encoding="utf-8")
    else:
        sys.stdout.write(document)
