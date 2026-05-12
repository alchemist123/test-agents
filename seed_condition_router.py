"""
Workflow 1: Condition Router
────────────────────────────
HTTP_TRIGGER → CONDITION (routes by score threshold) → [true] TRANSFORM → END
                                                      → [false] TRANSFORM → END

Tests: CONDITION node with two named branches, branching edges, two TRANSFORM nodes.
"""
import httpx, sys

BASE = "http://localhost:8001/api/v1"

CANVAS = {
    "nodes": [
        {
            "id": "trigger",
            "type": "HTTP_TRIGGER",
            "version": "1",
            "position": {"x": 50, "y": 200},
            "metadata": {"title": "Start", "description": "POST /run with {score: number, message: string}"},
            "config": {"method": "POST", "path": "/run"},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 60, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "condition",
            "type": "CONDITION",
            "version": "1",
            "position": {"x": 280, "y": 200},
            "metadata": {"title": "Score Check", "description": "Route: score > 50 → premium, else → standard"},
            "config": {
                "branches": [
                    {"name": "high_score", "expression": "data.get('score', 0) > 50"},
                    {"name": "low_score",  "expression": "data.get('score', 0) <= 50"},
                ]
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "transform_high",
            "type": "TRANSFORM",
            "version": "1",
            "position": {"x": 520, "y": 100},
            "metadata": {"title": "Premium Response", "description": "Enrich response for high-score users"},
            "config": {
                "mode": "jinja2",
                "expression": '{"tier": "premium", "message": "{{ message }}", "score": {{ score }}, "perk": "10% discount applied"}',
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "transform_low",
            "type": "TRANSFORM",
            "version": "1",
            "position": {"x": 520, "y": 320},
            "metadata": {"title": "Standard Response", "description": "Standard response for low-score users"},
            "config": {
                "mode": "jinja2",
                "expression": '{"tier": "standard", "message": "{{ message }}", "score": {{ score }}}',
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "end_high",
            "type": "END",
            "version": "1",
            "position": {"x": 760, "y": 100},
            "metadata": {"title": "End (Premium)", "description": ""},
            "config": {},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "end_low",
            "type": "END",
            "version": "1",
            "position": {"x": 760, "y": 320},
            "metadata": {"title": "End (Standard)", "description": ""},
            "config": {},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger",        "source_handle": "output",     "target": "condition",      "target_handle": "input"},
        {"id": "e2", "source": "condition",       "source_handle": "true",       "target": "transform_high", "target_handle": "input"},
        {"id": "e3", "source": "condition",       "source_handle": "false",      "target": "transform_low",  "target_handle": "input"},
        {"id": "e4", "source": "transform_high",  "source_handle": "output",     "target": "end_high",       "target_handle": "input"},
        {"id": "e5", "source": "transform_low",   "source_handle": "output",     "target": "end_low",        "target_handle": "input"},
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        # Create workflow
        r = client.post(f"{BASE}/workflows", json={"name": "Condition Router", "description": "Routes by score threshold — high (>50) gets premium tier, low gets standard."})
        r.raise_for_status()
        wf_id = r.json()["id"]
        print(f"Created workflow: {wf_id}")

        # Compile canvas
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
