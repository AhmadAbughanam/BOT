from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.orm import Session

from bot.jsonutil import extract_json
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
    judge_model: str | None = None  # "provider:model" for the self-eval step; None = use the main chain

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
        if data.get("judge_model"):
            cfg.judge_model = str(data["judge_model"])
        return cfg


@dataclass
class RefineResult:
    answer: str
    score: float
    iterations: int
    run_id: str


def _parse_eval(text: str) -> tuple[float, str]:
    data = extract_json(text)
    if not isinstance(data, dict):
        return 0.0, "eval response had no JSON object"
    try:
        score = float(data.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(1.0, score))
    return score, str(data.get("critique", ""))


def _judge_chain(cfg: RefineConfig, fallback: LLMChain) -> LLMChain:
    if not cfg.judge_model:
        return fallback
    try:
        from bot.llm.chain import chain_for_model

        return chain_for_model(cfg.judge_model)
    except Exception as exc:  # noqa: BLE001 - bad config must not break the loop
        logger.warning("judge_model %r unusable, scoring with the main chain: %s", cfg.judge_model, exc)
        return fallback


async def refine(
    question: str,
    chain: LLMChain,
    config: RefineConfig | None = None,
    *,
    context: str | None = None,
    task: str | None = None,
    session: Session | None = None,
    judge_chain: LLMChain | None = None,
) -> RefineResult:
    """Draft -> self-eval -> revise, repeating until threshold or max iterations.

    Returns the highest-scoring draft seen across all iterations (not necessarily the last).
    The self-eval step uses `judge_chain` (or `config.judge_model`) when set, else the main chain.
    """
    cfg = config or RefineConfig()
    judge = judge_chain or _judge_chain(cfg, chain)
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
        evaluation = await judge.chat(
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
