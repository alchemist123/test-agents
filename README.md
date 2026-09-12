# Test Agents & Workflows

Four standalone A2A agents for testing, plus four seed scripts that create
matching workflows in the platform.

## Agents

| Agent | Port | Purpose |
|-------|------|---------|
| diet-advisor | 8001 | Nutrition & diet tips (rule-based, by keyword) |
| sentiment-analyzer | 8002 | Keyword sentiment scoring (positive/negative/neutral) |
| text-summarizer | 8003 | Extractive summarization |
| calculator | 8004 | Safe math expression evaluator |

All agents accept `POST /` with `{"message": "..."}` and return JSON.
They also expose `GET /health` and `GET /a2a/agent-card`.

## Quick start

```bash
# Start all 4 agents
cd test-agents
docker compose up --build -d

# Verify
curl http://localhost:8001/health   # {"status":"ok","agent":"diet-advisor"}
curl http://localhost:8002/health   # {"status":"ok","agent":"sentiment-analyzer"}
curl http://localhost:8003/health   # {"status":"ok","agent":"text-summarizer"}
curl http://localhost:8004/health   # {"status":"ok","agent":"calculator"}

# Test individual agents
curl -X POST http://localhost:8001 -H "Content-Type: application/json" \
     -d '{"message": "how do I lose weight?"}'

curl -X POST http://localhost:8002 -H "Content-Type: application/json" \
     -d '{"message": "This product is absolutely amazing and I love it!"}'

curl -X POST http://localhost:8003 -H "Content-Type: application/json" \
     -d '{"message": "FastAPI is a modern, fast web framework for building APIs with Python. It is based on standard Python type hints. The key features are: fast to code, fewer bugs, intuitive, and ready for production."}'

curl -X POST http://localhost:8004 -H "Content-Type: application/json" \
     -d '{"message": "calculate sqrt(144) + 3 * 4"}'
```

## Seed workflows into the platform

With the backend running on `http://localhost:8001` (default docker-compose port):

```bash
cd test-agents/workflows

# Install httpx if needed
pip install httpx

# Seed all 4 workflows at once
python seed_all.py

# Or seed individually
python seed_condition_router.py   # Workflow 1: CONDITION branching
python seed_data_pipeline.py      # Workflow 2: Chained TRANSFORM nodes
python seed_remote_agent.py       # Workflow 3: Chained REMOTE_AGENT nodes
python seed_orchestrator.py       # Workflow 4: ORCHESTRATOR_AGENT + 3 tool agents
python seed_tool_groups.py        # Workflow 5: parallel + sequential tool groups
python seed_sub_agents.py         # Workflow 6: LLM_AGENT nodes used as sub-agents
python seed_human_approval.py     # Workflow 7: pauses at input-required for a human
python seed_all.py                # all seven
```

## Workflow descriptions

### 1. Condition Router
`A2A_START → CONDITION → [high_score|low_score] TRANSFORM → END`
                          `→ [false] TRANSFORM → END`

Sends `{"score": 75, "message": "hello"}` — score > 50 routes to premium tier,
score ≤ 50 routes to standard tier.

### 2. Data Transform Pipeline
`A2A_START → TRANSFORM (JMESPath) → TRANSFORM (Jinja2) → END`

Input: `{"user": {"name": "Alice", "email": "..."}, "items": [1,2,3], "total": 42}`  
First TRANSFORM extracts fields; second renders a human-readable greeting.

### 3. Remote Agent Chain
`A2A_START → REMOTE_AGENT (diet) → REMOTE_AGENT (sentiment) → TRANSFORM → END`

Chains two agents: diet advisor gives a tip, sentiment analyzer scores its tone.
Requires agents running on ports 8001 and 8002.

### 4. Multi-Tool Orchestrator
`A2A_START → ORCHESTRATOR_AGENT → END`  
(with diet-advisor, text-summarizer, calculator wired as tools)

ADK-powered agent that picks the right tool automatically.  
Try: `{"message": "what should I eat to build muscle?"}` — routes to diet advisor.  
Try: `{"message": "calculate 15 * 7 + 3"}` — routes to calculator.  
Requires agents running and Vertex AI / Google AI key configured in the backend.

### 5. Tool Groups
`A2A_START → ORCHESTRATOR_AGENT → END`
(with two composite tools wired into it)

    [diet]       ─┐
    [sentiment]  ─┴─tools─> [Parallel Tools "compare_advisors"]     ─┐
                                                                      ├─tools─> [ORCHESTRATOR]
    [summarizer] ─┐                                                   │
    [calculator] ─┴─tools─> [Sequential Tools "summarise_then_count"]─┘

The agent sees **two** tools rather than four: one asks both advisors at once,
the other runs a summarise-then-calculate pipeline where each step's output
feeds the next. Ordering is drawn, not configured.

### 6. Sub-agents
`A2A_START → ORCHESTRATOR_AGENT → END`
(with an LLM agent attached directly, and another inside a group)

    [weather MCP] ─tools─> [LLM Agent "trip_planner"] ─tools─┐
                                                              ├─> [ORCHESTRATOR]
    [grammar MCP] ─┐                                          │
    [LLM "editor"] ┴─tools─> [Sequential Tools "polish_text"] ─┘

`trip_planner` is attached straight to the orchestrator, so ADK exposes it with
`mode='single_turn'` via `sub_agents`. `editor` sits inside a group, so the group
drives it through its own `Runner`. Both declare an input structure — which
becomes the calling model's tool parameters — and an output structure, which
constrains the reply to a named shape.

Requires MCP servers on ports 9001/9002 and Vertex AI configured to run for real;
it compiles and packages without them.

### 7. Human in the loop
`A2A_START → CONDITION → [large] → HUMAN_APPROVAL → [approved|rejected] → TRANSFORM → END`
`                      → [small] → TRANSFORM ─────────────────────────────────────────┘`

All three things a person can be asked for. Under the threshold it goes straight
through; over it the A2A task parks at **`input-required`** for an approval, and
again afterwards for the payment details.

    python run_once.py '{"amount": 20, "reason": "coffee"}'
    # completed — the gate is never reached

    python run_once.py '{"amount": 5000, "reason": "laptops"}'
    # WAITING: prints the question and the fields to answer with

    python run_once.py '{"amount": 5000, "reason": "laptops"}' \
        --answer '{"approved": true, "comment": "ok", "cost_centre": "ENG-1"}'
    # completed, outcome "paid"

Approving pauses a second time, for `account` and `pay_on`; answer that with
`--resume`, which continues the live task instead of replaying the workflow.
Approving without `cost_centre` asks again; rejecting never needs it. Runs
offline — no model, no MCP server, no credentials.
