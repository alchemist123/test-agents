"""
Workflow 7: Human in the loop
─────────────────────────────
A2A_START → CONDITION → [small] ─────────────────────────────→ TRANSFORM (auto) ─┐
                      → [large] → HUMAN_APPROVAL                                 │
                                    ─approved→ HUMAN_INPUT → TRANSFORM (paid) ───┼→ END
                                    ─rejected→ TRANSFORM (declined) ─────────────┘

All three things a person can be asked for, in one workflow:

  * **approve**  — the gate's `approved` route
  * **reject**   — its `rejected` route
  * **give input** — HUMAN_INPUT collects values the workflow cannot work out
    for itself, then carries on

Anything under the threshold goes straight through; anything over parks the A2A
task at `input-required` until a person answers.

How the pause works — all of it is ADK and A2A, none of it is ours:

  * the node returns a `RequestInput`, which ADK turns into an interrupt event
  * `to_a2a` reports the task as **input-required**, carrying the question and
    a JSON Schema for the answer
  * the caller resumes by sending `message/send` with the *same taskId* and a
    data part tagged `adk_type: function_response`
  * the node runs again and reads the answer from `ctx.resume_inputs`

Try it from the generated package, which does the whole handshake for you:

    python run_once.py '{"amount": 5000, "reason": "new laptops"}'
        -> WAITING  state=input-required, and it prints what to answer

    python run_once.py '{"amount": 5000, "reason": "new laptops"}' \\
        --answer '{"approved": true, "comment": "ok", "cost_centre": "ENG-1"}'
        -> pauses again, this time for the payment details

    # answer the second pause with --resume, which continues the live task
    python run_once.py --resume <task-id> --context <context-id> \\
        --interrupt <interrupt-id> \\
        --answer '{"account": "GBP-CURRENT", "pay_on": "2026-10-01"}'
        -> completed, outcome "paid"

    python run_once.py '{"amount": 20, "reason": "coffee"}'
        -> completed straight away; the gate is never reached

Runs entirely offline: no model, no MCP server, no credentials.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"

# Anything at or above this needs a person.
THRESHOLD = 1000


def _node(node_id, node_type, title, config, x, y):
    return {
        "id": node_id,
        "type": node_type,
        "version": "1",
        "position": {"x": x, "y": y},
        "metadata": {"title": title, "description": ""},
        "config": config,
        "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
        "policies": {"timeout_seconds": 120, "retry": {"max_attempts": 1}, "on_error": "fail"},
    }


def _edge(edge_id, source, target, source_handle="output"):
    return {
        "id": edge_id,
        "source": source,
        "source_handle": source_handle,
        "target": target,
        "target_handle": "input",
        "condition": None,
    }


CANVAS = {
    "schema_version": 6,
    "nodes": [
        _node("trigger", "A2A_START", "Expense Request", {
            "input_mode": "json",
            "state_key": "wf",
            "payload_schema": {"fields": [
                {"name": "amount", "type": "number",
                 "description": "Amount being claimed", "required": True},
                {"name": "reason", "type": "text",
                 "description": "What the money is for", "required": True},
            ]},
        }, 40, 260),

        _node("size", "CONDITION", "Needs approval?", {
            "branches": [
                {"name": "large", "expression": f"data.get('amount', 0) >= {THRESHOLD}"},
                {"name": "small", "expression": "True"},
            ],
        }, 520, 260),

        _node("gate", "HUMAN_APPROVAL", "Finance Sign-off", {
            "prompt": (
                "This expense is over the auto-approval limit. Approve it?"
            ),
            "assignees": ["finance@example.com"],
            # Asked for alongside approved/comment, and advertised on the
            # paused task so a client can build a form from it.
            "collect_fields": {"fields": [
                {"name": "cost_centre", "type": "string",
                 "description": "Which cost centre to charge", "required": True},
            ]},
        }, 1000, 120),

        # Approved, but the workflow still needs details only a person has.
        # A second pause, of the other kind: values, not a decision.
        _node("details", "HUMAN_INPUT", "Payment Details", {
            "prompt": "Approved. Where should this be paid from, and when?",
            "assignees": ["accounts@example.com"],
            "collect_fields": {"fields": [
                {"name": "account", "type": "string",
                 "description": "Account to pay from", "required": True},
                {"name": "pay_on", "type": "string",
                 "description": "Date to pay (YYYY-MM-DD)", "required": True},
                {"name": "note", "type": "text",
                 "description": "Anything the payment run should know",
                 "required": False},
            ]},
        }, 1480, 40),

        _node("paid", "TRANSFORM", "Record Payment", {
            "mode": "python",
            "expression": (
                "result = {'outcome': 'paid', "
                "'cost_centre': data.get('cost_centre'), "
                "'account': data.get('account'), "
                "'pay_on': data.get('pay_on'), "
                "'approved_by': 'finance'}"
            ),
        }, 1960, 40),
        _node("declined", "TRANSFORM", "Record Decline", {
            "mode": "python",
            "expression": (
                "result = {'outcome': 'declined', 'why': data.get('comment')}"
            ),
        }, 1480, 300),
        _node("auto", "TRANSFORM", "Auto-approve", {
            "mode": "python",
            "expression": "result = {'outcome': 'paid', 'approved_by': 'policy'}",
        }, 1000, 480),

        _node("end", "END", "End", {"output_mapping": {}}, 1960, 300),
    ],
    "edges": [
        _edge("e1", "trigger", "size"),
        _edge("e2", "size", "gate", "large"),
        _edge("e3", "size", "auto", "small"),
        # Both decisions must be wired, or one of them would have nowhere to go.
        _edge("e4", "gate", "details", "approved"),
        _edge("e9", "details", "paid"),
        _edge("e5", "gate", "declined", "rejected"),
        _edge("e6", "paid", "end"),
        _edge("e7", "declined", "end"),
        _edge("e8", "auto", "end"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Human In The Loop",
            "description": (
                "Approve, reject, or supply values — an expense gate followed "
                "by an input request, both pausing the A2A task."
            ),
        })
        r.raise_for_status()
        workflow_id = r.json()["id"]
        print(f"Created workflow: {workflow_id}")

        r = client.post(f"{BASE}/workflows/{workflow_id}/versions", json={"canvas": CANVAS})
        r.raise_for_status()
        result = r.json()
        if result["is_valid"]:
            print(f"✓ Compiled successfully — version {result['version_id']}")
        else:
            print(f"✗ Validation errors: {result['errors']}", file=sys.stderr)
        for warning in result.get("warnings") or []:
            print(f"  ! {warning}")
        return workflow_id


if __name__ == "__main__":
    seed()
