"""
Workflow 13: MCP Tool Behind a Human Gate
─────────────────────────────────────────
A2A_START ─▶ ORCHESTRATOR_AGENT ─▶ END
                    ▲
                    │ tools
              TOOL (price_quote, require_confirmation)

The agent decides *when* to call the MCP tool; a person decides *whether* it
may. Tick **Ask a human first** on the tool and the run stops the moment the
model tries to use it, naming the exact call it wants to make, and does not
send the MCP request until someone approves.

This is a different kind of human-in-the-loop from a HUMAN_APPROVAL node. That
one is a step you place: the flow always reaches it, at a point you chose. This
one is a *guard on a capability*: the model picks the moment, which is the only
way to gate a tool an agent calls on its own initiative. Both park the A2A task
at `input-required`, so both are answered the same way.

How it works, measured rather than assumed:

  * the generated tool is `FunctionTool(..., require_confirmation=True)`. ADK
    turns the pending call into an `adk_request_confirmation` long-running
    function call carrying `originalFunctionCall`, and the A2A layer reports
    long-running calls as `input-required`;
  * the agent runs via `ctx.run_node`, as a child of the graph node, so that
    interrupt reaches the workflow. Run in its own nested `Runner` — which is
    what the agent node used to do — the confirmation event is produced and
    then dropped, and the task completes as though the human had approved;
  * a node that calls `ctx.run_node` must be `rerun_on_resume=True`, or ADK
    fails the run outright: the workflow wakes the parent node up to collect
    the child's answer.

Approve, and the MCP tool runs and its result comes back. Reject, and the model
is told `{"error": "This tool call is rejected."}` and the MCP server is never
contacted.

Needs a model (the agent has to decide to call the tool) and an MCP server:

    python backend/tests/support/demo_mcp_server.py 8000 0.0.0.0

Try it:

    python run_once.py '{"request": "quote me 2 widgets"}' --mode task
    → task parks at input-required
    python run_once.py --task <task-id>        # see what it is asking
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"
# host.docker.internal: the platform packages and runs this inside a container,
# where `localhost` is the backend itself. See seed_mcp_tool.py.
MCP_URL = "http://host.docker.internal:8000/mcp"


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


def _edge(edge_id, source, target, source_handle="output", target_handle="input"):
    return {
        "id": edge_id,
        "source": source,
        "source_handle": source_handle,
        "target": target,
        "target_handle": target_handle,
        "condition": None,
    }


CANVAS = {
    "schema_version": 7,
    "nodes": [
        _node("trigger", "A2A_START", "Request", {
            "input_mode": "json",
            "state_key": "wf",
            "payload_schema": {"fields": [
                {"name": "request", "type": "string",
                 "description": "What to ask the agent for", "required": True},
            ]},
        }, 40, 240),

        _node("agent", "ORCHESTRATOR_AGENT", "Buyer Agent", {
            "model": "gemini-2.0-flash",
            "instruction": (
                "You quote prices. Use the price quote tool when asked for a "
                "price. Report exactly what it returns."
            ),
        }, 480, 240),

        # Wired into the agent's `tools` handle, not into the flow: the agent
        # calls it, the flow does not pass through it.
        _node("quote_tool", "TOOL", "Price Quote (needs approval)", {
            "mcp_url": MCP_URL,
            "tool_name": "price_quote",
            # The one line this workflow is about.
            "require_confirmation": True,
        }, 480, 480),

        _node("done", "END", "Done", {"output_mapping": {}}, 920, 240),
    ],
    "edges": [
        _edge("e1", "trigger", "agent"),
        _edge("e2", "quote_tool", "agent", "output", "tools"),
        _edge("e3", "agent", "done"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "MCP Tool Behind a Human Gate",
            "description": (
                "An agent may call an MCP tool, but only once a person has "
                "approved the specific call."
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
