import argparse
import html
import json
from pathlib import Path

from .config import STRATEGY_NAME
from .offline_strategy_runner import load_csv_bars, make_context
from .strategy.registry import create_strategy


def build_chart_rows(strategy, bars):
    rows = []

    for index in range(1, len(bars) + 1):
        visible_bars = bars[:index]
        snapshot = strategy.get_snapshot(make_context(visible_bars))
        latest_bar = snapshot["latest_bar"]
        signal = snapshot["signal"]
        levels = snapshot["values"].get("levels", {})

        rows.append(
            {
                "index": index,
                "time": latest_bar.get("time", str(index)),
                "open": float(latest_bar["open"]),
                "high": float(latest_bar["high"]),
                "low": float(latest_bar["low"]),
                "close": float(latest_bar["close"]),
                "signal": signal["direction"] if signal else None,
                "reason": signal["reason"] if signal else None,
                "longLevel": levels.get("long_level"),
                "shortLevel": levels.get("short_level"),
                "atrUp": levels.get("atr_up"),
                "atrDn": levels.get("atr_dn"),
            }
        )

    return rows


def render_html(rows, title):
    payload = json.dumps(rows)
    escaped_title = html.escape(title)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      color: #1f2937;
      background: #f8fafc;
    }}
    header {{
      padding: 18px 24px 8px;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 700;
    }}
    .meta {{
      margin-top: 6px;
      color: #64748b;
      font-size: 13px;
    }}
    .wrap {{
      padding: 12px 24px 24px;
    }}
    .panel {{
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      overflow: hidden;
    }}
    svg {{
      display: block;
      width: 100%;
      height: 620px;
    }}
    .axis {{
      stroke: #cbd5e1;
      stroke-width: 1;
    }}
    .grid {{
      stroke: #e2e8f0;
      stroke-width: 1;
    }}
    .label {{
      fill: #64748b;
      font-size: 12px;
    }}
    .up {{
      stroke: #059669;
      fill: #d1fae5;
    }}
    .down {{
      stroke: #dc2626;
      fill: #fee2e2;
    }}
    .level-long {{
      stroke: #2563eb;
      stroke-width: 1.5;
      stroke-dasharray: 5 4;
      fill: none;
    }}
    .level-short {{
      stroke: #9333ea;
      stroke-width: 1.5;
      stroke-dasharray: 5 4;
      fill: none;
    }}
    .atr-up {{
      stroke: #f59e0b;
      stroke-width: 1.5;
      fill: none;
    }}
    .atr-dn {{
      stroke: #14b8a6;
      stroke-width: 1.5;
      fill: none;
    }}
    .signal {{
      fill: #111827;
      stroke: #ffffff;
      stroke-width: 2;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      padding: 12px 16px;
      border-top: 1px solid #e2e8f0;
      font-size: 13px;
      color: #475569;
    }}
    .swatch {{
      display: inline-block;
      width: 20px;
      height: 3px;
      margin-right: 6px;
      vertical-align: middle;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escaped_title}</h1>
    <div class="meta">Candles, SigHL levels, ATR trailing stop, and signal markers from offline CSV replay.</div>
  </header>
  <div class="wrap">
    <div class="panel">
      <svg id="chart" role="img" aria-label="{escaped_title}"></svg>
      <div class="legend">
        <span><span class="swatch" style="background:#2563eb"></span>Long level</span>
        <span><span class="swatch" style="background:#9333ea"></span>Short level</span>
        <span><span class="swatch" style="background:#f59e0b"></span>ATR up</span>
        <span><span class="swatch" style="background:#14b8a6"></span>ATR down</span>
        <span>● Signal</span>
      </div>
    </div>
  </div>
  <script>
    const rows = {payload};
    const svg = document.getElementById("chart");
    const width = 1200;
    const height = 620;
    const margin = {{ top: 24, right: 72, bottom: 64, left: 54 }};
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);

    const values = [];
    for (const row of rows) {{
      values.push(row.high, row.low);
      for (const key of ["longLevel", "shortLevel", "atrUp", "atrDn"]) {{
        if (row[key] !== null && row[key] !== undefined) values.push(Number(row[key]));
      }}
    }}
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const pad = Math.max((maxValue - minValue) * 0.08, 0.5);
    const yMin = minValue - pad;
    const yMax = maxValue + pad;
    const candleStep = plotWidth / Math.max(rows.length, 1);
    const candleWidth = Math.max(Math.min(candleStep * 0.58, 14), 4);

    function x(index) {{
      return margin.left + (index - 0.5) * candleStep;
    }}
    function y(value) {{
      return margin.top + (yMax - value) / (yMax - yMin) * plotHeight;
    }}
    function add(tag, attrs, text) {{
      const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      if (text !== undefined) node.textContent = text;
      svg.appendChild(node);
      return node;
    }}
    function pathFor(key) {{
      let d = "";
      for (const row of rows) {{
        const value = row[key];
        if (value === null || value === undefined) continue;
        d += `${{d ? "L" : "M"}} ${{x(row.index)}} ${{y(Number(value))}} `;
      }}
      return d.trim();
    }}

    for (let i = 0; i <= 5; i++) {{
      const value = yMin + (yMax - yMin) * i / 5;
      const py = y(value);
      add("line", {{ class: "grid", x1: margin.left, y1: py, x2: width - margin.right, y2: py }});
      add("text", {{ class: "label", x: width - margin.right + 8, y: py + 4 }}, value.toFixed(2));
    }}

    add("line", {{ class: "axis", x1: margin.left, y1: margin.top, x2: margin.left, y2: height - margin.bottom }});
    add("line", {{ class: "axis", x1: margin.left, y1: height - margin.bottom, x2: width - margin.right, y2: height - margin.bottom }});

    add("path", {{ class: "level-long", d: pathFor("longLevel") }});
    add("path", {{ class: "level-short", d: pathFor("shortLevel") }});
    add("path", {{ class: "atr-up", d: pathFor("atrUp") }});
    add("path", {{ class: "atr-dn", d: pathFor("atrDn") }});

    for (const row of rows) {{
      const cx = x(row.index);
      const isUp = row.close >= row.open;
      add("line", {{ class: isUp ? "up" : "down", x1: cx, y1: y(row.high), x2: cx, y2: y(row.low) }});
      const bodyTop = y(Math.max(row.open, row.close));
      const bodyHeight = Math.max(Math.abs(y(row.open) - y(row.close)), 1);
      add("rect", {{
        class: isUp ? "up" : "down",
        x: cx - candleWidth / 2,
        y: bodyTop,
        width: candleWidth,
        height: bodyHeight,
        rx: 1
      }});

      if (row.signal) {{
        add("circle", {{ class: "signal", cx, cy: y(row.high) - 14, r: 7 }});
        add("text", {{ class: "label", x: cx + 10, y: y(row.high) - 10 }}, row.signal);
      }}
    }}

    const labelEvery = Math.max(Math.ceil(rows.length / 8), 1);
    for (const row of rows) {{
      if ((row.index - 1) % labelEvery !== 0 && row.index !== rows.length) continue;
      add("text", {{
        class: "label",
        x: x(row.index),
        y: height - margin.bottom + 24,
        "text-anchor": "middle"
      }}, row.time);
    }}
  </script>
</body>
</html>
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate an offline strategy HTML chart from a CSV file."
    )
    parser.add_argument("csv_path", help="Path to CSV with OHLC bars")
    parser.add_argument(
        "--strategy",
        default=STRATEGY_NAME,
        help=f"Strategy name. Defaults to config STRATEGY_NAME ({STRATEGY_NAME}).",
    )
    parser.add_argument(
        "--output",
        default="data/offline_strategy_chart.html",
        help="Output HTML path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    bars = load_csv_bars(args.csv_path)

    if not bars:
        raise ValueError("CSV does not contain any bars")

    strategy = create_strategy(args.strategy)
    rows = build_chart_rows(strategy, bars)
    title = f"{args.strategy} offline chart: {Path(args.csv_path).name}"
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(rows, title), encoding="utf-8")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
