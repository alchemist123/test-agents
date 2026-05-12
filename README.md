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
```

## Workflow descriptions

### 1. Condition Router
`HTTP_TRIGGER → CONDITION → [true] TRANSFORM → END`
                          `→ [false] TRANSFORM → END`

Sends `{"score": 75, "message": "hello"}` — score > 50 routes to premium tier,
score ≤ 50 routes to standard tier.

### 2. Data Transform Pipeline
`HTTP_TRIGGER → TRANSFORM (JMESPath) → TRANSFORM (Jinja2) → END`

Input: `{"user": {"name": "Alice", "email": "..."}, "items": [1,2,3], "total": 42}`  
First TRANSFORM extracts fields; second renders a human-readable greeting.

### 3. Remote Agent Chain
`HTTP_TRIGGER → REMOTE_AGENT (diet) → REMOTE_AGENT (sentiment) → TRANSFORM → END`

Chains two agents: diet advisor gives a tip, sentiment analyzer scores its tone.
Requires agents running on ports 8001 and 8002.

### 4. Multi-Tool Orchestrator
`HTTP_TRIGGER → ORCHESTRATOR_AGENT → END`  
(with diet-advisor, text-summarizer, calculator wired as tools)

ADK-powered agent that picks the right tool automatically.  
Try: `{"message": "what should I eat to build muscle?"}` — routes to diet advisor.  
Try: `{"message": "calculate 15 * 7 + 3"}` — routes to calculator.  
Requires agents running and Vertex AI / Google AI key configured in the backend.
