"""变化检测器：对比历史 → 算变化 → 判断告警。"""

from .base import Detector, SignalCandidate
from .price_drop import PriceDropDetector
from .review_surge import ReviewSurgeDetector
from .trend_shift import TrendShiftDetector

__all__ = [
    "Detector",
    "SignalCandidate",
    "PriceDropDetector",
    "ReviewSurgeDetector",
    "TrendShiftDetector",
]
