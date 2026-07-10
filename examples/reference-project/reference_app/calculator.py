"""Deterministic score helpers for the reference fixture."""


def summarize_scores(scores: list[int]) -> dict[str, float | int]:
    """Return a tiny stable summary for integer scores."""
    if not scores:
        return {"count": 0, "minimum": 0, "maximum": 0, "average": 0.0}
    return {
        "count": len(scores),
        "minimum": min(scores),
        "maximum": max(scores),
        "average": round(sum(scores) / len(scores), 2),
    }
