from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class TimeframeEnum(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


class RiskMethodEnum(str, Enum):
    FIXED_LOT = "fixed_lot"
    FIXED_FRACTIONAL = "fixed_fractional"
    KELLY = "kelly"
    MARTINGALE = "martingale"


class StrategyTypeEnum(str, Enum):
    SIGNAL = "signal"
    GRID = "grid"
    HEDGE = "hedge"
    SCALP = "scalp"


class ConditionLogicEnum(str, Enum):
    AND = "AND"
    OR = "OR"


class ConditionConfig(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def absorb_extra_as_params(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        known = {"type", "params"}
        extra = {k: v for k, v in values.items() if k not in known}
        if extra:
            existing = values.get("params", {})
            values["params"] = {**extra, **existing}
        return values


class EntryExitConfig(BaseModel):
    conditions: list[ConditionConfig] = Field(default_factory=list)
    logic: ConditionLogicEnum = ConditionLogicEnum.AND


class RiskConfig(BaseModel):
    method: RiskMethodEnum
    risk_pct: float | None = None
    lot_size: float | None = None
    stop_loss_pips: float | None = None
    take_profit_pips: float | None = None
    trailing_stop: bool = False
    trailing_stop_pips: float | None = None
    max_daily_loss_usd: float = Field(gt=0)
    max_open_positions: int = Field(default=1, ge=1)
    max_lot_size: float = Field(gt=0)

    # Martingale-specific — required when method=martingale (no defaults allowed)
    max_multiplier: float | None = None
    multiplier: float | None = None

    @model_validator(mode="after")
    def validate_method_fields(self) -> RiskConfig:
        if self.method == RiskMethodEnum.FIXED_LOT and self.lot_size is None:
            raise ValueError("fixed_lot requires lot_size")
        if self.method == RiskMethodEnum.FIXED_FRACTIONAL and self.risk_pct is None:
            raise ValueError("fixed_fractional requires risk_pct")
        if self.method == RiskMethodEnum.KELLY and self.risk_pct is None:
            raise ValueError("kelly requires risk_pct (used as max bet fraction)")
        if self.method == RiskMethodEnum.MARTINGALE:
            if self.max_multiplier is None:
                raise ValueError("martingale requires max_multiplier — no default allowed")
            if self.max_lot_size is None:
                raise ValueError("martingale requires max_lot_size — no default allowed")
        return self

    @field_validator("risk_pct")
    @classmethod
    def risk_pct_range(cls, v: float | None) -> float | None:
        if v is not None and not (0 < v <= 100):
            raise ValueError("risk_pct must be between 0 and 100")
        return v


class GridConfig(BaseModel):
    direction: str = "both"
    levels: int = Field(ge=2)
    spacing_usd: float | None = None
    spacing_pips: float | None = None
    base_lot: float = Field(gt=0)

    @model_validator(mode="after")
    def needs_spacing(self) -> GridConfig:
        if self.spacing_usd is None and self.spacing_pips is None:
            raise ValueError("grid requires spacing_usd or spacing_pips")
        return self


class StrategyConfig(BaseModel):
    strategy: str
    symbol: str
    timeframe: TimeframeEnum
    description: str = ""
    type: StrategyTypeEnum = StrategyTypeEnum.SIGNAL
    enabled: bool = True

    entry: EntryExitConfig | None = None
    exit: EntryExitConfig | None = None
    grid: GridConfig | None = None
    risk: RiskConfig

    @model_validator(mode="after")
    def validate_type_fields(self) -> StrategyConfig:
        if self.type == StrategyTypeEnum.GRID and self.grid is None:
            raise ValueError("grid strategy requires grid config block")
        if self.type == StrategyTypeEnum.SIGNAL and self.entry is None:
            raise ValueError("signal strategy requires entry config block")
        return self
