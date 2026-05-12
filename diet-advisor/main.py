"""Diet Advisor A2A Agent — rule-based nutrition & diet tips."""
import random
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Diet Advisor Agent", version="1.0.0")

TIPS = {
    "weight_loss": [
        "Create a moderate calorie deficit of 300-500 kcal/day for sustainable weight loss.",
        "Prioritize protein (1.6-2.2 g/kg body weight) to preserve muscle mass while cutting.",
        "Fill half your plate with non-starchy vegetables — high volume, low calories.",
        "Limit liquid calories: sodas, juices and alcohol add up fast without satiety.",
        "Eat slowly and mindfully — it takes 20 minutes for satiety signals to reach the brain.",
    ],
    "muscle_gain": [
        "Eat in a 250-500 kcal surplus and target 1.6-2.4 g protein per kg body weight.",
        "Distribute protein intake across 4-5 meals to maximize muscle protein synthesis.",
        "Time carbs around your workouts — pre- and post-workout carbs fuel performance and recovery.",
        "Don't neglect sleep: growth hormone peaks during deep sleep, driving muscle repair.",
        "Creatine monohydrate (3-5 g/day) is the most evidence-backed supplement for strength.",
    ],
    "hydration": [
        "Aim for pale-yellow urine — a reliable hydration indicator throughout the day.",
        "Drink 500 ml of water 30 minutes before meals to naturally reduce portion sizes.",
        "Electrolytes matter: add a pinch of salt or an electrolyte tablet for long workouts.",
        "Coffee and tea count toward daily fluid intake; the diuretic effect is mild.",
        "Thirst is a late signal — drink consistently before you feel thirsty.",
    ],
    "general": [
        "Eat whole foods 80% of the time; the remaining 20% can include treats without guilt.",
        "Meal prep on weekends reduces weekday decision fatigue and unhealthy impulse choices.",
        "A Mediterranean-style diet has the strongest evidence base for long-term health.",
        "Fibre goal: 25-35 g/day from vegetables, legumes, and whole grains.",
        "Limit ultra-processed foods — they are engineered to override satiety signals.",
    ],
}

KEYWORDS = {
    "weight_loss": ["weight", "lose", "fat", "diet", "slim", "calorie", "deficit"],
    "muscle_gain": ["muscle", "gain", "bulk", "protein", "strength", "hypertrophy", "build"],
    "hydration": ["water", "hydrat", "drink", "thirst", "fluid", "electrolyte"],
}


def _classify(message: str) -> str:
    lower = message.lower()
    for category, kws in KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return category
    return "general"


@app.get("/health")
def health():
    return {"status": "ok", "agent": "diet-advisor"}


@app.get("/a2a/agent-card")
def agent_card():
    return {
        "name": "Diet Advisor",
        "description": "Provides evidence-based diet and nutrition tips.",
        "version": "1.0.0",
        "capabilities": ["weight_loss", "muscle_gain", "hydration", "general"],
    }


@app.post("/")
@app.post("/a2a")
async def handle_message(request: Request):
    body = await request.json()

    # A2A JSON-RPC message/send format
    if body.get("method") == "message/send":
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        message = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
        category = _classify(message)
        tip = random.choice(TIPS[category])
        result_text = f"{tip} (category: {category})"
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "artifacts": [{"parts": [{"kind": "text", "text": result_text}]}]
            },
        })

    # Simple REST format: {"message": "..."}
    message = body.get("message", "") if isinstance(body, dict) else ""
    category = _classify(message)
    tip = random.choice(TIPS[category])
    return JSONResponse({
        "response": tip,
        "category": category,
        "query": message,
        "agent": "diet-advisor",
    })
