"""
Progress analytics helpers for dashboards and reporting.

Provides:
- Mastery histograms and distribution analysis
- Summary statistics (mean, median, min, max)
- Progress visualization helpers
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple


def mastery_histogram(mastery: Dict[str, float], bin_size: int = 10) -> List[Tuple[str, int]]:
    """
    Build histogram of mastery values grouped by bins.

    Args:
        mastery: Dict mapping topics/modules to mastery scores (0-100)
        bin_size: Size of each bin (default: 10 for ranges like 0-9, 10-19, etc.)

    Returns:
        List of (bin_label, count) tuples, sorted by bin

    Example:
        >>> mastery = {"python": 85, "java": 72, "c++": 45}
        >>> mastery_histogram(mastery)
        [('40-49', 1), ('70-79', 1), ('80-89', 1)]
    """
    if not mastery:
        return []

    bins: Dict[str, int] = {}
    for value in mastery.values():
        # Clamp to [0, 100] and determine bin
        clamped = max(0.0, min(100.0, float(value)))
        bin_start = int(math.floor(clamped) // bin_size) * bin_size

        # Handle edge case: score of exactly 100 goes in 90-99 bin
        if bin_start >= 100:
            bin_start = 100 - bin_size

        bin_label = f"{bin_start}-{bin_start + bin_size - 1}"
        bins[bin_label] = bins.get(bin_label, 0) + 1

    # Sort by bin start value
    sorted_bins = sorted(bins.items(), key=lambda kv: int(kv[0].split("-")[0]))
    return sorted_bins


def mastery_summary(mastery: Dict[str, float]) -> Dict[str, float]:
    """
    Calculate summary statistics for mastery scores.

    Args:
        mastery: Dict mapping topics/modules to mastery scores (0-100)

    Returns:
        Dict with mean, median, min, max, std_dev

    Example:
        >>> mastery = {"python": 85, "java": 72, "c++": 45}
        >>> summary = mastery_summary(mastery)
        >>> summary["mean"]
        67.33
    """
    if not mastery:
        return {
            "mean": 0.0,
            "median": 0.0,
            "min": 0.0,
            "max": 0.0,
            "std_dev": 0.0,
            "count": 0,
        }

    values = sorted(mastery.values())
    n = len(values)

    # Mean
    mean_val = sum(values) / n

    # Median
    if n % 2 == 1:
        median_val = values[n // 2]
    else:
        median_val = (values[n // 2 - 1] + values[n // 2]) / 2.0

    # Standard deviation
    variance = sum((v - mean_val) ** 2 for v in values) / n
    std_dev = math.sqrt(variance)

    return {
        "mean": round(mean_val, 2),
        "median": round(median_val, 2),
        "min": round(values[0], 2),
        "max": round(values[-1], 2),
        "std_dev": round(std_dev, 2),
        "count": n,
    }


def mastery_percentile(mastery: Dict[str, float], percentile: float) -> float:
    """
    Calculate the Nth percentile of mastery scores.

    Args:
        mastery: Dict mapping topics/modules to mastery scores
        percentile: Percentile to calculate (0-100)

    Returns:
        Mastery score at the given percentile

    Example:
        >>> mastery = {"a": 10, "b": 20, "c": 30, "d": 40, "e": 50}
        >>> mastery_percentile(mastery, 75)  # 75th percentile
        40.0
    """
    if not mastery:
        return 0.0

    values = sorted(mastery.values())
    n = len(values)

    # Use linear interpolation between closest ranks
    rank = (percentile / 100.0) * (n - 1)
    lower_idx = int(math.floor(rank))
    upper_idx = int(math.ceil(rank))

    if lower_idx == upper_idx:
        return round(values[lower_idx], 2)

    # Interpolate
    fraction = rank - lower_idx
    result = values[lower_idx] + fraction * (values[upper_idx] - values[lower_idx])
    return round(result, 2)


def mastery_by_category(
    mastery: Dict[str, float],
    thresholds: Dict[str, Tuple[float, float]] = None,
) -> Dict[str, List[str]]:
    """
    Categorize topics/modules by mastery level.

    Args:
        mastery: Dict mapping topics to mastery scores
        thresholds: Custom thresholds (default: novice/beginner/intermediate/advanced/expert)

    Returns:
        Dict mapping category names to lists of topics

    Example:
        >>> mastery = {"python": 85, "java": 45, "c++": 92}
        >>> categories = mastery_by_category(mastery)
        >>> categories["expert"]
        ['c++']
    """
    if thresholds is None:
        thresholds = {
            "novice": (0.0, 50.0),
            "beginner": (50.0, 65.0),
            "intermediate": (65.0, 80.0),
            "advanced": (80.0, 90.0),
            "expert": (90.0, 100.0),
        }

    categories: Dict[str, List[str]] = {cat: [] for cat in thresholds}

    for topic, score in mastery.items():
        for category, (low, high) in thresholds.items():
            if low <= score < high or (category == "expert" and score == 100.0):
                categories[category].append(topic)
                break

    return categories


def learning_velocity(
    assessment_history: List[Dict],
    window_days: int = 7,
) -> float:
    """
    Calculate learning velocity (mastery gain per day) over recent window.

    Args:
        assessment_history: List of assessment dicts with 'timestamp' and 'score'
        window_days: Number of days to look back

    Returns:
        Average mastery points gained per day

    Note:
        Requires at least 2 assessments to calculate velocity
    """
    if len(assessment_history) < 2:
        return 0.0

    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)

    recent = [
        a
        for a in assessment_history
        if datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00")) >= cutoff
    ]

    if len(recent) < 2:
        return 0.0

    # Calculate slope of scores over time
    first_score = recent[0]["score"]
    last_score = recent[-1]["score"]
    first_time = datetime.fromisoformat(recent[0]["timestamp"].replace("Z", "+00:00"))
    last_time = datetime.fromisoformat(recent[-1]["timestamp"].replace("Z", "+00:00"))

    days_elapsed = (last_time - first_time).total_seconds() / 86400.0

    if days_elapsed == 0:
        return 0.0

    velocity = (last_score - first_score) / days_elapsed
    return round(velocity, 2)
