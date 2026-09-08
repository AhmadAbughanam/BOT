from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from bot.llm.base import ChatMessage
from bot.llm.chain import LLMChain
from bot.refine.criteria import (
    DEFAULT_CRITERIA,
    DRAFT_SYSTEM,
    eval_prompt,
    revise_prompt,
)
from bot.storage.models import LoopTrace

logger = logging.getLogger(__name__)


@dataclass
class RefineConfig:
    max_iterations: int = 3
    score_threshold: float = 0.85
    criteria: list[str] = field(default_factory=lambda: list(DEFAULT_CRITERIA))
    keep_traces: bool = True

    @classmethod
    def from_mapping(cls, data: dict | None) -> "RefineConfig":
        data = data or {}
        cfg = cls()
        if "max_iterations" in data:
            cfg.max_iterations = int(data["max_iterations"])
        if "score_threshold" in data:
            cfg.score_threshold = float(data["score_threshold"])
        if data.get("criteria"):
            cfg.criteria = list(data["criteria"])
        if "keep_traces" in data:
            cfg.keep_traces = bool(data["keep_traces"])
        return cfg


@dataclass
class RefineResult:
    answer: str
    score: float
    iterations: int
    run_id: str


def _parse_eval(text: str) -> tuple[float, str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return 0.0, "eval response had no JSON object"
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return 0.0, "eval response was not valid JSON"
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(1.0, score))
    return score, str(data.get("critique", ""))


async def refine(
    question: str,
    chain: LLMChain,
    config: RefineConfig | None = None,
    *,
    context: str | None = None,
    task: str | None = None,
    session: Session | None = None,
) -> RefineResult:
    """Draft -> self-eval -> revise, repeating until threshold or max iterations.

    Returns the highest-scoring draft seen across all iterations (not necessarily the last).
    """
    cfg = config or RefineConfig()
    run_id = uuid4().hex[:16]
    system = DRAFT_SYSTEM if context is None else f"{DRAFT_SYSTEM}\n\nCONTEXT:\n{context}"

    draft = await chain.chat(
        [ChatMessage("system", system), ChatMessage("user", question)]
    )
    current = draft.text
    best_text, best_score = current, -1.0
    iterations = 0

    for i in range(1, cfg.max_iterations + 1):
        iterations = i
        evaluation = await chain.chat(
            [ChatMessage("user", eval_prompt(question, current, cfg.criteria))],
            temperature=0.0,
        )
        score, critique = _parse_eval(evaluation.text)

        if cfg.keep_traces and session is not None:
            session.add(
                LoopTrace(
                    run_id=run_id,
                    task=task,
                    iteration=i,
                    draft=current,
                    score=score,
                    critique=critique,
                )
            )

        if score > best_score:
            best_text, best_score = current, score

        if score >= cfg.score_threshold or i == cfg.max_iterations:
            break

        revised = await chain.chat(
            [ChatMessage("user", revise_prompt(question, current, critique))]
        )
        current = revised.text

    logger.info("refine run %s: %d iteration(s), best score %.2f", run_id, iterations, best_score)
    return RefineResult(answer=best_text, score=best_score, iterations=iterations, run_id=run_id)
