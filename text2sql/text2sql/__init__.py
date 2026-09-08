"""text2sql verifiers v1 environment: RL on one bank database (BIRD financial) with execution reward."""
from verifiers.v1.harnesses.null.harness import NullHarness, NullHarnessConfig

from text2sql.taskset import T2SQLEnv, T2SQLTaskset


class T2SQLHarnessConfig(NullHarnessConfig):
    pass


class T2SQLHarness(NullHarness):
    """Plain single-turn chat, no tools, no container (exported so verifiers doesn't pick the bash harness)."""


__all__ = ["T2SQLEnv", "T2SQLTaskset", "T2SQLHarness"]
