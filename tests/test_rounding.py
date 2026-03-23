from decimal import Decimal

import pytest

from src.rounding import (
    odoo_hours_to_minutes,
    round_up_to_10min,
    seconds_to_hours_rounded,
)


class TestRoundUpTo10Min:
    """ganbaru gym用: 10分単位切り上げテスト"""

    def test_zero_returns_zero(self):
        assert round_up_to_10min(0) == 0

    def test_one_minute_rounds_to_10(self):
        assert round_up_to_10min(1) == 10

    def test_exactly_10_stays_10(self):
        assert round_up_to_10min(10) == 10

    def test_11_rounds_to_20(self):
        assert round_up_to_10min(11) == 20

    def test_23_rounds_to_30(self):
        assert round_up_to_10min(23) == 30

    def test_30_stays_30(self):
        assert round_up_to_10min(30) == 30

    def test_31_rounds_to_40(self):
        assert round_up_to_10min(31) == 40

    def test_125_rounds_to_130(self):
        assert round_up_to_10min(125) == 130

    def test_float_minutes(self):
        """浮動小数点の分数でも正しく切り上げ"""
        assert round_up_to_10min(10.1) == 20
        assert round_up_to_10min(9.9) == 10


class TestOdooHoursToMinutes:
    """Odoo unit_amount変換テスト"""

    def test_one_hour(self):
        assert odoo_hours_to_minutes(1.0) == 60.0

    def test_half_hour(self):
        assert odoo_hours_to_minutes(0.5) == 30.0

    def test_quarter_hour(self):
        assert odoo_hours_to_minutes(0.25) == 15.0

    def test_zero(self):
        assert odoo_hours_to_minutes(0) == 0.0


class TestSecondsToHoursRounded:
    """アトラ用: 秒→時間換算（小数第2位四捨五入）テスト"""

    def test_7500_seconds(self):
        """125分 → 2.08時間"""
        assert seconds_to_hours_rounded(7500) == Decimal('2.08')

    def test_3600_seconds(self):
        """60分 → 1.00時間"""
        assert seconds_to_hours_rounded(3600) == Decimal('1.00')

    def test_5400_seconds(self):
        """90分 → 1.50時間"""
        assert seconds_to_hours_rounded(5400) == Decimal('1.50')

    def test_2700_seconds(self):
        """45分 → 0.75時間"""
        assert seconds_to_hours_rounded(2700) == Decimal('0.75')

    def test_zero_seconds(self):
        assert seconds_to_hours_rounded(0) == Decimal('0.00')

    def test_rounding_half_up(self):
        """四捨五入が正しく動作（floatの2.075問題を回避）"""
        # 2.075時間 = 7470秒
        result = seconds_to_hours_rounded(7470)
        assert result == Decimal('2.08')
