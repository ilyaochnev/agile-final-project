from dataclasses import dataclass
from statistics import mean
from typing import Dict, List

from app.capital_client import CapitalClient, CapitalSession


@dataclass(frozen=True)
class TradeDecision:
    direction: str
    size: float
    reason: str


def _extract_mid_prices(price_payload: Dict) -> List[float]:
    prices = []
    for candle in price_payload.get("prices", []):
        bid = candle.get("bid") or candle.get("close", {}).get("bid")
        ask = candle.get("ask") or candle.get("close", {}).get("ask")
        if bid is not None and ask is not None:
            prices.append((bid + ask) / 2)
    if not prices:
        raise ValueError("No price data returned from Capital.com API.")
    return prices


def decide_trade(price_payload: Dict, trade_size: float) -> TradeDecision:
    mids = _extract_mid_prices(price_payload)
    short_window = mids[-5:]
    long_window = mids[-20:]
    short_avg = mean(short_window)
    long_avg = mean(long_window)
    if short_avg > long_avg:
        return TradeDecision(direction="BUY", size=trade_size, reason="short_avg > long_avg")
    if short_avg < long_avg:
        return TradeDecision(direction="SELL", size=trade_size, reason="short_avg < long_avg")
    return TradeDecision(direction="NONE", size=0, reason="no crossover")


def execute_trade(
    client: CapitalClient,
    session: CapitalSession,
    epic: str,
    trade_size: float,
    dry_run: bool,
) -> Dict:
    prices = client.fetch_prices(session=session, epic=epic)
    decision = decide_trade(prices, trade_size)
    if decision.direction == "NONE":
        return {"status": "skipped", "reason": decision.reason}
    if dry_run:
        return {
            "status": "dry_run",
            "direction": decision.direction,
            "size": decision.size,
            "reason": decision.reason,
        }
    result = client.place_order(
        session=session,
        epic=epic,
        direction=decision.direction,
        size=decision.size,
    )
    return {"status": "placed", "direction": decision.direction, "result": result}
