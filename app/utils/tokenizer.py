try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None

from typing import Optional

MODEL_ENCODINGS = {
    "gpt-3.5-cheap": "cl100k_base",
    "gpt-4-expensive": "cl100k_base",
}


def _get_encoding(model: str):
    if tiktoken is None:
        return None
    encoding_name = MODEL_ENCODINGS.get(model, "cl100k_base")
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception:
            return None


def estimate_tokens(content: str, model: str = "gpt-4-expensive") -> int:
    if tiktoken is None:
        return max(1, len(content) // 4)
    enc = _get_encoding(model)
    if enc is None:
        return max(1, len(content) // 4)
    return max(1, len(enc.encode(content)))


def estimate_cost(tokens: int, model: str, cost_per_1k: float, multiplier: float) -> float:
    price = {
        "gpt-3.5-cheap": cost_per_1k,
        "gpt-4-expensive": cost_per_1k * multiplier,
    }.get(model, cost_per_1k)
    return round(tokens / 1000 * price, 6)
