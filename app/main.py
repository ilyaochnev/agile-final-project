import argparse
import json
import sys

from app.bot import execute_trade
from app.capital_client import CapitalClient
from app.config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capital.com trading bot")
    parser.add_argument("--epic", required=True, help="Capital.com market epic")
    parser.add_argument("--size", type=float, default=1.0, help="Trade size")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    client = CapitalClient(base_url=config.base_url, api_key=config.api_key)
    session = client.create_session(identifier=config.identifier, password=config.password)
    result = execute_trade(
        client=client,
        session=session,
        epic=args.epic,
        trade_size=args.size,
        dry_run=config.dry_run,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
