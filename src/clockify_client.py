import logging
import time
from functools import wraps
from typing import Optional

import isodate
import requests

logger = logging.getLogger(__name__)


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


class ClockifyClient:
    BASE_URL = "https://api.clockify.me/api/v1"

    def __init__(self, api_key: str, workspace_id: str):
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self.workspace_id = workspace_id
        self._user_id: Optional[str] = None

    def get_user_id(self) -> str:
        """APIキーに紐づくユーザーIDを取得（キャッシュ）"""
        if self._user_id:
            return self._user_id
        resp = requests.get(
            f"{self.BASE_URL}/user",
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        self._user_id = resp.json()["id"]
        logger.info("Clockify user_id: %s", self._user_id)
        return self._user_id

    @retry()
    def get_time_entries(self, project_id: Optional[str],
                         year: int, month: int,
                         last_day: str) -> list:
        """当月時間エントリをページネーション対応で全件取得。
        project_idがNoneの場合はワークスペース全体を取得。
        """
        user_id = self.get_user_id()
        entries = []
        page = 1
        start = f"{year}-{month:02d}-01T00:00:00Z"
        end = f"{last_day}T23:59:59Z"

        while True:
            params = {
                "start": start,
                "end": end,
                "page": page,
                "page-size": 200,
            }
            if project_id:
                params["project"] = project_id

            resp = requests.get(
                f"{self.BASE_URL}/workspaces/{self.workspace_id}"
                f"/user/{user_id}/time-entries",
                headers=self.headers,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                break
            entries.extend(data)
            page += 1

        logger.info(
            "Clockify時間エントリ取得 (%d件)", len(entries)
        )
        return entries

    @retry()
    def get_projects(self) -> dict:
        """ワークスペースのプロジェクト一覧を {project_id: project_name} で返す"""
        resp = requests.get(
            f"{self.BASE_URL}/workspaces/{self.workspace_id}/projects",
            headers=self.headers,
            params={"page-size": 200},
            timeout=30,
        )
        resp.raise_for_status()
        return {p["id"]: p["name"] for p in resp.json()}

    @staticmethod
    def sum_duration_seconds(entries: list) -> float:
        """エントリリストの合計秒数を算出"""
        total = 0.0
        for entry in entries:
            duration_str = entry.get("timeInterval", {}).get("duration")
            if duration_str:
                total += isodate.parse_duration(
                    duration_str
                ).total_seconds()
        return total
