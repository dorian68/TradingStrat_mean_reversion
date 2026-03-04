from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _downsample(df: pd.DataFrame, max_points: int = 10000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = max(1, len(df) // max_points)
    return df.iloc[::step].copy()


def build_trade_report(
    price_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    output_path: Path,
    title: str = "Backtest Trade Report",
):
    if "Timestamp" in price_df.columns:
        ts = pd.to_datetime(price_df["Timestamp"], errors="coerce")
        base = price_df.assign(Timestamp=ts).dropna(subset=["Timestamp"])
    else:
        base = price_df.copy()
        base["Timestamp"] = pd.to_datetime(base.index, errors="coerce")
        base = base.dropna(subset=["Timestamp"])

    if "Close" not in base.columns:
        raise ValueError("Close column missing in price data.")

    base = base.sort_values("Timestamp")
    base = _downsample(base, max_points=12000)

    prices = {
        "t": base["Timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S%z").tolist(),
        "c": base["Close"].astype(float).tolist(),
    }

    trades = []
    if not trades_df.empty:
        for _, row in trades_df.iterrows():
            trades.append(
                {
                    "entry_time": str(row.get("entry_time")),
                    "exit_time": str(row.get("exit_time")),
                    "entry_price": float(row.get("entry_price")),
                    "exit_price": float(row.get("exit_price")),
                    "stop_price": float(row.get("stop_price")),
                    "take_price": float(row.get("take_price")),
                    "side": str(row.get("side")),
                    "exit_reason": str(row.get("exit_reason")),
                }
            )

    html = _render_html(prices, trades, title)
    output_path.write_text(html, encoding="utf-8")


def _render_html(prices: dict, trades: list, title: str) -> str:
    prices_json = json.dumps(prices, ensure_ascii=True)
    trades_json = json.dumps(trades, ensure_ascii=True)
    title_json = json.dumps(title, ensure_ascii=True)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; padding: 16px; background: #0f1115; color: #e6e6e6; }}
    h1 {{ margin: 0 0 8px 0; font-size: 20px; }}
    #controls {{ margin: 12px 0 12px 0; display: flex; gap: 8px; flex-wrap: wrap; }}
    input {{ background: #1a1e24; color: #e6e6e6; border: 1px solid #2a313c; padding: 6px 8px; border-radius: 4px; }}
    button {{ background: #2b6ef3; color: white; border: 0; padding: 6px 10px; border-radius: 4px; cursor: pointer; }}
    button.secondary {{ background: #2a313c; }}
    #chart {{ height: 720px; }}
    .hint {{ font-size: 12px; color: #b3b3b3; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="hint">Use date filters to focus on a specific period. Dates are ISO-8601, e.g. 2026-01-15T12:00:00+00:00</div>
  <div id="controls">
    <input id="start" placeholder="Start (ISO)" />
    <input id="end" placeholder="End (ISO)" />
    <button onclick="applyFilter()">Apply Filter</button>
    <button class="secondary" onclick="promptFilter()">Prompt Filter</button>
    <button class="secondary" onclick="resetFilter()">Reset</button>
  </div>
  <div id="chart"></div>

  <script>
    const prices = {prices_json};
    const trades = {trades_json};
    const title = {title_json};

    function inRange(ts, start, end) {{
      if (!start && !end) return true;
      const t = new Date(ts);
      if (start && t < start) return false;
      if (end && t > end) return false;
      return true;
    }}

    function tradeOverlaps(trade, start, end) {{
      if (!start && !end) return true;
      const entry = new Date(trade.entry_time);
      const exit = new Date(trade.exit_time);
      if (start && exit < start) return false;
      if (end && entry > end) return false;
      return true;
    }}

    function buildShapes(filteredTrades) {{
      const shapes = [];
      filteredTrades.forEach(t => {{
        shapes.push({{
          type: "line",
          x0: t.entry_time,
          x1: t.exit_time,
          y0: t.stop_price,
          y1: t.stop_price,
          line: {{ color: "#ff4d4d", width: 1, dash: "dot" }}
        }});
        shapes.push({{
          type: "line",
          x0: t.entry_time,
          x1: t.exit_time,
          y0: t.take_price,
          y1: t.take_price,
          line: {{ color: "#36d399", width: 1, dash: "dot" }}
        }});
      }});
      return shapes;
    }}

    function render(start, end) {{
      const x = [];
      const y = [];
      for (let i = 0; i < prices.t.length; i++) {{
        if (inRange(prices.t[i], start, end)) {{
          x.push(prices.t[i]);
          y.push(prices.c[i]);
        }}
      }}

      const filteredTrades = trades.filter(t => tradeOverlaps(t, start, end));
      const entryX = filteredTrades.map(t => t.entry_time);
      const entryY = filteredTrades.map(t => t.entry_price);
      const entryColors = filteredTrades.map(t => t.side === "long" ? "#36d399" : "#ff4d4d");

      const exitSL = filteredTrades.filter(t => t.exit_reason === "stop_loss");
      const exitTP = filteredTrades.filter(t => t.exit_reason === "take_profit");
      const exitOther = filteredTrades.filter(t => t.exit_reason !== "stop_loss" && t.exit_reason !== "take_profit");

      const exitXSL = exitSL.map(t => t.exit_time);
      const exitYSL = exitSL.map(t => t.exit_price);
      const exitXTP = exitTP.map(t => t.exit_time);
      const exitYTP = exitTP.map(t => t.exit_price);
      const exitXOther = exitOther.map(t => t.exit_time);
      const exitYOther = exitOther.map(t => t.exit_price);

      const traces = [
        {{
          x: x,
          y: y,
          type: "scatter",
          mode: "lines",
          name: "Close",
          line: {{ color: "#8ab4f8", width: 1.5 }}
        }},
        {{
          x: entryX,
          y: entryY,
          type: "scatter",
          mode: "markers",
          name: "Entries",
          marker: {{ color: entryColors, size: 6, opacity: 0.9 }}
        }},
        {{
          x: exitXTP,
          y: exitYTP,
          type: "scatter",
          mode: "markers",
          name: "Exit TP",
          marker: {{ color: "#36d399", size: 7, symbol: "diamond", opacity: 0.9 }}
        }},
        {{
          x: exitXSL,
          y: exitYSL,
          type: "scatter",
          mode: "markers",
          name: "Exit SL",
          marker: {{ color: "#ff4d4d", size: 7, symbol: "x", opacity: 0.9 }}
        }},
        {{
          x: exitXOther,
          y: exitYOther,
          type: "scatter",
          mode: "markers",
          name: "Exit Other",
          marker: {{ color: "#b3b3b3", size: 6, symbol: "circle-open", opacity: 0.8 }}
        }},
        {{
          x: [prices.t[0], prices.t[1] || prices.t[0]],
          y: [prices.c[0], prices.c[0]],
          type: "scatter",
          mode: "lines",
          name: "SL line",
          line: {{ color: "#ff4d4d", width: 1, dash: "dot" }},
          visible: "legendonly"
        }},
        {{
          x: [prices.t[0], prices.t[1] || prices.t[0]],
          y: [prices.c[0], prices.c[0]],
          type: "scatter",
          mode: "lines",
          name: "TP line",
          line: {{ color: "#36d399", width: 1, dash: "dot" }},
          visible: "legendonly"
        }}
      ];

      const layout = {{
        title: title,
        paper_bgcolor: "#0f1115",
        plot_bgcolor: "#0f1115",
        font: {{ color: "#e6e6e6" }},
        xaxis: {{ rangeslider: {{ visible: true }}, showgrid: false }},
        yaxis: {{ showgrid: true, gridcolor: "#1a1e24" }},
        shapes: buildShapes(filteredTrades),
        legend: {{ orientation: "h" }}
      }};

      Plotly.newPlot("chart", traces, layout, {{ responsive: true, displaylogo: false }});
    }}

    function parseInput(value) {{
      if (!value) return null;
      const d = new Date(value);
      return isNaN(d.getTime()) ? null : d;
    }}

    function applyFilter() {{
      const start = parseInput(document.getElementById("start").value);
      const end = parseInput(document.getElementById("end").value);
      render(start, end);
    }}

    function promptFilter() {{
      const startStr = prompt("Start date (ISO, optional):");
      const endStr = prompt("End date (ISO, optional):");
      document.getElementById("start").value = startStr || "";
      document.getElementById("end").value = endStr || "";
      applyFilter();
    }}

    function resetFilter() {{
      document.getElementById("start").value = "";
      document.getElementById("end").value = "";
      render(null, null);
    }}

    render(null, null);
  </script>
</body>
</html>
"""


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.2f}%"


def build_calibration_report(
    scenario_results: list[dict],
    output_path: Path,
    title: str = "Scenario Calibration Report",
    subtitle: str = "",
) -> None:
    rows_html = []
    cards_html = []

    for result in scenario_results:
        scenario = result["scenario"]
        best = result["best"]
        train = best["train_stats"]
        test = best["test_stats"]
        trade_report = result.get("artifacts", {}).get("trade_report")
        trade_link = Path(trade_report).name if trade_report else ""

        trade_html = f'<a href="{trade_link}">Report</a>' if trade_link else ""

        rows_html.append(
            "<tr>"
            f"<td>{scenario['name']}</td>"
            f"<td>{scenario['label']}</td>"
            f"<td>{scenario['start']}</td>"
            f"<td>{scenario['end']}</td>"
            f"<td>{scenario['bars']}</td>"
            f"<td>{best['score']:.3f}</td>"
            f"<td>{_fmt_pct(train.get('total_return'))}</td>"
            f"<td>{train.get('sharpe', 0.0):.2f}</td>"
            f"<td>{_fmt_pct(train.get('max_drawdown'))}</td>"
            f"<td>{_fmt_pct(train.get('win_rate'))}</td>"
            f"<td>{_fmt_pct(test.get('total_return'))}</td>"
            f"<td>{test.get('sharpe', 0.0):.2f}</td>"
            f"<td>{_fmt_pct(test.get('max_drawdown'))}</td>"
            f"<td>{_fmt_pct(test.get('win_rate'))}</td>"
            f"<td>{trade_html}</td>"
            "</tr>"
        )

        params_json = json.dumps(best["strategy_params"], indent=2, ensure_ascii=True)
        config_json = json.dumps(best["config"], indent=2, ensure_ascii=True)
        top_candidates = result.get("top_candidates", [])

        candidates_rows = []
        for cand in top_candidates:
            c_train = cand["train_stats"]
            candidates_rows.append(
                "<tr>"
                f"<td>{cand['score']:.3f}</td>"
                f"<td>{_fmt_pct(c_train.get('total_return'))}</td>"
                f"<td>{c_train.get('sharpe', 0.0):.2f}</td>"
                f"<td>{_fmt_pct(c_train.get('max_drawdown'))}</td>"
                f"<td>{_fmt_pct(c_train.get('win_rate'))}</td>"
                "</tr>"
            )

        cards_html.append(
            f"""
      <div class="card">
        <h2>{scenario['name']}</h2>
        <div class="meta">{scenario['label']} | {scenario['start']} → {scenario['end']} | Bars: {scenario['bars']}</div>
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Total Return</th>
              <th>Sharpe</th>
              <th>Max DD</th>
              <th>Win Rate</th>
              <th>Trades</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Train</td>
              <td>{_fmt_pct(train.get('total_return'))}</td>
              <td>{train.get('sharpe', 0.0):.2f}</td>
              <td>{_fmt_pct(train.get('max_drawdown'))}</td>
              <td>{_fmt_pct(train.get('win_rate'))}</td>
              <td>{train.get('trades', 0)}</td>
            </tr>
            <tr>
              <td>Test</td>
              <td>{_fmt_pct(test.get('total_return'))}</td>
              <td>{test.get('sharpe', 0.0):.2f}</td>
              <td>{_fmt_pct(test.get('max_drawdown'))}</td>
              <td>{_fmt_pct(test.get('win_rate'))}</td>
              <td>{test.get('trades', 0)}</td>
            </tr>
          </tbody>
        </table>
        <div class="links">
          {f'<a href="{trade_link}">Trade Report</a>' if trade_link else ''}
        </div>
        <details>
          <summary>Best Strategy Params</summary>
          <pre>{params_json}</pre>
        </details>
        <details>
          <summary>Best Risk Config</summary>
          <pre>{config_json}</pre>
        </details>
        <details>
          <summary>Top Candidates (Train)</summary>
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Total Return</th>
                <th>Sharpe</th>
                <th>Max DD</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {''.join(candidates_rows)}
            </tbody>
          </table>
        </details>
      </div>
"""
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; padding: 16px; background: #0f1115; color: #e6e6e6; }}
    h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
    h2 {{ margin: 0 0 6px 0; font-size: 18px; }}
    .meta {{ font-size: 12px; color: #b3b3b3; margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0 14px 0; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #2a313c; text-align: left; }}
    th {{ color: #b3b3b3; font-weight: 600; }}
    tr:hover {{ background: #1a1e24; }}
    .card {{ border: 1px solid #1f232b; background: #12161c; padding: 14px; border-radius: 10px; margin-bottom: 16px; }}
    .links a {{ color: #8ab4f8; text-decoration: none; margin-right: 12px; }}
    details {{ margin-top: 8px; }}
    summary {{ cursor: pointer; color: #8ab4f8; }}
    pre {{ background: #0b0e13; padding: 10px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">{subtitle}</div>
  <h2>Scenario Overview</h2>
  <table>
    <thead>
      <tr>
        <th>Scenario</th>
        <th>Label</th>
        <th>Start</th>
        <th>End</th>
        <th>Bars</th>
        <th>Score</th>
        <th>Train Return</th>
        <th>Train Sharpe</th>
        <th>Train Max DD</th>
        <th>Train Win</th>
        <th>Test Return</th>
        <th>Test Sharpe</th>
        <th>Test Max DD</th>
        <th>Test Win</th>
        <th>Trade Report</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
  {''.join(cards_html)}
</body>
</html>
"""

    output_path.write_text(html, encoding="utf-8")
