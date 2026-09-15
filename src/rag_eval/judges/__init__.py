"""Judge abstraction for model-based semantic evaluation.

Judges evaluate claims, evidence relationships, and other semantic judgments.
They are separate from target execution and operate on persisted data.

This package provides:
- JudgeAdapter protocol (provider-neutral)
- DummyJudgeAdapter for testing
"""

from .base import DummyJudgeAdapter, JudgeAdapter

__all__ = [
    "JudgeAdapter",
    "DummyJudgeAdapter",
]
