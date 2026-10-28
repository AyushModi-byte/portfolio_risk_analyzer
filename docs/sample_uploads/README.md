# Sample uploads for the live demo

Illustrative holdings, not real positions. All symbols are in the bundled price snapshot, so they
also work when Yahoo Finance is down.

| File | What it shows |
| --- | --- |
| `demo_portfolio.csv` | Full upload: 9 NSE and 3 US stocks, with exchange and currency. Goes straight to the dashboard (INR/USD conversion, sectors, drawdown, correlations). |
| `demo_broker_export.csv` | Broker-style headers (`Instrument`, `Qty.`, `Avg. cost`, `LTP`), auto-detected. India only. |
| `demo_mapping_needed.csv` | Headers the parser cannot guess (`Scrip`, `Units Held`, `Cost per Unit (Rs)`), so the column-mapping dialog opens. |
