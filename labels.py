def get_label(confidence: float) -> str:
    """
    Map a confidence score (0–1, higher = more likely AI-generated) to a
    transparency label for creators.
    """
    # These three label strings must match planning.md verbatim — the README
    # documentation requirement depends on exact text.

    # High-confidence AI: confidence ≥ 0.70 means we lean strongly toward AI origin.
    if confidence >= 0.70:
        pct = round(confidence * 100)
        return f"This content is likely AI-generated (High confidence: {pct}%)."

    # High-confidence human: confidence ≤ 0.30 means we lean strongly toward human origin.
    if confidence <= 0.30:
        # Invert the percentage: confidence measures AI-likelihood, so a score like
        # 0.18 means 82% sure it's human — showing "18%" next to "high confidence"
        # would contradict the label.
        pct = round((1 - confidence) * 100)
        return f"This content is likely written by a human (High confidence: {pct}%)."

    # Uncertain: 0.30 < confidence < 0.70 — not enough certainty either way.
    pct = round(confidence * 100)
    return f"We are uncertain about the origin of this content (Confidence: {pct}%)."
