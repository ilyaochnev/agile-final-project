import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalConfig:
    api_key: str
    identifier: str
    password: str
    demo: bool
    dry_run: bool
    base_url: str


def load_config() -> CapitalConfig:
    api_key = os.getenv("CAPITAL_API_KEY", "").strip()
    identifier = os.getenv("CAPITAL_IDENTIFIER", "").strip()
    password = os.getenv("CAPITAL_PASSWORD", "").strip()
    demo = os.getenv("CAPITAL_DEMO", "true").lower() == "true"
    dry_run = os.getenv("CAPITAL_DRY_RUN", "true").lower() == "true"
    base_url = (
        "https://demo-api-capital.backend-capital.com"
        if demo
        else "https://api-capital.backend-capital.com"
    )

    if not api_key or not identifier or not password:
        raise ValueError(
            "Missing credentials. Set CAPITAL_API_KEY, CAPITAL_IDENTIFIER, and CAPITAL_PASSWORD."
        )

    return CapitalConfig(
        api_key=api_key,
        identifier=identifier,
        password=password,
        demo=demo,
        dry_run=dry_run,
        base_url=base_url,
    )
