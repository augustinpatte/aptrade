"""The strategy interface.

A strategy only looks at bars and emits signals. It never sizes, never checks
limits and never talks to a broker: the backtester (and later the risk module and
the broker) do that. The same strategy object therefore runs unchanged in a
backtest, in paper trading and live, which is what makes those results comparable."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..sessions import Session


@dataclass(frozen=True)
class Signal:
    side: str            # "long" or "short"
    bar: int             # index of the bar whose CLOSE produced the signal
    ref_price: float     # the price the plan is built on (that bar's close)
    stop: float          # bracket levels, fixed before any fill
    target: float
    tag: dict = field(default_factory=dict)

    @property
    def risk(self) -> float:
        """Planned risk per share. Positions are sized on this, so R is measured in it."""
        return self.ref_price - self.stop if self.side == "long" else self.stop - self.ref_price


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def signals(self, session: Session) -> list[Signal]:
        """Signals for one session, in time order. Must only use bars up to sig.bar."""

    @abstractmethod
    def params(self) -> dict:
        """Everything needed to rebuild this strategy: stored with every run."""
