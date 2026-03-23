import math
from decimal import Decimal, ROUND_HALF_UP


def round_up_to_10min(total_minutes: float) -> int:
    """
    分を10分単位で切り上げる（ganbaru gym用）

    Examples:
        0分    → 0分     (稼働なし)
        1分    → 10分
        10分   → 10分
        11分   → 20分
        125分  → 130分
    """
    if total_minutes == 0:
        return 0
    return math.ceil(total_minutes / 10) * 10


def odoo_hours_to_minutes(unit_amount: float) -> float:
    """Odoo unit_amount（時間単位）を分に変換"""
    return round(unit_amount * 60, 6)


def seconds_to_hours_rounded(total_seconds: float) -> Decimal:
    """
    秒を時間換算し、小数第2位で四捨五入する（アトラ用）

    Examples:
        7500秒  (125分) → Decimal('2.08')
        3600秒  (60分)  → Decimal('1.00')
        5400秒  (90分)  → Decimal('1.50')
    """
    hours = Decimal(str(total_seconds)) / Decimal('3600')
    return hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
