import logging
from datetime import datetime, timedelta

from src.rounding import seconds_to_hours_rounded

logger = logging.getLogger(__name__)


class AtraBuilder:
    """アトラ請求書ビルダー"""

    def __init__(self, clockify_client, freee_client, mappings: dict):
        self.clockify = clockify_client
        self.freee = freee_client
        self.mappings = mappings

    def build(self, year: int, month: int, dry_run: bool = False) -> dict:
        """
        アトラの請求書データを構築し、freeeにドラフト作成

        Returns:
            結果サマリーの辞書
        """
        clockify_cfg = self.mappings["clockify"]
        odoo_cfg = self.mappings["odoo"]
        freee_cfg = self.mappings["freee"]

        project_id = clockify_cfg["projects"]["atra"]["project_id"]
        unit_price = odoo_cfg["sale_order_lines"]["atra"][0]["unit_price"]

        # 月末日の計算
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        last_day_str = last_day.strftime("%Y-%m-%d")

        # 1. Clockifyから時間エントリを取得
        entries = self.clockify.get_time_entries(
            project_id, year, month, last_day_str
        )

        # 2. 合計秒数を算出
        total_seconds = self.clockify.sum_duration_seconds(entries)

        # 3. 時間換算（小数第2位で四捨五入）
        billed_hours = seconds_to_hours_rounded(total_seconds)
        atra_amount = int(billed_hours * unit_price)

        logger.info(
            "アトラ: エントリ %d件 / 合計%.0f秒 → %s時間",
            len(entries), total_seconds, billed_hours,
        )

        invoice_lines = [{
            "description": f"システム開発支援 {billed_hours}時間",
            "unit_price": unit_price,
            "quantity": float(billed_hours),
            "account_item_id": freee_cfg["account_items"]["service_fee"]["account_item_id"],
            "tax_code": freee_cfg["tax_codes"]["taxable_10pct"],
        }]

        result = {
            "partner": "アトラ",
            "entry_count": len(entries),
            "total_seconds": total_seconds,
            "billed_hours": str(billed_hours),
            "unit_price": unit_price,
            "total_amount": atra_amount,
            "invoice_lines": invoice_lines,
            "freee_invoice_id": None,
        }

        if dry_run:
            logger.info(
                "[DRY-RUN] アトラ 請求書: ¥%s", atra_amount
            )
            return result

        # 4. freeeに請求書ドラフト作成
        issue_date = last_day_str
        due_date = (
            last_day + timedelta(
                days=freee_cfg["invoice"]["payment_term_days"]
            )
        ).strftime("%Y-%m-%d")
        title = freee_cfg["invoice"]["title_template"].format(
            year=year, month=month
        )

        freee_result = self.freee.create_invoice_draft(
            partner_id=freee_cfg["partners"]["atra"]["partner_id"],
            issue_date=issue_date,
            due_date=due_date,
            title=title,
            lines=invoice_lines,
        )
        result["freee_invoice_id"] = freee_result.get(
            "invoice", {}
        ).get("id")

        return result
