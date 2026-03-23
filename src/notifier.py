import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def notify(message: str, level: str = "info"):
    """
    エラー/完了通知をSlackに送信
    SLACK_WEBHOOK_URL 環境変数が未設定の場合はログのみ
    """
    log_func = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
    }.get(level, logger.info)
    log_func(message)

    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return

    color = {
        "info": "#36a64f",
        "warning": "#ff9900",
        "error": "#ff0000",
    }.get(level, "#36a64f")

    payload = {
        "attachments": [{
            "color": color,
            "title": f"[請求書生成] {level.upper()}",
            "text": message,
            "footer": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }]
    }

    try:
        requests.post(webhook_url, json=payload, timeout=10)
    except Exception as e:
        logger.error("Slack通知の送信に失敗しました: %s", e)
