"""Base class for all target strategies."""
from abc import ABC, abstractmethod

import pandas as pd


class TargetStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def build(self, features: pd.DataFrame) -> pd.Series:
        """Return a Series named 'target', indexed like features."""
        ...

    def description(self) -> str:
        return self.name
