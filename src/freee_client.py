import json
import logging
import time
from functools import wraps
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TOKEN_FILE = Path(".freee_token.json")


def retry(max_attempts=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError,
                        requests.ConnectionError,
                        requests.Timeout) as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait = backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
        return wrapper
    return decorator


class FreeeClient:
    BASE_URL = "https://api.freee.co.jp"
    INVOICE_BASE_URL = "https://api.freee.co.jp/iv"
    TOKEN_URL = "https://accounts.secure.freee.co.jp/public_api/token"

    def __init__(self, client_id: str, client_secret: str,
                 company_id: int, token_file: Path = TOKEN_FILE):
        self.client_id = client_id
        self.client_secret = client_secret
        self.company_id = company_id
        self.token_file = token_file
        self.access_token = None
        self._load_token()

    def _load_token(self):
        """保存済みトークンを読み込む"""
        if self.token_file.exists():
            with open(self.token_file) as f:
                data = json.load(f)
            self.access_token = data.get("access_token")
            self._refresh_token_value = data.get("refresh_token")
            logger.info("freeeトークンをファイルから読み込みました")
        else:
            logger.warning(
                "freeeトークンファイルが見つかりません: %s",
                self.token_file
            )
            self.access_token = None
            self._refresh_token_value = None

    def _save_token(self, token_data: dict):
        """トークンをファイルに保存"""
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        self.access_token = token_data["access_token"]
        self._refresh_token_value = token_data["refresh_token"]
        logger.info("freeeトークンを保存しました")

    def refresh_token(self):
        """リフレッシュトークンでアクセストークンを更新"""
        if not self._refresh_token_value:
            raise RuntimeError(
                "freeeリフレッシュトークンがありません。"
                "初回OAuth認証を実行してください。"
            )
        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self._refresh_token_value,
        }, timeout=30)
        resp.raise_for_status()
        token_data = resp.json()
        self._save_token(token_data)
        logger.info("freeeトークンを更新しました")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @retry()
    def _request(self, method: str, path: str,
                 base_url: str = None, **kwargs) -> dict:
        """API呼び出し（認証エラー時にトークン自動更新）"""
        url = f"{base_url or self.BASE_URL}{path}"
        resp = requests.request(
            method, url,
            headers=self._headers(),
            timeout=30,
            **kwargs
        )
        if resp.status_code == 401:
            logger.info("freeeトークン期限切れ、自動更新します")
            self.refresh_token()
            resp = requests.request(
                method, url,
                headers=self._headers(),
                timeout=30,
                **kwargs
            )
        resp.raise_for_status()
        return resp.json()

    def create_invoice_draft(self, partner_id: int,
                             issue_date: str,
                             due_date: str,
                             title: str,
                             lines: list) -> dict:
        """
        freeeに請求書ドラフトを作成

        Args:
            partner_id: freee取引先ID
            issue_date: 請求日 (YYYY-MM-DD)
            due_date: 支払期限 (YYYY-MM-DD)
            title: 請求書タイトル
            lines: 明細行リスト
                [{"description": str, "unit_price": int,
                  "quantity": float, "account_item_id": int,
                  "tax_code": int}, ...]
        """
        invoice_lines = []
        for line in lines:
            invoice_lines.append({
                "description": line["description"],
                "unit_price": str(line["unit_price"]),
                "quantity": float(line["quantity"]),
                "tax_rate": 10,
                "account_item_id": line["account_item_id"],
                "tax_code": line["tax_code"],
            })

        payload = {
            "company_id": self.company_id,
            "partner_id": partner_id,
            "partner_title": "御中",
            "billing_date": issue_date,
            "issue_date": issue_date,
            "payment_date": due_date,
            "subject": title,
            "memo": " ",
            "lines": invoice_lines,
            "tax_entry_method": "out",
            "tax_fraction": "round",
            "withholding_tax_entry_method": "out",
        }

        result = self._request(
            "POST", "/invoices",
            base_url=self.INVOICE_BASE_URL,
            json=payload
        )
        invoice_id = result.get("invoice", {}).get("id")
        logger.info("freee請求書ドラフト作成 (ID: %s)", invoice_id)
        return result
