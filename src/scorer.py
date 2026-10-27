"""Multi-criteria real estate location scoring engine (PropScore 0-100)."""

import numpy as np
import geopandas as gpd

from src.config import CATEGORIES, score_to_grade


def _decay_curve(walk_mins: np.ndarray, ideal_mins: float, max_mins: float) -> np.ndarray:
    """
    Smooth logistic/cosine decay curve mapping walking time (minutes) to a 0-100 score.
    - <= ideal_mins: 95 to 100 pts
    - == max_mins: ~15 pts
    - > max_mins * 1.4: approaches 0 pts
    """
    scores = np.zeros_like(walk_mins, dtype=np.float64)
    for i, t in enumerate(walk_mins):
        if t <= ideal_mins:
            # 95 - 100 range for very close amenities
            ratio = max(0.0, t / max(ideal_mins, 0.5))
            scores[i] = 100.0 - 5.0 * ratio
        elif t <= max_mins:
            # Smooth cosine decay from 95 down to 20
            progress = (t - ideal_mins) / (max_mins - ideal_mins)
            scores[i] = 20.0 + 75.0 * (0.5 * (1.0 + np.cos(np.pi * progress)))
        else:
            # Tail decay below 20
            over = (t - max_mins) / max_mins
            scores[i] = max(0.0, 20.0 * np.exp(-2.0 * over))
    return np.round(scores, 1)


def compute_propscores(bldg_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Compute category sub-scores, overall PropScore (0-100), and letter grades."""
    gdf = bldg_gdf.copy()
    weighted_sum = np.zeros(len(gdf), dtype=np.float64)

    for cat_key, cfg in CATEGORIES.items():
        mins_col = f"{cat_key}_walk_min"
        score_col = f"{cat_key}_score"
        walk_mins = gdf[mins_col].values.astype(np.float64)
        sub_scores = _decay_curve(walk_mins, cfg.ideal_walk_mins, cfg.max_walk_mins)
        gdf[score_col] = sub_scores
        weighted_sum += sub_scores * cfg.weight

    # Variety bonus (up to +5 points if surrounded by rich variety of POIs within 10 mins)
    poi_counts = gdf.get("poi_count_10min", 0).values.astype(np.float64)
    variety_bonus = np.minimum(5.0, poi_counts * 0.35)

    overall = np.clip(np.round(weighted_sum + variety_bonus, 1), 0.0, 100.0)
    gdf["propscore"] = overall

    grades = []
    labels = []
    for s in overall:
        g, lbl = score_to_grade(float(s))
        grades.append(g)
        labels.append(lbl)

    gdf["grade"] = grades
    gdf["grade_label"] = labels

    return gdf
