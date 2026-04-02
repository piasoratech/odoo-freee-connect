import logging
from datetime import datetime, timedelta

from src.rounding import odoo_hours_to_minutes, round_up_to_10min

logger = logging.getLogger(__name__)


class GanbaruGymBuilder:
    """ganbaru gym 請求書ビルダー"""

    def __init__(self, odoo_client, freee_client, mappings: dict):
        self.odoo = odoo_client
        self.freee = freee_client
        self.mappings = mappings

    def build(self, year: int, month: int, dry_run: bool = False) -> dict:
        """
        ganbaru gymの請求書データを構築し、freeeにドラフト作成

        Returns:
            結果サマリーの辞書
        """
        odoo_cfg = self.mappings["odoo"]
        freee_cfg = self.mappings["freee"]
        partner_name = odoo_cfg["partners"]["ganbaru_gym"]["name"]
        project_name = odoo_cfg["projects"]["ganbaru_gym_spot"]["project_name"]

        # 月末日の計算
        if month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1) - timedelta(days=1)
        last_day_str = last_day.strftime("%Y-%m-%d")

        # 1. 固定費の明細を構築（mappings.yamlから）
        fixed_lines_cfg = odoo_cfg["sale_order_lines"]["ganbaru_gym"]
        invoice_lines = []
        fixed_total = 0

        for line_cfg in fixed_lines_cfg:
            if "fixed_price" in line_cfg:
                invoice_lines.append({
                    "description": line_cfg["product_name"],
                    "unit_price": line_cfg["fixed_price"],
                    "quantity": 1,
                    "account_item_id": freee_cfg["account_items"]["service_fee"]["account_item_id"],
                    "tax_code": freee_cfg["tax_codes"]["taxable_10pct"],
                })
                fixed_total += line_cfg["fixed_price"]

        # 2. タイムシートからスポット稼働分を集計
        timesheets = self.odoo.get_timesheets(
            project_name, year, month, last_day_str
        )

        total_minutes_raw = sum(
            odoo_hours_to_minutes(ts["unit_amount"])
            for ts in timesheets
        )
        billed_minutes = round_up_to_10min(total_minutes_raw)
        spot_amount = billed_minutes * 50

        logger.info(
            "ganbaru gym: タイムシート %d件 / 合計%.1f分 → 繰上%d分",
            len(timesheets), total_minutes_raw, billed_minutes,
        )

        # スポット稼働がある場合のみ明細に追加
        if billed_minutes > 0:
            invoice_lines.append({
                "description": f"スポットHP作業費 {billed_minutes}分",
                "unit_price": 50,
                "quantity": billed_minutes,
                "account_item_id": freee_cfg["account_items"]["spot_work"]["account_item_id"],
                "tax_code": freee_cfg["tax_codes"]["taxable_10pct"],
            })

        total_amount = fixed_total + spot_amount

        result = {
            "partner": partner_name,
            "fixed_total": fixed_total,
            "timesheet_count": len(timesheets),
            "total_minutes_raw": total_minutes_raw,
            "billed_minutes": billed_minutes,
            "spot_amount": spot_amount,
            "total_amount": total_amount,
            "invoice_lines": invoice_lines,
            "freee_invoice_id": None,
        }

        if dry_run:
            logger.info(
                "[DRY-RUN] ganbaru gym 請求書: ¥%s", total_amount
            )
            return result

        # 3. freeeに請求書ドラフト作成
        issue_date = last_day_str
        due_date = (
            last_day + timedelta(
                days=freee_cfg["invoice"]["payment_term_days"]
            )
        ).strftime("%Y-%m-%d")
        title = freee_cfg["invoice"]["title_templates"]["ganbaru_gym"].format(
            year=year, month=month
        )

        freee_result = self.freee.create_invoice_draft(
            partner_id=freee_cfg["partners"]["ganbaru_gym"]["partner_id"],
            issue_date=issue_date,
            due_date=due_date,
            title=title,
            lines=invoice_lines,
        )
        result["freee_invoice_id"] = freee_result.get(
            "invoice", {}
        ).get("id")

        return result
