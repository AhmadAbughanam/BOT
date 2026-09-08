from __future__ import annotations

from bot.llm.base import ChatResult
from bot.refine.loop import RefineConfig, _parse_eval, refine


class ScriptedChain:
    """Returns canned responses in order; records every prompt it was given."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.prompts: list[str] = []

    async def chat(self, messages, *, temperature=0.7, max_tokens=None) -> ChatResult:
        self.prompts.append(messages[-1].content)
        text = self._replies.pop(0)
        return ChatResult(text=text, provider="fake", model="fake")


async def test_stops_once_threshold_is_met() -> None:
    chain = ScriptedChain(["draft-1", '{"score": 0.9, "critique": "good"}'])
    cfg = RefineConfig(max_iterations=3, score_threshold=0.85, keep_traces=False)

    result = await refine("q", chain, cfg)

    assert result.answer == "draft-1"
    assert result.iterations == 1
    assert len(chain._replies) == 0  # draft + one eval, no revise


async def test_iterates_and_returns_last_when_it_improves() -> None:
    chain = ScriptedChain(
        [
            "draft-1",
            '{"score": 0.4, "critique": "too vague"}',
            "draft-2",
            '{"score": 0.95, "critique": "sharp"}',
        ]
    )
    cfg = RefineConfig(max_iterations=3, score_threshold=0.85, keep_traces=False)

    result = await refine("q", chain, cfg)

    assert result.answer == "draft-2"
    assert result.score == 0.95
    assert result.iterations == 2


async def test_returns_best_scoring_draft_not_the_last() -> None:
    chain = ScriptedChain(
        [
            "draft-1",
            '{"score": 0.8, "critique": "close"}',
            "draft-2",
            '{"score": 0.3, "critique": "worse"}',
        ]
    )
    cfg = RefineConfig(max_iterations=2, score_threshold=0.99, keep_traces=False)

    result = await refine("q", chain, cfg)

    assert result.answer == "draft-1"
    assert result.score == 0.8
    assert result.iterations == 2


def test_parse_eval_handles_noise_around_json() -> None:
    score, critique = _parse_eval('here you go: {"score": 0.73, "critique": "ok"} thanks')
    assert score == 0.73
    assert critique == "ok"


def test_parse_eval_clamps_and_defaults() -> None:
    assert _parse_eval('{"score": 5}')[0] == 1.0
    assert _parse_eval("not json at all")[0] == 0.0
