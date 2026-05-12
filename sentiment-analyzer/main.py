"""Sentiment Analyzer A2A Agent — keyword-based sentiment scoring."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Sentiment Analyzer Agent", version="1.0.0")

POSITIVE_WORDS = {
    "great", "good", "excellent", "amazing", "wonderful", "fantastic", "love",
    "happy", "joy", "best", "awesome", "beautiful", "perfect", "brilliant",
    "superb", "outstanding", "positive", "success", "win", "like", "enjoy",
    "glad", "pleased", "excited", "thrilled", "delighted", "helpful",
}
NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "horrible", "hate", "worst", "poor",
    "sad", "angry", "fail", "failure", "disappointing", "disappointed",
    "frustrating", "frustrated", "wrong", "broken", "useless", "waste",
    "annoying", "annoyed", "ugly", "painful", "boring", "slow", "problem",
}


def _analyze(text: str) -> dict:
    words = text.lower().split()
    clean = [w.strip(".,!?;:\"'()[]{}") for w in words]
    pos_hits = [w for w in clean if w in POSITIVE_WORDS]
    neg_hits = [w for w in clean if w in NEGATIVE_WORDS]

    total = len(pos_hits) + len(neg_hits) or 1
    pos_score = len(pos_hits) / total
    neg_score = len(neg_hits) / total

    if pos_score > neg_score:
        sentiment = "positive"
        score = round(0.5 + pos_score * 0.5, 3)
    elif neg_score > pos_score:
        sentiment = "negative"
        score = round(0.5 - neg_score * 0.5, 3)
    else:
        sentiment = "neutral"
        score = 0.5

    return {
        "sentiment": sentiment,
        "score": score,
        "positive_keywords": pos_hits[:5],
        "negative_keywords": neg_hits[:5],
        "word_count": len(clean),
    }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "sentiment-analyzer"}


@app.get("/a2a/agent-card")
def agent_card():
    return {
        "name": "Sentiment Analyzer",
        "description": "Analyzes text sentiment: positive, negative, or neutral.",
        "version": "1.0.0",
    }


@app.post("/")
@app.post("/a2a")
async def handle_message(request: Request):
    body = await request.json()

    if body.get("method") == "message/send":
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        message = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
        result = _analyze(message)
        import json as _j
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "artifacts": [{"parts": [{"kind": "text", "text": _j.dumps(result)}]}]
            },
        })

    message = body.get("message", "") if isinstance(body, dict) else ""
    result = _analyze(message)
    return JSONResponse({**result, "query": message, "agent": "sentiment-analyzer"})
