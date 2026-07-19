# RISK DISCLOSURE

ApexSignal F1 is a **research and paper-trading** project. Read this before interpreting
any output.

1. **Not financial advice.** Nothing produced by this system is a recommendation to buy,
   sell, or hold any contract, security, or asset. Allocations are **simulated** for
   research and are labeled *"Model-ranked simulated allocation."*
2. **No live-money execution.** The default and only supported execution paths are paper
   accounting, a local synthetic market, and the Kalshi **demo** environment. Real-money
   trading is not implemented. `ENABLE_LIVE_TRADING=false` is enforced.
3. **Models can be wrong.** Probabilities are estimates with uncertainty. Calibration can
   drift with rule changes, upgrades, weather, and small samples. Rare events
   (safety cars, DNFs) are especially uncertain.
4. **Markets carry real risk.** Prediction markets can be illiquid, wide, fast-moving, and
   can settle against you. Fees and slippage erode edge. Past calibration does not
   guarantee future results.
5. **Data & news can mislead.** Timing/telemetry gaps, mismapped markets, rumor vs.
   confirmation, and extraction errors all propagate. The system deliberately returns
   *"No qualifying opportunity"* when uncertainty, liquidity, or edge thresholds fail.
6. **Jurisdiction.** Prediction-market access is restricted in some jurisdictions
   (e.g., Polymarket lists the US as blocked). This project stays read-only there and does
   **not** bypass any geographic or platform controls.
7. **Independent project.** Not affiliated with Formula 1, the FIA, any constructor,
   Kalshi, Polymarket, or Akuna Capital.

Use it to learn, not to bet.
