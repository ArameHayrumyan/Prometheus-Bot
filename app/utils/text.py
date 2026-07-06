"""Small text helpers shared by display code."""


def smart_truncate(text: str, limit: int) -> str:
    """Cut at the last sentence end (or word boundary) before `limit`,
    never mid-word, appending an ellipsis when something was dropped."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # prefer a sentence boundary in the second half of the window
    best = -1
    for sep in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
        idx = cut.rfind(sep)
        if idx > best:
            best = idx
    if best >= limit * 0.5:
        return cut[:best + 1].rstrip()
    # else fall back to the last word boundary
    idx = cut.rfind(" ")
    if idx > 0:
        cut = cut[:idx]
    return cut.rstrip(" ,;:-") + "…"
