#!/usr/bin/env python3
"""
freeeトークンを定期的にリフレッシュするスクリプト

freeeのリフレッシュトークンは長期間使われないと無効化されるため、
このスクリプトをcronで毎日実行してトークンを生かしておく。
"""
import logging
import os
import sys

from dotenv import load_dotenv

from src.freee_client import FreeeClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    try:
        freee = FreeeClient(
            client_id=os.environ["FREEE_CLIENT_ID"],
            client_secret=os.environ["FREEE_CLIENT_SECRET"],
            company_id=int(os.environ["FREEE_COMPANY_ID"]),
        )
        freee.refresh_token()
        logger.info("freeeトークンの更新に成功しました")
    except Exception as e:
        logger.error("freeeトークンの更新に失敗: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
