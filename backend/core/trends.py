"""
Trend calculation utilities.
Centralized logic for computing metric variations.
"""
from typing import Optional, Dict, Any
from enum import Enum


class TrendDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


def calculate_trend(current: Optional[float], previous: Optional[float]) -> Dict[str, Any]:
    """
    Calculate trend between two metric values.

    Args:
        current: Current metric value
        previous: Previous metric value

    Returns:
        Dict with value (absolute change), direction, and percent change
    """
    if current is None or previous is None or previous == 0:
        return {"value": 0, "direction": TrendDirection.STABLE, "percent": 0.0}

    diff = current - previous
    percent = (diff / abs(previous)) * 100

    if diff > 0:
        direction = TrendDirection.UP
    elif diff < 0:
        direction = TrendDirection.DOWN
    else:
        direction = TrendDirection.STABLE

    return {
        "value": round(diff, 2),
        "direction": direction,
        "percent": round(percent, 2)
    }


def parse_download_count(downloads_str: Optional[str]) -> int:
    """
    Parse Play Store download string to numeric value.

    Examples:
        "1 000 000+" -> 1_000_000
        "10M+" -> 10_000_000
        "500K+" -> 500_000
    """
    if not downloads_str:
        return 0

    # Remove various separators: regular space, narrow no-break space, non-breaking space
    clean = downloads_str.replace("+", "").replace(" ", "").replace("\u202f", "").replace("\u00a0", "").replace(",", "").replace(".", "").strip()

    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

    for suffix, multiplier in multipliers.items():
        if clean.upper().endswith(suffix):
            try:
                return int(float(clean[:-1]) * multiplier)
            except ValueError:
                return 0

    try:
        return int(clean)
    except ValueError:
        return 0
