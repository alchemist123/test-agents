"""
Workflow 6: Sub-agents
──────────────────────
A2A_START → ORCHESTRATOR_AGENT → END

with two LLM_AGENT nodes used as sub-agents rather than as flow nodes:

    [weather MCP tool] ─tools─> [LLM Agent "trip_planner"] ─┐
                                                             ├─tools─> [ORCHESTRATOR]
    [LLM Agent "editor"] ─tools─> [SEQUENTIAL_AGENT "polish"]┘
    [grammar MCP tool]  ─tools─┘

`trip_planner` is attached straight to the orchestrator, so ADK exposes it as a
tool via `sub_agents` with `mode='single_turn'`. `editor` sits inside a
sequential group, so the group drives it through its own Runner.

Both declare an input structure — which is what the calling model's tool
parameters are built from — and an output structure, which constrains the reply
to a named shape.

Tests: LLM_AGENT as a sub-agent in both positions, a sub-agent with its own MCP
tool, and ADK input_schema / output_schema round-tripping from the canvas.
"""
import sys

import httpx

BASE = "http://localhost:8001/api/v1"


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


def _edge(edge_id, source, target, target_handle="input"):
    return {
        "id": edge_id,
        "source": source,
        "source_handle": "output",
        "target": target,
        "target_handle": target_handle,
        "condition": None,
    }


def _fields(*specs):
    return {
        "fields": [
            {
                "name": name,
                "type": field_type,
                "description": description,
                "required": required,
            }
            for name, field_type, description, required in specs
        ]
    }


CANVAS = {
    # No schema_version: the backend stamps the current one, so a seed
    # cannot be stranded on an old version by a later migration.
    "nodes": [
        _node("trigger", "A2A_START", "A2A Start", {
            "input_mode": "json",
            "state_key": "wf",
            "payload_schema": _fields(
                ("request", "text", "What the user wants planned or written", True),
            ),
        }, 40, 40),

        _node("orchestrator", "ORCHESTRATOR_AGENT", "Orchestrator", {
            "model": "gemini-2.5-flash",
            "system_prompt": (
                "Answer the user's request. You can call a trip planner and a "
                "polish pipeline. Pass them proper arguments — they declare "
                "what they need."
            ),
        }, 1240, 40),

        # ── Sub-agent attached straight to the orchestrator ──────────────────
        # ADK exposes this via sub_agents with mode='single_turn'.
        _node("planner", "LLM_AGENT", "Trip Planner", {
            "provider": "vertex_ai",
            "model": "gemini-2.5-flash",
            "name": "trip_planner",
            "description": "Plans a short trip for a city and a number of days.",
            "system_prompt": (
                "Plan a trip. Use the weather tool before recommending outdoor "
                "activities."
            ),
            "input_structure": _fields(
                ("city", "string", "Destination city", True),
                ("days", "integer", "Trip length in days", True),
                ("interests", "string", "What the traveller enjoys", False),
            ),
            "output_structure": _fields(
                ("itinerary", "text", "Day-by-day plan", True),
                ("packing_list", "array", "What to bring", False),
            ),
            "output_key": "trip",
        }, 640, 300),
        _node("weather", "TOOL", "Weather MCP", {
            "mcp_url": "http://host.docker.internal:9001/mcp",
            "tool_name": "get_forecast",
        }, 40, 300),

        # ── Sub-agent inside a sequential group ──────────────────────────────
        # A group's members are tools, so this one runs through its own Runner.
        _node("polish", "SEQUENTIAL_AGENT", "Polish Pipeline", {
            "name": "polish_text",
            "description": "Check grammar, then rewrite the text in a house style.",
            "order": ["grammar", "editor"],
            "stop_on_error": True,
        }, 640, 700),
        _node("grammar", "TOOL", "Grammar MCP", {
            "mcp_url": "http://host.docker.internal:9002/mcp",
            "tool_name": "check_grammar",
        }, 40, 700),
        _node("editor", "LLM_AGENT", "Editor", {
            "provider": "vertex_ai",
            "model": "gemini-2.5-flash",
            "name": "editor",
            "description": "Rewrites text in a consistent house style.",
            "system_prompt": "Rewrite the text clearly and concisely.",
            "input_structure": _fields(
                ("text", "text", "The text to rewrite", True),
                ("style", "string", "House style to apply", False),
            ),
            "output_structure": _fields(
                ("rewritten", "text", "The rewritten text", True),
            ),
        }, 40, 1000),

        _node("end", "END", "End", {"output_mapping": {"result": "answer"}}, 1860, 40),
    ],
    "edges": [
        _edge("f1", "trigger", "orchestrator"),
        _edge("f2", "orchestrator", "end"),

        # trip_planner -> orchestrator, with its own MCP tool
        _edge("t1", "weather", "planner", "tools"),
        _edge("t2", "planner", "orchestrator", "tools"),

        # grammar + editor -> sequential group -> orchestrator
        _edge("t3", "grammar", "polish", "tools"),
        _edge("t4", "editor", "polish", "tools"),
        _edge("t5", "polish", "orchestrator", "tools"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Sub Agents",
            "description": "LLM agents used as sub-agents, with declared input and output structures.",
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
