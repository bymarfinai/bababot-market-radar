from __future__ import annotations

import unittest

from market_radar.decision_engine import DECISION_VERSION, decide
from market_radar.models import MarketContext, MovementDetection


def context(
    *,
    structure: str = "BREAKOUT",
    taker: str = "BUY",
    oi: str = "FRESH_LONG_PARTICIPATION",
    regime: str = "BULL",
    volume_confirmed: bool = True,
    funding: float | None = 0.0001,
    errors: tuple[str, ...] = (),
) -> MarketContext:
    return MarketContext(
        context_version="stage5-v1",
        quote_volume_5m=2_000_000.0,
        quote_volume_24h=100_000_000.0,
        volume_ratio=2.0,
        volume_confirmed=volume_confirmed,
        prev_20_high=100.0,
        prev_20_low=90.0,
        breakout_up_pct=1.0 if structure == "BREAKOUT" else 0.0,
        breakdown_down_pct=1.0 if structure == "BREAKDOWN" else 0.0,
        breakout=structure == "BREAKOUT",
        breakdown=structure == "BREAKDOWN",
        failed_breakout=structure == "FAILED_BREAKOUT",
        failed_breakdown=structure == "FAILED_BREAKDOWN",
        structure_status=structure,
        taker_buy_quote_volume_5m=1_300_000.0 if taker == "BUY" else 700_000.0,
        taker_sell_quote_volume_5m=700_000.0 if taker == "BUY" else 1_300_000.0,
        taker_buy_sell_ratio=1.857 if taker == "BUY" else 0.538,
        taker_buy_share=0.65 if taker == "BUY" else (0.35 if taker == "SELL" else 0.50),
        taker_bias=taker,
        raw_oi_first=100.0,
        raw_oi_last=102.0,
        raw_oi_change_pct=2.0,
        raw_oi_window_minutes=25,
        oi_interpretation=oi,
        funding_rate=funding,
        market_regime=regime,
        regime_ema7=101.0,
        regime_ema20=100.0,
        regime_atr14=2.0,
        regime_hh=2,
        regime_hl=2,
        regime_lh=0,
        regime_ll=0,
        regime_source_version="b27ag-swing-regime-v1",
        regime_bar_close_time_ms=1_000,
        context_errors=errors,
    )


def candidate(
    *,
    stage: str = "IGNITION",
    long_score: float = 80.0,
    short_score: float = 20.0,
    ctx: MarketContext | None = None,
) -> MovementDetection:
    return MovementDetection(
        symbol="TESTUSDT",
        detector_version="stage2-v1",
        candle_close_time_ms=1_000,
        movement_state=(
            "EARLY_MOVEMENT"
            if stage == "IGNITION"
            else "STRONG_CONTINUATION"
            if stage == "EXPANSION"
            else "LATE_MOVEMENT"
        ),
        direction_hint="UP" if long_score >= short_score else "DOWN",
        is_moving=True,
        ret_5m_pct=0.6 if long_score >= short_score else -0.6,
        ret_15m_pct=1.2 if long_score >= short_score else -1.2,
        ret_1h_pct=2.0 if long_score >= short_score else -2.0,
        ret_24h_pct=5.0 if long_score >= short_score else -5.0,
        median_abs_ret_5m_pct=0.1,
        return_expansion_ratio=4.0,
        volume_ratio=2.0,
        range_ratio=2.0,
        trades_ratio=2.0,
        directional_persistence=True,
        evidence_count=5,
        reasons=(),
        stage=stage,
        stage_classifier_version="stage3-v1",
        long_score=long_score,
        short_score=short_score,
        score_gap=long_score - short_score,
        score_edge=abs(long_score - short_score),
        direction_score_version="stage4-v1",
        market_context=ctx,
        market_context_version="stage5-v1" if ctx else None,
    )


class Stage6DecisionTests(unittest.TestCase):
    def test_aligned_ignition_becomes_long(self):
        result = decide(candidate(ctx=context()))
        self.assertEqual(result.decision, "LONG")
        self.assertEqual(result.decision_version, DECISION_VERSION)
        self.assertGreaterEqual(result.decision_context_confirmations, 2)
        self.assertGreater(result.decision_context_balance, 0)

    def test_aligned_expansion_becomes_short(self):
        result = decide(
            candidate(
                stage="EXPANSION",
                long_score=15.0,
                short_score=82.0,
                ctx=context(
                    structure="BREAKDOWN",
                    taker="SELL",
                    oi="FRESH_SHORT_PARTICIPATION",
                    regime="BEAR",
                    funding=-0.0001,
                ),
            )
        )
        self.assertEqual(result.decision, "SHORT")
        self.assertGreaterEqual(result.decision_context_confirmations, 1)

    def test_score_below_68_is_no_trade(self):
        result = decide(
            candidate(
                long_score=67.9,
                short_score=20.0,
                ctx=context(),
            )
        )
        self.assertEqual(result.decision, "NO TRADE")
        self.assertTrue(any("score_below_68" in r for r in result.decision_reasons))

    def test_edge_below_10_is_no_trade(self):
        result = decide(
            candidate(
                long_score=75.0,
                short_score=66.0,
                ctx=context(),
            )
        )
        self.assertEqual(result.decision, "NO TRADE")
        self.assertTrue(any("edge_below_10" in r for r in result.decision_reasons))

    def test_exhaustion_is_no_trade_even_with_high_scores(self):
        result = decide(
            candidate(
                stage="EXHAUSTION",
                long_score=95.0,
                short_score=5.0,
                ctx=context(),
            )
        )
        self.assertEqual(result.decision, "NO TRADE")
        self.assertIn("exhaustion_chase_risk", result.decision_reasons)

    def test_missing_required_context_is_no_trade(self):
        result = decide(candidate(ctx=None))
        self.assertEqual(result.decision, "NO TRADE")
        self.assertIn("required_context_incomplete", result.decision_reasons)

    def test_missing_funding_makes_context_incomplete(self):
        result = decide(candidate(ctx=context(funding=None)))
        self.assertEqual(result.decision, "NO TRADE")
        self.assertIn("required_context_incomplete", result.decision_reasons)

    def test_confirmed_opposite_structure_is_hard_veto(self):
        # Score says LONG, but the same closed candle confirms a breakdown.
        # Other context is deliberately supportive to prove the structure veto.
        result = decide(
            candidate(
                ctx=context(
                    structure="BREAKDOWN",
                    taker="BUY",
                    oi="FRESH_LONG_PARTICIPATION",
                    regime="BULL",
                )
            )
        )
        self.assertEqual(result.decision, "NO TRADE")
        self.assertIn("hard_structure_conflict", result.decision_reasons)

    def test_context_conflicts_can_force_no_trade(self):
        result = decide(
            candidate(
                ctx=context(
                    structure="NO_STRUCTURAL_BREAK",
                    taker="SELL",
                    oi="FRESH_SHORT_PARTICIPATION",
                    regime="BEAR",
                    volume_confirmed=True,
                )
            )
        )
        self.assertEqual(result.decision, "NO TRADE")
        self.assertLess(result.decision_context_balance, 1)

    def test_funding_does_not_act_as_standalone_direction_trigger(self):
        # Strong positive funding does not veto an otherwise aligned LONG.
        # Funding is retained as positioning context only.
        result = decide(candidate(ctx=context(funding=0.005)))
        self.assertEqual(result.decision, "LONG")
        self.assertTrue(any(r.startswith("context:funding=") for r in result.decision_reasons))


if __name__ == "__main__":
    unittest.main()
