"""Judge abstraction for model-based semantic evaluation.

Judges evaluate claims, evidence relationships, and other semantic judgments.
They are separate from target execution and operate on persisted data.

This package provides:
- JudgeAdapter protocol (provider-neutral)
"""

from .base import JudgeAdapter, JudgeConfiguration
from .openai_compatible import OpenAICompatibleJudge, create_judge_adapter

__all__ = [
    "JudgeAdapter",
    "JudgeConfiguration",
    "OpenAICompatibleJudge",
    "create_judge_adapter",
]
