"""
Workflow 2: Data Transform Pipeline
────────────────────────────────────
HTTP_TRIGGER → TRANSFORM (extract fields via JMESPath) → TRANSFORM (format with Jinja2) → END

Tests: chained TRANSFORM nodes with different modes (jmespath + jinja2).

Expected input:
  {"user": {"name": "Alice", "email": "alice@example.com"}, "items": [1, 2, 3], "total": 42}

After first TRANSFORM (jmespath):
  {"name": "Alice", "email": "alice@example.com", "item_count": 3, "total": 42}

After second TRANSFORM (jinja2):
  {"greeting": "Hello Alice!", "summary": "You have 3 items totalling 42."}
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
            "metadata": {
                "title": "Start",
                "description": 'POST /run with {"user": {"name": "...", "email": "..."}, "items": [...], "total": N}',
            },
            "config": {"method": "POST", "path": "/run"},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 60, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "extract",
            "type": "TRANSFORM",
            "version": "1",
            "position": {"x": 280, "y": 200},
            "metadata": {"title": "Extract Fields", "description": "JMESPath: flatten nested user + aggregate items"},
            "config": {
                "mode": "jmespath",
                "expression": "{name: user.name, email: user.email, item_count: length(items), total: total}",
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "format",
            "type": "TRANSFORM",
            "version": "1",
            "position": {"x": 520, "y": 200},
            "metadata": {"title": "Format Output", "description": "Jinja2: render a human-readable summary"},
            "config": {
                "mode": "jinja2",
                "expression": '{"greeting": "Hello {{ name }}!", "email": "{{ email }}", "summary": "You have {{ item_count }} items totalling {{ total }}."}',
            },
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
        {
            "id": "end",
            "type": "END",
            "version": "1",
            "position": {"x": 760, "y": 200},
            "metadata": {"title": "Done", "description": ""},
            "config": {},
            "io": {"input_schema": {"type": "object"}, "output_schema": {"type": "object"}},
            "policies": {"timeout_seconds": 30, "retry": {"max_attempts": 1}, "on_error": "fail"},
        },
    ],
    "edges": [
        {"id": "e1", "source": "trigger", "source_handle": "output", "target": "extract", "target_handle": "input"},
        {"id": "e2", "source": "extract",  "source_handle": "output", "target": "format",  "target_handle": "input"},
        {"id": "e3", "source": "format",   "source_handle": "output", "target": "end",     "target_handle": "input"},
    ],
}


def seed():
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{BASE}/workflows", json={
            "name": "Data Transform Pipeline",
            "description": "Chains two TRANSFORM nodes: JMESPath extraction then Jinja2 formatting.",
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
