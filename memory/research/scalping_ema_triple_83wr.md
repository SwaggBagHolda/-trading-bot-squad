# EMA Triple + RSI + MACD Histogram Scalping Strategy
# Date: 2026-04-09 | Source: DavidDTech Medium | Confidence: HIGH

## Finding
83% documented win rate scalping strategy using triple EMA alignment (9/55/200),
RSI midline filter (51/49), and MACD histogram divergence on 5-minute candles.

## Data
- Win Rate: 83% (documented by author)
- Risk:Reward: 1:2
- Timeframe: 5-minute candles
- MACD histogram checked on 1-minute interval

## Exact Rules
### Indicators
- EMA 9 (fast)
- EMA 55 (medium)
- EMA 200 (slow/trend)
- RSI 14, thresholds: long >51, short <49
- MACD histogram with Bollinger Bands overlay (larger-than-average bar = signal)

### LONG Entry
1. EMA 9 > EMA 55 > EMA 200 (bullish alignment)
2. RSI > 51
3. MACD histogram red bar larger than average (reversal signal)

### SHORT Entry
1. EMA 9 < EMA 55 < EMA 200 (bearish alignment)
2. RSI < 49
3. MACD histogram green bar larger than average

### Exit
- 1:2 risk-reward ratio
- Stop: recent swing low/high
- Take profit: 2x stop distance

## Application
APEX scalper — upgrade from EMA 9/21 to EMA 9/55/200 triple alignment.
Add RSI midline filter. Keep existing FVG signal as secondary.

## Source
https://daviddtech.medium.com/83-win-rate-5-minute-ultimate-scalping-trading-strategy-89c4e89fb364

## Also Found (HyperTrain internal)
- ETH/USD mean_reversion 4h: 68.92% WR, 74 trades, Sharpe 1.46
  Source: sentinel_winners.json (internal backtest on Coinbase OHLCV)
