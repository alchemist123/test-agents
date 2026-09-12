"""
Workflow 3: Remote Agent Orchestration
───────────────────────────────────────
A2A_START → REMOTE_AGENT (diet-advisor) → REMOTE_AGENT (sentiment-analyzer) → TRANSFORM → END

Tests: chained REMOTE_AGENT nodes — diet advisor responds, sentiment analyzer analyzes the advice.

Requires: test agents running (docker compose up in test-agents/)
  Diet Advisor   → http://host.docker.internal:8001  (or http://localhost:8001 when run locally)
  Sentiment      → http://host.docker.internal:8002

Adjust DIET_ENDPOINT / SENTIMENT_ENDPOINT below if running outside Docker.
"""
import httpx, sys

BASE = "http://localhost:8001/api/v1"

DIET_ENDPOINT      = "http://host.docker.internal:8005"
SENTIMENT_ENDPOINT = "http://host.docker.internal:8002"

CANVAS = {
    "nodes": [
        {
            "id": "trigger",
            "type": "A2A_START",
            "version": "1",
            "position": {"x": 50, "y": 200},
            "metadata": {"title": "Start", "description": 'POST /run with {"message": "your diet question"}'},
            "config": {
                "input_mode": "json",
                "state_key": "wf",
                "payload_schema": {
                    "fields": [
                        {"name": 'message', "type": 'text', "description": 'Text for the remote agents', "required": True},
                    ]
                },
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 60, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "diet_agent",
            "type": "REMOTE_AGENT",
            "version": "1",
            "position": {"x": 280, "y": 200},
            "metadata": {"title": "Diet Advisor", "description": "Get a personalized diet tip"},
            "config": {
                "name": "diet_advisor",
                "endpoint": DIET_ENDPOINT,
                "description": "Provides evidence-based diet and nutrition tips",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 2}, "on_error": "fail"},
        },
        {
            "id": "sentiment_agent",
            "type": "REMOTE_AGENT",
            "version": "1",
            "position": {"x": 520, "y": 200},
            "metadata": {"title": "Sentiment Analyzer", "description": "Check the tone of the advice"},
            "config": {
                "name": "sentiment_analyzer",
                "endpoint": SENTIMENT_ENDPOINT,
                "description": "Analyzes the sentiment of the diet advice response",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 2}, "on_error": "fail"},
        },
        {
            "id": "summarize",
            "type": "TRANSFORM",
            "version": "1",
            "position": {"x": 760, "y": 200},
            "metadata": {"title": "Merge Results", "description": "Package both results into a single response"},
            "config": {
                "mode": "jmespath",
                "expression": "{sentiment: sentiment, score: score, advice: response, category: category}",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "end",
            "type": "END",
            "version": "1",
            "position": {"x": 980, "y": 200},
            "metadata": {"title": "Done", "description": ""},
            "config": {},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger",        "source_handle": "output", "target": "diet_agent",      "target_handle": "input"},
        {"id": "e2", "source": "diet_agent",      "source_handle": "output", "target": "sentiment_agent", "target_handle": "input"},
        {"id": "e3", "source": "sentiment_agent", "source_handle": "output", "target": "summarize",       "target_handle": "input"},
        {"id": "e4", "source": "summarize",       "source_handle": "output", "target": "end",             "target_handle": "input"},
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Remote Agent Chain",
            "description": "Calls diet-advisor then sentiment-analyzer to analyze the advice tone.",
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
