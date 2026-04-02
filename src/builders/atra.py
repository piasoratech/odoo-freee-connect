import logging
from collections import defaultdict
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
        Clockifyのプロジェクト単位で請求明細を分ける

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

        # 1. Clockifyからプロジェクト一覧と時間エントリを取得
        project_map = self.clockify.get_projects()
        entries = self.clockify.get_time_entries(
            project_id, year, month, last_day_str
        )

        # 2. プロジェクトIDごとに秒数を集計
        seconds_by_project = defaultdict(float)
        for entry in entries:
            pid = entry.get("projectId") or "__no_project__"
            duration_str = entry.get("timeInterval", {}).get("duration")
            if duration_str:
                import isodate
                seconds_by_project[pid] += isodate.parse_duration(
                    duration_str
                ).total_seconds()

        # 3. プロジェクトごとに請求明細を生成
        invoice_lines = []
        total_amount = 0
        project_summaries = []

        for pid, secs in sorted(seconds_by_project.items()):
            project_name = project_map.get(pid, "未分類") if pid != "__no_project__" else "未分類"
            billed_hours = seconds_to_hours_rounded(secs)
            amount = int(billed_hours * unit_price)
            total_amount += amount

            invoice_lines.append({
                "description": f"{project_name} {billed_hours}時間",
                "unit_price": unit_price,
                "quantity": float(billed_hours),
                "account_item_id": freee_cfg["account_items"]["service_fee"]["account_item_id"],
                "tax_code": freee_cfg["tax_codes"]["taxable_10pct"],
            })
            project_summaries.append(
                f"{project_name}: {billed_hours}h → ¥{amount:,}"
            )
            logger.info(
                "アトラ [%s]: %.0f秒 → %s時間 ¥%d",
                project_name, secs, billed_hours, amount,
            )

        total_seconds = sum(seconds_by_project.values())
        logger.info(
            "アトラ合計: エントリ %d件 / %d件のプロジェクト / 合計¥%d",
            len(entries), len(invoice_lines), total_amount,
        )

        result = {
            "partner": "アトラ",
            "entry_count": len(entries),
            "total_seconds": total_seconds,
            "project_summaries": project_summaries,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "invoice_lines": invoice_lines,
            "freee_invoice_id": None,
        }

        if dry_run:
            logger.info(
                "[DRY-RUN] アトラ 請求書: ¥%d (%d明細)",
                total_amount, len(invoice_lines),
            )
            return result

        # 4. freeeに請求書ドラフト作成
        issue_date = last_day_str
        due_date = (
            last_day + timedelta(
                days=freee_cfg["invoice"]["payment_term_days"]
            )
        ).strftime("%Y-%m-%d")
        title = freee_cfg["invoice"]["title_templates"]["atra"].format(
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
