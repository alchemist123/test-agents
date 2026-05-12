"""Text Summarizer A2A Agent — extractive summarization by sentence scoring."""
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Text Summarizer Agent", version="1.0.0")

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it", "its",
    "i", "we", "you", "he", "she", "they", "me", "us", "him", "her", "them",
}


def _word_freq(sentences: list[str]) -> dict[str, int]:
    freq: dict[str, int] = {}
    for s in sentences:
        for word in re.findall(r"\b\w+\b", s.lower()):
            if word not in STOP_WORDS and len(word) > 2:
                freq[word] = freq.get(word, 0) + 1
    return freq


def _score_sentence(sentence: str, freq: dict[str, int]) -> float:
    words = [w for w in re.findall(r"\b\w+\b", sentence.lower()) if w not in STOP_WORDS]
    if not words:
        return 0.0
    return sum(freq.get(w, 0) for w in words) / len(words)


def _summarize(text: str, max_sentences: int = 3) -> dict:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    if not sentences:
        return {"summary": text[:300], "key_points": [], "word_count": len(text.split())}

    freq = _word_freq(sentences)
    scored = sorted(
        enumerate(sentences),
        key=lambda x: _score_sentence(x[1], freq),
        reverse=True,
    )
    top_indices = sorted(i for i, _ in scored[:max_sentences])
    summary = " ".join(sentences[i] for i in top_indices)
    key_points = [sentences[i] for i in top_indices]

    return {
        "summary": summary,
        "key_points": key_points,
        "original_sentence_count": len(sentences),
        "word_count": len(text.split()),
    }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "text-summarizer"}


@app.get("/a2a/agent-card")
def agent_card():
    return {
        "name": "Text Summarizer",
        "description": "Extracts the most important sentences from a body of text.",
        "version": "1.0.0",
    }


@app.post("/")
@app.post("/a2a")
async def handle_message(request: Request):
    body = await request.json()

    if body.get("method") == "message/send":
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        message = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
        result = _summarize(message)
        import json as _j
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "artifacts": [{"parts": [{"kind": "text", "text": _j.dumps(result)}]}]
            },
        })

    message = body.get("message", "") if isinstance(body, dict) else ""
    result = _summarize(message)
    return JSONResponse({**result, "agent": "text-summarizer"})
