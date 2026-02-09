# Capital.com Trading Bot Starter

This project provides a minimal Python app that connects to the Capital.com REST API, fetches recent prices, and makes a basic moving-average trade decision. It is designed as a safe starter template, with a dry-run mode enabled by default.

## Features
- Authenticates with Capital.com using the session API.
- Pulls recent prices for a specified epic.
- Applies a simple moving-average crossover strategy.
- Supports dry-run mode to avoid placing real orders.

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and populate it with your Capital.com credentials.

## Usage
Run the bot with the desired epic:

```bash
python -m app.main --epic US100 --size 1
```

## Safety
- `CAPITAL_DRY_RUN=true` (default) will prevent real orders.
- Set `CAPITAL_DEMO=true` to use the Capital.com demo environment.
- Review the strategy logic in `app/bot.py` before using this in production.

## Next Steps
- Add risk management (stop-loss, take-profit).
- Add logging and observability.
- Expand the strategy to use more robust indicators.
