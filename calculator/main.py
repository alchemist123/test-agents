"""Calculator A2A Agent — safe math expression evaluator."""
import ast
import math
import operator
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Calculator Agent", version="1.0.0")

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "ceil": math.ceil, "floor": math.floor,
    "round": round, "log": math.log, "log10": math.log10, "exp": math.exp,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "pi": math.pi, "e": math.e,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _SAFE_FUNCS:
        val = _SAFE_FUNCS[node.id]
        if isinstance(val, (int, float)):
            return val
        raise ValueError(f"Cannot use {node.id} as a value here")
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
            raise ValueError(f"Unsupported function call")
        fn = _SAFE_FUNCS[node.func.id]
        if not callable(fn):
            raise ValueError(f"{node.func.id} is not callable")
        args = [_eval_node(a) for a in node.args]
        return fn(*args)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def _extract_expression(message: str) -> str:
    """Pull the math expression out of a natural-language message."""
    # Try to find a pattern like "calculate 3+4" or just "3 + 4 * 2"
    match = re.search(r"(?:calculate|compute|eval|=\s*)([\d\s\+\-\*\/\^\(\)\.%a-z]+)", message, re.I)
    if match:
        return match.group(1).strip()
    # Fall back to the whole message stripped of non-math chars
    return re.sub(r"[^0-9\s\+\-\*\/\^\(\)\.%a-z]", "", message.lower()).strip()


def _calculate(expression: str) -> dict:
    expr = expression.strip().replace("^", "**")
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return {
            "result": result,
            "expression": expression,
            "formatted": f"{expression} = {result}",
            "error": None,
        }
    except Exception as exc:
        return {
            "result": None,
            "expression": expression,
            "formatted": None,
            "error": str(exc),
        }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "calculator"}


@app.get("/a2a/agent-card")
def agent_card():
    return {
        "name": "Calculator",
        "description": "Safely evaluates math expressions. Supports +,-,*,/,**,%,sqrt,log,sin,cos,tan.",
        "version": "1.0.0",
    }


@app.post("/")
@app.post("/a2a")
async def handle_message(request: Request):
    body = await request.json()

    if body.get("method") == "message/send":
        parts = body.get("params", {}).get("message", {}).get("parts", [])
        message = " ".join(p.get("text", "") for p in parts if p.get("kind") == "text")
        expr = _extract_expression(message)
        result = _calculate(expr)
        summary = result["formatted"] or result.get("error", "Could not evaluate")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "artifacts": [{"parts": [{"kind": "text", "text": summary}]}]
            },
        })

    message = body.get("message", "") if isinstance(body, dict) else ""
    expr = _extract_expression(message)
    result = _calculate(expr)
    return JSONResponse({**result, "query": message, "agent": "calculator"})
