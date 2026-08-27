# Personal Net Worth Tracker

Local-only Flask application. No SQL database. Your data is stored in `data.json`; API settings are stored in `settings.json`.

## Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Docker

```bash
docker compose up -d --build
```

## What it tracks

- Crypto: quantity + average USD buy price + current CoinGecko price
- Indian stocks: NSE/BSE + quantity + average INR buy price
- US stocks: ticker + quantity + average USD buy price
- Mutual funds: MFapi scheme code + units + purchase NAV
- Bank balances
- Gold
- Property/land
- Other assets
- Loans and other liabilities
- Saved net-worth snapshots

Net worth = assets - liabilities.

## Market sources

Crypto uses CoinGecko's public API. Indian and US stocks use Yahoo Finance's public chart endpoint by default, with optional Twelve Data support. Indian mutual-fund NAV uses MFapi.in. USD/INR conversion uses Frankfurter.

Market APIs are best-effort and may have delays/rate limits. This is a personal valuation dashboard, not a trading system.

## Security

The server binds to `127.0.0.1` only. Keep it that way for personal use. Do not expose it to the internet without adding authentication and HTTPS.

Back up `data.json` regularly.
