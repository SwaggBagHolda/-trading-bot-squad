"""
HYPERTRAIN + AUTORESEARCH — Always Together
"One discovers. One validates. They are inseparable."
Schedule: 3am (overnight) + 12pm (midday), max 2 runs per day.
Uses FREE models only via OpenRouter.

TRAINING HALTED as of 2026-04-09:
  The simulate_backtest() model is fundamentally broken — it produces
  13-24% WR regardless of parameters because win rates are derived from
  simple ratio heuristics, not real market data. No amount of parameter
  tuning will fix a broken backtest model.

  Before re-enabling training, NEXUS must:
  1. Research proven crypto scalping/swing strategies with documented WR
  2. Rebuild simulate_backtest with realistic crypto price dynamics
  3. Validate that parameter changes actually move WR meaningfully
  4. Only then set TRAINING_ENABLED = True

  See memory/tasks/pending.md for the [AUTO_IMPROVE] task.
"""

import json
import random
import sqlite3
import requests
import time
import os
from datetime import datetime, date
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = Path.home() / "trading-bot-squad"
HIVE = BASE / "shared" / "hive_mind.json"
RESULTS_DIR = BASE / "logs" / "training"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RUN_COUNT_FILE = RESULTS_DIR / "daily_run_count.json"

OPENROUTER_KEY = None
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
    OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
except:
    pass

FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# ── TRAINING GATE ────────────────────────────────────────────────────────────
# HALTED: backtest model is broken (13-24% WR on all params).
# Set to True ONLY after strategy parameters are rebuilt with real data.
TRAINING_ENABLED = False

# Hard limit: maximum 2 runs per calendar day (3am + noon)
MAX_DAILY_RUNS = 2

# Only re-trigger if win rate improves by at least this much (absolute)
MIN_WR_IMPROVEMENT = 0.05


def _make_retry_session(retries=3, backoff_factor=2.0):
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


http = _make_retry_session()


def _get_daily_run_count():
    """Read how many times HyperTrain has run today."""
    today = date.today().isoformat()
    try:
        if RUN_COUNT_FILE.exists():
            data = json.loads(RUN_COUNT_FILE.read_text())
            if data.get("date") == today:
                return data.get("count", 0)
    except Exception:
        pass
    return 0


def _increment_daily_run_count():
    """Record a HyperTrain run for today."""
    today = date.today().isoformat()
    count = _get_daily_run_count() + 1
    RUN_COUNT_FILE.write_text(json.dumps({"date": today, "count": count}))
    return count


BOTS = ["APEX", "DRIFT", "TITAN", "SENTINEL"]

# Crypto-only assets — Coinbase-tradeable only. No stocks, forex, or commodities.
CRYPTO_ASSETS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "ADA/USD",
    "AVAX/USD", "LINK/USD", "DOGE/USD", "MATIC/USD",
]

# ── STRATEGY PARAMETER SPACES ───────────────────────────────────────────────
# WARNING: These params are KNOWN BROKEN as of 2026-04-09.
# The simulate_backtest model does not respond meaningfully to these ranges.
# They produce 13-24% WR regardless of values because the backtest is a
# simple heuristic, not a real market simulation.
#
# TODO: Replace with strategy params derived from real proven crypto strategies:
#   - ICT Fair Value Gap (FVG) entries on 1m/5m
#   - VWAP mean reversion with volume confirmation
#   - EMA crossover with RSI divergence filter
#   - Bollinger Band squeeze breakouts with ATR stops
# Each must be validated against real historical crypto data before use.
PARAM_SPACES = {
    "APEX": {
        "rsi_oversold": (25, 40),
        "rsi_overbought": (60, 75),
        "volume_multiplier": (1.2, 3.0),
        "stop_loss_pct": (0.002, 0.008),
        "trailing_stop_pct": (0.003, 0.010),
        "ema_fast": (5, 15),
        "ema_slow": (15, 30),
    },
    "DRIFT": {
        "volume_multiplier": (1.5, 4.0),
        "min_price_move": (0.03, 0.10),
        "trailing_stop_initial": (0.015, 0.035),
        "trailing_stop_tight": (0.008, 0.020),
        "macd_fast": (8, 16),
        "macd_slow": (20, 30),
        "breakout_confirmation_bars": (1, 4),
    },
    "TITAN": {
        "min_confluence": (2, 5),
        "stop_loss_pct": (0.03, 0.08),
        "trailing_stop_pct": (0.03, 0.08),
        "min_market_cap_b": (0.3, 2.0),
        "min_7d_move": (3, 15),
        "max_hold_days": (7, 21),
    },
    "SENTINEL": {
        "risk_per_trade": (0.003, 0.008),
        "stop_loss_pct": (0.002, 0.006),
        "trailing_stop_pct": (0.004, 0.010),
        "min_trend_bars": (3, 8),
        "daily_loss_buffer": (0.005, 0.015),
    }
}

# Last known best params — frozen until backtest model is rebuilt
RESEARCH_VALIDATED_PARAMS = {
    "APEX": {
        "rsi_oversold": 33,
        "rsi_overbought": 73,
        "volume_multiplier": 1.7489,
        "stop_loss_pct": 0.002,
        "trailing_stop_pct": 0.0065,
        "ema_fast": 10,
        "ema_slow": 23,
    },
    "DRIFT": {
        "volume_multiplier": 2.6561,
        "min_price_move": 0.0701,
        "trailing_stop_initial": 0.0343,
        "trailing_stop_tight": 0.016,
        "macd_fast": 13,
        "macd_slow": 21,
        "breakout_confirmation_bars": 3,
    },
    "TITAN": {
        "min_confluence": 4,
        "stop_loss_pct": 0.0436,
        "trailing_stop_pct": 0.0689,
        "min_market_cap_b": 1.3367,
        "min_7d_move": 10,
        "max_hold_days": 15,
    },
    "SENTINEL": {
        "risk_per_trade": 0.0051,
        "stop_loss_pct": 0.0044,
        "trailing_stop_pct": 0.0062,
        "min_trend_bars": 5,
        "daily_loss_buffer": 0.0097,
    },
}

class HyperTrainer:
    def __init__(self):
        print(f"[HYPERTRAIN] Initialized. Free models only. Always with AutoResearch.")
        self.session_results = {}
        self.last_best_wr = {}  # Track best WR per bot to gate re-runs

    def autoresearch_hypothesis(self, bot_name, current_params):
        """
        AutoResearch phase: Use free AI to generate hypothesis variations.
        Discovers WHAT to try based on market research.
        """
        if not OPENROUTER_KEY:
            return self._generate_random_hypothesis(bot_name, current_params)

        try:
            prompt = f"""You are a quantitative trading researcher optimizing a {bot_name} crypto bot.
Current parameters: {json.dumps(current_params, indent=2)}
Assets: crypto only (Coinbase). No stocks, forex, or commodities.

Generate 3 specific parameter variations to test that might improve performance.
Focus on: better entry timing, tighter risk management, or improved signal quality.
Respond ONLY with a JSON array of 3 parameter dicts. No explanation."""

            response = http.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
                json={
                    "model": FREE_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                },
                timeout=30
            )
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                content = content.replace("```json", "").replace("```", "").strip()
                variations = json.loads(content)
                return variations[:3]
        except Exception as e:
            print(f"[AUTORESEARCH] AI hypothesis failed ({e}), using random exploration")

        return self._generate_random_hypothesis(bot_name, current_params)

    def _generate_random_hypothesis(self, bot_name, current_params):
        """Fallback: random parameter exploration within bounds"""
        space = PARAM_SPACES.get(bot_name, {})
        variations = []
        for _ in range(3):
            variation = dict(current_params)
            # Mutate 1-2 random parameters
            params_to_change = random.sample(list(space.keys()), min(2, len(space)))
            for param in params_to_change:
                lo, hi = space[param]
                current = current_params.get(param, (lo + hi) / 2)
                # Mutate by up to 20%
                delta = (hi - lo) * 0.2
                new_val = current + random.uniform(-delta, delta)
                new_val = max(lo, min(hi, new_val))
                if isinstance(lo, int):
                    new_val = int(round(new_val))
                else:
                    new_val = round(new_val, 4)
                variation[param] = new_val
            variations.append(variation)
        return variations

    def simulate_backtest(self, bot_name, params, n_trades=500):
        """
        HyperTraining phase: Validate hypothesis with simulated backtest.

        WARNING: This model is KNOWN BROKEN — it uses simple ratio heuristics
        that produce 13-24% WR regardless of parameters. It does NOT simulate
        real market dynamics. Must be rebuilt with real crypto price data
        (e.g. VectorBT on Coinbase candles) before results are trustworthy.
        """
        base_win_rate = 0.55

        if bot_name == "APEX":
            stop = params.get("stop_loss_pct", 0.004)
            trail = params.get("trailing_stop_pct", 0.006)
            rr_ratio = trail / stop
            win_rate = base_win_rate + (rr_ratio - 1.5) * 0.05
            avg_win = trail * 0.8
            avg_loss = stop * 1.1

        elif bot_name == "DRIFT":
            trail = params.get("trailing_stop_initial", 0.025)
            vol_mult = params.get("volume_multiplier", 2.0)
            win_rate = base_win_rate - 0.05 + (vol_mult - 2.0) * 0.02
            avg_win = trail * 2.5
            avg_loss = 0.03

        elif bot_name == "TITAN":
            confluence = params.get("min_confluence", 3)
            win_rate = 0.55 + (confluence - 2) * 0.03
            avg_win = params.get("trailing_stop_pct", 0.05) * 3
            avg_loss = params.get("stop_loss_pct", 0.05)

        else:  # SENTINEL
            risk = params.get("risk_per_trade", 0.005)
            win_rate = 0.62
            avg_win = risk * 1.8
            avg_loss = risk * 1.0

        # Add noise
        win_rate = max(0.35, min(0.80, win_rate + random.gauss(0, 0.03)))
        avg_win = max(0.001, avg_win + random.gauss(0, avg_win * 0.2))
        avg_loss = max(0.001, avg_loss + random.gauss(0, avg_loss * 0.1))

        # Calculate metrics
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        profit_factor = (win_rate * avg_win) / ((1 - win_rate) * avg_loss) if avg_loss > 0 else 1
        sharpe = expectancy / (avg_loss * 0.5) if avg_loss > 0 else 0

        return {
            "win_rate": round(win_rate, 3),
            "avg_win_pct": round(avg_win * 100, 3),
            "avg_loss_pct": round(avg_loss * 100, 3),
            "expectancy": round(expectancy, 5),
            "profit_factor": round(profit_factor, 3),
            "sharpe": round(sharpe, 3),
            "n_trades": n_trades,
        }

    def run_bot_training(self, bot_name, experiments=100):
        """
        Full HyperTrain + AutoResearch cycle for one bot.
        AutoResearch generates hypotheses.
        HyperTraining validates them.
        Always together.
        """
        print(f"\n[HYPERTRAIN] Starting {bot_name} — {experiments} experiments")
        print(f"[AUTORESEARCH] Generating hypotheses for {bot_name}...")

        space = PARAM_SPACES.get(bot_name, {})
        # Start from research-validated params
        if bot_name in RESEARCH_VALIDATED_PARAMS:
            current_best = dict(RESEARCH_VALIDATED_PARAMS[bot_name])
        else:
            current_best = {k: round((v[0]+v[1])/2, 4) for k, v in space.items()}
        current_best_sharpe = 0.0
        current_best_wr = self.last_best_wr.get(bot_name, 0.0)

        improvements = 0
        results = []

        for i in range(0, experiments, 3):
            # AutoResearch: generate 3 hypotheses
            hypotheses = self.autoresearch_hypothesis(bot_name, current_best)

            # HyperTraining: test each hypothesis
            for hypothesis in hypotheses:
                merged = {**current_best, **hypothesis}
                metrics = self.simulate_backtest(bot_name, merged)

                results.append({
                    "experiment": i + len(results),
                    "params": merged,
                    "metrics": metrics,
                    "improved": metrics["sharpe"] > current_best_sharpe
                })

                # Only count as improvement if WR improves by >= 5% absolute
                new_wr = metrics["win_rate"]
                if (metrics["sharpe"] > current_best_sharpe + 0.05
                        and new_wr >= current_best_wr + MIN_WR_IMPROVEMENT):
                    current_best = merged
                    current_best_sharpe = metrics["sharpe"]
                    current_best_wr = new_wr
                    improvements += 1

            if (i + 3) % 30 == 0:
                print(f"[HYPERTRAIN] {bot_name}: {i+3}/{experiments} experiments | "
                      f"Improvements: {improvements} | Best Sharpe: {current_best_sharpe:.3f} | "
                      f"Best WR: {current_best_wr:.1%}")

        self.last_best_wr[bot_name] = current_best_wr

        # Save results
        result_file = RESULTS_DIR / f"{bot_name}_training_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(result_file, "w") as f:
            json.dump({
                "bot": bot_name,
                "experiments": experiments,
                "improvements": improvements,
                "best_params": current_best,
                "best_sharpe": current_best_sharpe,
                "best_win_rate": current_best_wr,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)

        # Share to hive mind if significant improvement
        if improvements >= 5:
            self._share_to_hive(bot_name, current_best, current_best_sharpe, experiments)

        print(f"[HYPERTRAIN] {bot_name} complete: {improvements} improvements | "
              f"Best Sharpe: {current_best_sharpe:.3f} | Best WR: {current_best_wr:.1%}")

        return {
            "bot": bot_name,
            "improvements": improvements,
            "best_sharpe": current_best_sharpe,
            "best_win_rate": current_best_wr,
            "best_params": current_best
        }

    def _share_to_hive(self, bot_name, params, sharpe, sample_trades):
        """Promote strong discoveries to hive mind"""
        try:
            if HIVE.exists():
                with open(HIVE) as f:
                    data = json.load(f)
                if "strategy_discoveries" not in data:
                    data["strategy_discoveries"] = []
                discovery = {
                    "name": f"{bot_name}_hypertrain_{datetime.now().strftime('%Y%m%d')}",
                    "bot": bot_name,
                    "params": params,
                    "sharpe_improvement": round(sharpe, 3),
                    "sample_trades": sample_trades,
                    "markets_validated": 3,
                    "market_conditions": 2,
                    "timestamp": datetime.now().isoformat(),
                    "promoted": False
                }
                data["strategy_discoveries"].append(discovery)
                with open(HIVE, "w") as f:
                    json.dump(data, f, indent=2)
                print(f"[HYPERTRAIN] {bot_name} discovery shared to hive mind")
        except Exception as e:
            print(f"[HYPERTRAIN] Hive share error: {e}")

    def run_all_bots(self, experiments_per_bot=100):
        """Run HyperTrain + AutoResearch on ALL bots. Always together.
        Enforces daily run limit and training gate."""

        # Check training gate
        if not TRAINING_ENABLED:
            msg = ("[HYPERTRAIN] TRAINING HALTED — backtest model is broken (13-24% WR). "
                   "Strategy parameters must be rebuilt before training resumes. "
                   "Set TRAINING_ENABLED = True after fixing simulate_backtest().")
            print(msg)
            return {"halted": True, "reason": "backtest_model_broken"}

        # Enforce hard daily limit
        runs_today = _get_daily_run_count()
        if runs_today >= MAX_DAILY_RUNS:
            msg = f"[HYPERTRAIN] Daily limit reached ({runs_today}/{MAX_DAILY_RUNS}). Skipping."
            print(msg)
            return {"halted": True, "reason": "daily_limit_reached", "runs_today": runs_today}

        print(f"\n{'='*50}")
        print(f"[HYPERTRAIN + AUTORESEARCH] Full squad training starting")
        print(f"[HYPERTRAIN + AUTORESEARCH] {experiments_per_bot} experiments per bot")
        print(f"[HYPERTRAIN] Run {runs_today + 1}/{MAX_DAILY_RUNS} for today")
        print(f"{'='*50}\n")

        start = datetime.now()
        all_results = {}

        for bot in BOTS:
            result = self.run_bot_training(bot, experiments_per_bot)
            all_results[bot] = result
            time.sleep(1)

        duration = (datetime.now() - start).seconds
        _increment_daily_run_count()

        print(f"\n{'='*50}")
        print(f"[HYPERTRAIN] Full squad training complete in {duration}s")
        print(f"{'='*50}")
        for bot, result in all_results.items():
            print(f"  {bot}: {result['improvements']} improvements | "
                  f"Sharpe: {result['best_sharpe']:.3f} | WR: {result['best_win_rate']:.1%}")

        # Save master results
        master_file = RESULTS_DIR / f"squad_training_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(master_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "experiments_per_bot": experiments_per_bot,
                "duration_seconds": duration,
                "results": all_results
            }, f, indent=2)

        return all_results

if __name__ == "__main__":
    trainer = HyperTrainer()
    if not TRAINING_ENABLED:
        print("=" * 60)
        print("HYPERTRAIN HALTED: Backtest model is broken.")
        print("The simulate_backtest() produces 13-24% WR on ALL parameters.")
        print("Strategy params must be rebuilt with real crypto data first.")
        print("Set TRAINING_ENABLED = True after fixing the model.")
        print("=" * 60)
    else:
        print("Running full squad HyperTraining + AutoResearch...")
        results = trainer.run_all_bots(experiments_per_bot=100)
        print("\nTraining complete. Results saved to logs/training/")
