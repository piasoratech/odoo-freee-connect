#!/usr/bin/env python3
"""
月次請求書自動生成スクリプト

Odoo・Clockifyからデータを取得し、freee上に請求書ドラフトを自動生成する。
"""
import argparse
import logging
import os
import sys
from datetime import datetime
import yaml
from dotenv import load_dotenv

from src.builders.atra import AtraBuilder
from src.builders.ganbaru_gym import GanbaruGymBuilder
from src.clockify_client import ClockifyClient
from src.freee_client import FreeeClient
from src.notifier import notify
from src.odoo_client import OdooClient

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_mappings(path: str = "config/mappings.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def parse_args():
    parser = argparse.ArgumentParser(
        description="月次請求書生成スクリプト"
    )
    parser.add_argument(
        "--month",
        type=str,
        default="prev",
        help="対象月: 'prev'(前月), または 'YYYY-MM' 形式",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="freeeへの書き込みをスキップする",
    )
    return parser.parse_args()


def resolve_month(month_arg: str) -> tuple[int, int]:
    """引数から対象年月を解決する"""
    if month_arg == "prev":
        today = datetime.now()
        if today.month == 1:
            return today.year - 1, 12
        return today.year, today.month - 1
    parts = month_arg.split("-")
    return int(parts[0]), int(parts[1])


def main():
    args = parse_args()
    load_dotenv()

    year, month = resolve_month(args.month)
    dry_run = args.dry_run

    logger.info(
        "=== 月次請求書生成スクリプト %d年%d月分 %s===",
        year, month, "[DRY-RUN] " if dry_run else "",
    )

    mappings = load_mappings()

    try:
        # --- Odoo接続 ---
        odoo = OdooClient(
            url=os.environ["ODOO_URL"],
            db=os.environ["ODOO_DB"],
            username=os.environ["ODOO_USERNAME"],
            api_key=os.environ["ODOO_API_KEY"],
        )
        odoo.authenticate()
        logger.info("Odoo接続 OK")

        # --- Clockify接続 ---
        clockify = ClockifyClient(
            api_key=os.environ["CLOCKIFY_API_KEY"],
            workspace_id=mappings["clockify"]["workspace_id"],
        )
        logger.info("Clockify接続準備 OK")

        # --- freee接続 ---
        freee = FreeeClient(
            client_id=os.environ["FREEE_CLIENT_ID"],
            client_secret=os.environ["FREEE_CLIENT_SECRET"],
            company_id=int(os.environ["FREEE_COMPANY_ID"]),
        )
        freee.refresh_token()
        logger.info("freee接続 OK")

        # --- ganbaru gym 請求書 ---
        gym_builder = GanbaruGymBuilder(odoo, freee, mappings)
        gym_result = gym_builder.build(year, month, dry_run=dry_run)
        logger.info(
            "ganbaru gym: 固定費¥%s + スポット¥%s = 合計¥%s%s",
            gym_result["fixed_total"],
            gym_result["spot_amount"],
            gym_result["total_amount"],
            f" (freee ID: {gym_result['freee_invoice_id']})"
            if gym_result["freee_invoice_id"] else "",
        )

        # --- アトラ 請求書 ---
        atra_builder = AtraBuilder(clockify, freee, mappings)
        atra_result = atra_builder.build(year, month, dry_run=dry_run)
        logger.info(
            "アトラ: %s時間 × ¥%s = 合計¥%s%s",
            atra_result["billed_hours"],
            atra_result["unit_price"],
            atra_result["total_amount"],
            f" (freee ID: {atra_result['freee_invoice_id']})"
            if atra_result["freee_invoice_id"] else "",
        )

        # --- 完了通知 ---
        summary = (
            f"{year}年{month}月分 請求書生成完了\n"
            f"・ganbaru gym: ¥{gym_result['total_amount']:,}\n"
            f"・アトラ: ¥{atra_result['total_amount']:,}\n"
            f"{'[DRY-RUN] ' if dry_run else ''}"
            f"freeeで請求書を確認・送付してください"
        )
        logger.info("=== 完了 ===")
        notify(summary, level="info")

    except Exception as e:
        error_msg = f"請求書生成エラー: {e}"
        logger.error(error_msg, exc_info=True)
        notify(error_msg, level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
