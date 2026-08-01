## Offline strategy runner

Run strategy logic without connecting to TWS:

```powershell
python -m backend.offline_strategy_runner data/sample_bars.csv
```

Use your own CSV with at least these columns:

```csv
time,open,high,low,close,volume
2026-06-22 09:30:00,100,101,99,100.5,1000
```

Useful modes:

```powershell
python -m backend.offline_strategy_runner data/sample_bars.csv --mode final
python -m backend.offline_strategy_runner data/sample_bars.csv --mode replay --show-all
python -m backend.offline_strategy_runner data/sample_bars.csv --strategy sig_hl_1m
```

Generate an offline HTML chart:

```powershell
python -m backend.offline_strategy_chart data/fixed_session_signal_bars.csv --output data/fixed_session_signal_chart.html
```

Generate simple 1-minute signal data:

```powershell
python data/generate_simple_1m_signal_bars.py
python -m backend.offline_strategy_runner data/simple_1m_signal_bars.csv
```

SigHL timeframe config:

```python
HISTORICAL_BAR_SIZE = "30 mins"
SIG_HL_LOOKBACK_TF = "4 hours"
```

The strategy calculates its own bars per timeframe. For example, `4 hours / 30 mins = 8` bars, and `4 hours / 1 min = 240` bars.

SigHL groups bars into fixed completed sessions using:

```python
SIG_HL_SESSION_ANCHOR = "09:30"
```
