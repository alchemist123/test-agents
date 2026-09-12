"""
Workflow 4: Orchestrator Agent with Multi-Tool A2A
────────────────────────────────────────────────────
A2A_START → ORCHESTRATOR_AGENT → END
               ↑ tools ↑
    REMOTE_AGENT (diet-advisor)
    REMOTE_AGENT (calculator)
    REMOTE_AGENT (text-summarizer)

The ORCHESTRATOR_AGENT (Google ADK) sees three tool-wired agents and decides which to
call based on the user's message content.

Requires:
  - GOOGLE_CLOUD_PROJECT (or GOOGLE_API_KEY) configured in backend .env
  - Test agents running on ports 8001, 8003, 8004

Adjust *_ENDPOINT constants if agents are on different hosts.
"""
import httpx, sys

BASE = "http://localhost:8001/api/v1"

# host.docker.internal lets the backend container reach agents running on the host.
# Diet-advisor is on 8005 (8001 is taken by the backend API itself).
DIET_ENDPOINT       = "http://host.docker.internal:8005"
SUMMARIZER_ENDPOINT = "http://host.docker.internal:8003"
CALCULATOR_ENDPOINT = "http://host.docker.internal:8004"

CANVAS = {
    "nodes": [
        {
            "id": "trigger",
            "type": "A2A_START",
            "version": "1",
            "position": {"x": 50, "y": 300},
            "metadata": {"title": "Start", "description": 'POST /run with {"message": "..."}'},
            "config": {
                "input_mode": "json",
                "state_key": "wf",
                "payload_schema": {
                    "fields": [
                        {"name": 'message', "type": 'text', "description": 'Request for the orchestrator', "required": True},
                    ]
                },
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 60, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        # Tool providers (wired into orchestrator via "tools" handle)
        {
            "id": "tool_diet",
            "type": "REMOTE_AGENT",
            "version": "1",
            "position": {"x": 280, "y": 100},
            "metadata": {"title": "Diet Advisor Tool", "description": ""},
            "config": {
                "name": "diet_advisor",
                "endpoint": DIET_ENDPOINT,
                "description": "Use this tool to answer questions about diet, nutrition, weight loss, muscle gain, or healthy eating",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "tool_summarizer",
            "type": "REMOTE_AGENT",
            "version": "1",
            "position": {"x": 280, "y": 300},
            "metadata": {"title": "Summarizer Tool", "description": ""},
            "config": {
                "name": "text_summarizer",
                "endpoint": SUMMARIZER_ENDPOINT,
                "description": "Use this tool to summarize long pieces of text into concise key points",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "tool_calc",
            "type": "REMOTE_AGENT",
            "version": "1",
            "position": {"x": 280, "y": 500},
            "metadata": {"title": "Calculator Tool", "description": ""},
            "config": {
                "name": "calculator",
                "endpoint": CALCULATOR_ENDPOINT,
                "description": "Use this tool to evaluate math expressions and arithmetic calculations",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        # Orchestrator
        {
            "id": "orchestrator",
            "type": "ORCHESTRATOR_AGENT",
            "version": "1",
            "position": {"x": 560, "y": 300},
            "metadata": {
                "title": "Multi-Tool Orchestrator",
                "description": "Routes to the right specialized agent based on the user message",
            },
            "config": {
                "model": "gemini-2.0-flash",
                "system_prompt": (
                    "You are a helpful assistant with access to three tools: "
                    "a diet advisor, a text summarizer, and a calculator. "
                    "Always use the appropriate tool to answer the user's request. "
                    "Be concise and factual."
                ),
                "tool_execution_mode": "sequential",
                "output_field": "response",
                "max_turns": 5,
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 120, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "end",
            "type": "END",
            "version": "1",
            "position": {"x": 820, "y": 300},
            "metadata": {"title": "Done", "description": ""},
            "config": {},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
    ],
    "edges": [
        # Execution flow
        {"id": "e1", "source": "trigger",      "source_handle": "output", "target": "orchestrator", "target_handle": "input"},
        {"id": "e2", "source": "orchestrator", "source_handle": "output", "target": "end",          "target_handle": "input"},
        # Tool-provision edges (connect to "tools" handle)
        {"id": "t1", "source": "tool_diet",       "source_handle": "output", "target": "orchestrator", "target_handle": "tools"},
        {"id": "t2", "source": "tool_summarizer",  "source_handle": "output", "target": "orchestrator", "target_handle": "tools"},
        {"id": "t3", "source": "tool_calc",        "source_handle": "output", "target": "orchestrator", "target_handle": "tools"},
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Multi-Tool Orchestrator",
            "description": "ADK orchestrator that routes between diet advisor, text summarizer, and calculator tools.",
        })
        r.raise_for_status()
        wf_id = r.json()["id"]
        print(f"Created workflow: {wf_id}")

        r = client.post(f"{BASE}/workflows/{wf_id}/versions", json={"canvas": CANVAS})
        r.raise_for_status()
        result = r.json()
        if result["is_valid"]:
            print(f"✓ Compiled successfully — version {result['version_id']}")
        else:
            print(f"✗ Validation errors: {result['errors']}", file=sys.stderr)
        return wf_id


if __name__ == "__main__":
    seed()
