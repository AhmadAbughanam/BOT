from __future__ import annotations

DEFAULT_CRITERIA: list[str] = [
    "grounded in the provided sources, no invented facts",
    "relevant to my stated interests",
    "correct dates and numbers",
    "no filler or hedging",
    "length fits the channel",
]

DRAFT_SYSTEM = (
    "You are a concise personal assistant. Answer the user directly and factually. "
    "If context is provided, rely on it and do not invent details."
)


def eval_prompt(question: str, draft: str, criteria: list[str]) -> str:
    checklist = "\n".join(f"- {c}" for c in criteria)
    return (
        "Score the draft answer from 0.0 to 1.0 against every criterion below.\n"
        f"CRITERIA:\n{checklist}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"DRAFT:\n{draft}\n\n"
        'Reply with ONLY compact JSON: {"score": <float 0..1>, "critique": "<one short paragraph>"}'
    )


def revise_prompt(question: str, draft: str, critique: str) -> str:
    return (
        "Rewrite the draft answer so it fully addresses the critique. "
        "Keep what already works; change only what the critique calls out.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"DRAFT:\n{draft}\n\n"
        f"CRITIQUE:\n{critique}\n\n"
        "Return only the improved answer, nothing else."
    )
