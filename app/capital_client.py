import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class CapitalSession:
    cst: str
    security_token: str


class CapitalClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self, session: Optional[CapitalSession] = None) -> Dict[str, str]:
        headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if session:
            headers.update({"CST": session.cst, "X-SECURITY-TOKEN": session.security_token})
        return headers

    def create_session(self, identifier: str, password: str) -> CapitalSession:
        url = f"{self.base_url}/api/v1/session"
        payload = {"identifier": identifier, "password": password}
        response = requests.post(url, headers=self._headers(), data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        cst = response.headers.get("CST")
        security_token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not security_token:
            raise RuntimeError("Missing session tokens from Capital.com response.")
        return CapitalSession(cst=cst, security_token=security_token)

    def fetch_prices(self, session: CapitalSession, epic: str, resolution: str = "MINUTE_5") -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/prices/{epic}"
        params = {"resolution": resolution, "max": 20}
        response = requests.get(url, headers=self._headers(session), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def place_order(
        self,
        session: CapitalSession,
        epic: str,
        direction: str,
        size: float,
        order_type: str = "MARKET",
        currency: str = "USD",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/positions"
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size,
            "orderType": order_type,
            "currencyCode": currency,
            "forceOpen": True,
        }
        response = requests.post(url, headers=self._headers(session), data=json.dumps(payload), timeout=10)
        response.raise_for_status()
        return response.json()
