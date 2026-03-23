from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.builders.atra import AtraBuilder
from src.builders.ganbaru_gym import GanbaruGymBuilder


SAMPLE_MAPPINGS = {
    "odoo": {
        "partners": {
            "ganbaru_gym": {"name": "ganbaru gym", "partner_id": 42},
            "atra": {"name": "アトラ", "partner_id": 57},
        },
        "projects": {
            "ganbaru_gym_spot": {
                "project_name": "ganbaru gymスポットHP",
                "project_id": 12,
            },
        },
        "sale_order_lines": {
            "ganbaru_gym": [
                {
                    "product_name": "HP運用保守ライトプラン",
                    "product_id": 101,
                    "fixed_price": 3000,
                },
                {
                    "product_name": "サイト制作費分割",
                    "product_id": 102,
                    "fixed_price": 2000,
                },
            ],
            "atra": [
                {
                    "product_name": "システム開発支援",
                    "product_id": 203,
                    "unit_price": 5000,
                },
            ],
        },
    },
    "clockify": {
        "workspace_id": "ws123",
        "projects": {
            "atra": {"project_id": "proj456", "name": "アトラ案件"},
        },
    },
    "freee": {
        "company_id": 1234567,
        "partners": {
            "ganbaru_gym": {
                "partner_code": "GANBARU001",
                "partner_id": 8765,
            },
            "atra": {
                "partner_code": "ATRA001",
                "partner_id": 8766,
            },
        },
        "account_items": {
            "service_fee": {
                "name": "売上高",
                "account_item_id": 1001,
            },
            "spot_work": {
                "name": "売上高（スポット）",
                "account_item_id": 1002,
            },
        },
        "tax_codes": {"taxable_10pct": 3, "tax_free": 0},
        "invoice": {
            "payment_term_days": 30,
            "title_template": "{year}年{month}月分 業務委託費",
        },
    },
}


class TestGanbaruGymBuilder:
    def _make_builder(self, timesheets=None):
        odoo = MagicMock()
        freee = MagicMock()
        odoo.get_timesheets.return_value = timesheets or []
        freee.create_invoice_draft.return_value = {
            "invoice": {"id": 12345}
        }
        return GanbaruGymBuilder(odoo, freee, SAMPLE_MAPPINGS), odoo, freee

    def test_fixed_only_no_spot(self):
        """スポット稼働なし → 固定費のみ"""
        builder, odoo, freee = self._make_builder(timesheets=[])
        result = builder.build(2026, 2, dry_run=True)

        assert result["fixed_total"] == 5000
        assert result["billed_minutes"] == 0
        assert result["spot_amount"] == 0
        assert result["total_amount"] == 5000
        assert len(result["invoice_lines"]) == 2

    def test_with_spot_work(self):
        """スポット稼働あり → 固定費+スポット費"""
        timesheets = [
            {"unit_amount": 0.5, "date": "2026-02-10",
             "name": "作業1", "task_id": [1, "task"]},
            {"unit_amount": 0.25, "date": "2026-02-15",
             "name": "作業2", "task_id": [2, "task"]},
        ]
        builder, odoo, freee = self._make_builder(timesheets=timesheets)
        result = builder.build(2026, 2, dry_run=True)

        # 0.5h + 0.25h = 0.75h = 45分 → 10分切り上げ → 50分
        assert result["total_minutes_raw"] == 45.0
        assert result["billed_minutes"] == 50
        assert result["spot_amount"] == 2500  # 50分 × ¥50
        assert result["total_amount"] == 7500  # ¥5000 + ¥2500
        assert len(result["invoice_lines"]) == 3  # 固定2 + スポット1

    def test_creates_freee_invoice_when_not_dry_run(self):
        """dry_run=False時にfreee APIが呼ばれる"""
        builder, odoo, freee = self._make_builder(timesheets=[])
        result = builder.build(2026, 2, dry_run=False)

        freee.create_invoice_draft.assert_called_once()
        assert result["freee_invoice_id"] == 12345

    def test_rounding_23_minutes(self):
        """23分 → 30分に繰り上げ"""
        timesheets = [
            {"unit_amount": 23 / 60, "date": "2026-02-10",
             "name": "作業", "task_id": [1, "task"]},
        ]
        builder, odoo, freee = self._make_builder(timesheets=timesheets)
        result = builder.build(2026, 2, dry_run=True)

        assert result["billed_minutes"] == 30
        assert result["spot_amount"] == 1500


class TestAtraBuilder:
    def _make_builder(self, entries=None, total_seconds=0.0):
        clockify = MagicMock()
        freee = MagicMock()
        clockify.get_time_entries.return_value = entries or []
        clockify.sum_duration_seconds.return_value = total_seconds
        freee.create_invoice_draft.return_value = {
            "invoice": {"id": 12346}
        }
        return AtraBuilder(clockify, freee, SAMPLE_MAPPINGS), clockify, freee

    def test_basic_calculation(self):
        """基本的な時間計算"""
        builder, clockify, freee = self._make_builder(
            entries=[{"id": 1}], total_seconds=7500,
        )
        result = builder.build(2026, 2, dry_run=True)

        # 7500秒 = 125分 = 2.0833...h → 2.08h
        assert result["billed_hours"] == "2.08"
        assert result["total_amount"] == 10400  # 2.08 × ¥5000
        assert result["unit_price"] == 5000

    def test_exact_hour(self):
        """ちょうど1時間"""
        builder, clockify, freee = self._make_builder(
            entries=[{"id": 1}], total_seconds=3600,
        )
        result = builder.build(2026, 2, dry_run=True)

        assert result["billed_hours"] == "1.00"
        assert result["total_amount"] == 5000

    def test_90_minutes(self):
        """90分 → 1.50時間"""
        builder, clockify, freee = self._make_builder(
            entries=[{"id": 1}], total_seconds=5400,
        )
        result = builder.build(2026, 2, dry_run=True)

        assert result["billed_hours"] == "1.50"
        assert result["total_amount"] == 7500

    def test_creates_freee_invoice_when_not_dry_run(self):
        """dry_run=False時にfreee APIが呼ばれる"""
        builder, clockify, freee = self._make_builder(
            entries=[], total_seconds=3600,
        )
        result = builder.build(2026, 2, dry_run=False)

        freee.create_invoice_draft.assert_called_once()
        assert result["freee_invoice_id"] == 12346

    def test_zero_hours(self):
        """稼働0時間"""
        builder, clockify, freee = self._make_builder(
            entries=[], total_seconds=0,
        )
        result = builder.build(2026, 2, dry_run=True)

        assert result["billed_hours"] == "0.00"
        assert result["total_amount"] == 0
