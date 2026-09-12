"""
Workflow 5: Tool Groups
───────────────────────
A2A_START → ORCHESTRATOR_AGENT → END

with the agent's tools arranged into two groups:

    [diet-advisor]     ─┐
    [sentiment]        ─┴─tools─> [PARALLEL_AGENT "compare"]    ─┐
                                                                 ├─tools─> [ORCHESTRATOR_AGENT]
    [text-summarizer]  ─┐                                        │
    [calculator]       ─┴─tools─> [SEQUENTIAL_AGENT "pipeline"] ─┘

The parallel group asks two agents the same question at once. The sequential
group runs the summarizer and then the calculator, so the second sees the
first's output.

Tests: SEQUENTIAL_AGENT / PARALLEL_AGENT resolution, execution order, and an
agent that sees two composite tools rather than four separate ones.
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


def _remote(node_id, title, name, port, description, x, y):
    return _node(
        node_id, "REMOTE_AGENT", title,
        {
            "name": name,
            "endpoint": f"http://host.docker.internal:{port}",
            "description": description,
        },
        x, y,
    )


CANVAS = {
    "nodes": [
        _node("trigger", "A2A_START", "A2A Start", {
            "input_mode": "json",
            "state_key": "wf",
            "payload_schema": {"fields": [
                {"name": "message", "type": "text",
                 "description": "The question to answer", "required": True},
            ]},
        }, 40, 40),

        _node("orchestrator", "ORCHESTRATOR_AGENT", "Orchestrator", {
            "model": "gemini-2.5-flash",
            "system_prompt": (
                "Answer the user's question. You have two composite tools: one "
                "asks several advisors at once, the other runs a summarise-then-"
                "calculate pipeline. Pick whichever fits."
            ),
        }, 1240, 40),

        # Parallel group: two independent opinions on the same question.
        _node("compare", "PARALLEL_AGENT", "Compare Advisors", {
            "name": "compare_advisors",
            "description": "Ask the diet and sentiment advisors the same question at once.",
            "max_concurrency": 2,
            "stop_on_error": False,
        }, 640, 300),
        _remote("diet", "Diet Advisor", "diet_advisor", 8005,
                "Answers questions about diet, nutrition and healthy eating.", 40, 300),
        _remote("sentiment", "Sentiment", "sentiment_analyzer", 8002,
                "Scores text as positive, negative or neutral.", 40, 600),

        # Sequential group: summarise first, then compute over the summary.
        _node("pipeline", "SEQUENTIAL_AGENT", "Summarise then Count", {
            "name": "summarise_then_count",
            "description": "Summarise the text, then compute over the summary.",
            "order": ["summarizer", "calculator"],
            "stop_on_error": True,
        }, 640, 900),
        _remote("summarizer", "Summarizer", "text_summarizer", 8003,
                "Summarises long text into key points.", 40, 900),
        _remote("calculator", "Calculator", "calculator", 8004,
                "Evaluates a maths expression.", 40, 1200),

        _node("end", "END", "End", {"output_mapping": {"result": "answer"}}, 1860, 40),
    ],
    "edges": [
        _edge("e1", "trigger", "orchestrator"),

        _edge("e2", "diet", "compare", "tools"),
        _edge("e3", "sentiment", "compare", "tools"),
        _edge("e4", "compare", "orchestrator", "tools"),

        _edge("e5", "summarizer", "pipeline", "tools"),
        _edge("e6", "calculator", "pipeline", "tools"),
        _edge("e7", "pipeline", "orchestrator", "tools"),

        _edge("e8", "orchestrator", "end"),
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Tool Groups",
            "description": "An orchestrator whose tools are arranged into a parallel and a sequential group.",
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
