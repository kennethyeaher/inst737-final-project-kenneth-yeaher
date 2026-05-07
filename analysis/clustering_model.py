import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from utils.logging_config import setup_logger

logger = setup_logger("ovara.clustering_model")

# file paths

INPUT_FILE = Path("data/load/access_model_dataset.csv")
OUTPUT_FILE = Path("data/model_outputs/clustering_results.csv")
SUMMARY_FILE = Path("data/model_outputs/clustering_summary.csv")
METADATA_FILE = Path("data/model_outputs/clustering_metadata.json")
PCA_PLOT_FILE = Path("data/visualizations/clustering_pca.png")

# clustering features — rate-based to keep clusters about supply archetype,
# not state size

CLUSTERING_FEATURES = [
    "providers_per_100k",
    "taxonomy_diversity",
    "recent_growth_per_100k",
    "avg_provider_enum_year",
]

K_RANGE = range(2, 7)
RANDOM_STATE = 42

# label sets keyed by k so cluster ids map to interpretable archetypes

CLUSTER_LABEL_SETS: dict[int, list[str]] = {
    2: ["low_supply", "high_supply"],
    3: ["low_supply", "mid_supply", "high_supply"],
    4: ["very_low_supply", "low_supply", "high_supply", "very_high_supply"],
    5: ["very_low_supply", "low_supply", "mid_supply", "high_supply", "very_high_supply"],
    6: ["very_low_supply", "low_supply", "below_mid_supply",
        "above_mid_supply", "high_supply", "very_high_supply"],
}


def load_clustering_data() -> pd.DataFrame:
    """load access model dataset and derive a rate-based growth feature."""
    df = pd.read_csv(INPUT_FILE)

    required = {
        "practice_state", "state_name", "providers_per_100k",
        "taxonomy_diversity", "recent_provider_growth",
        "avg_provider_enum_year", "metro_population",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    df = df.replace([float("inf"), float("-inf")], pd.NA)

    # convert raw growth count into a population-normalized rate so the
    # clustering captures growth intensity rather than state size
    df["recent_growth_per_100k"] = (
        df["recent_provider_growth"] / df["metro_population"] * 100000
    )

    before = df.shape[0]
    df = df.dropna(subset=CLUSTERING_FEATURES).copy()
    dropped = before - df.shape[0]
    if dropped > 0:
        logger.warning(f"dropped {dropped} rows with missing values")

    logger.info(f"states for clustering: {df.shape[0]}")
    return df


def select_optimal_k(X_scaled: np.ndarray) -> tuple[int, dict]:
    """sweep K_RANGE and pick the k with the highest silhouette score."""
    scores = {}
    logger.info("silhouette sweep:")
    for k in K_RANGE:
        model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = model.fit_predict(X_scaled)
        score = float(silhouette_score(X_scaled, labels))
        scores[k] = round(score, 4)
        logger.info(f"  k={k}  silhouette={score:.4f}")

    best_k = max(scores, key=scores.get)
    logger.info(f"selected k={best_k}  silhouette={scores[best_k]:.4f}")
    return best_k, scores


def fit_clusters(df: pd.DataFrame, X_scaled: np.ndarray, k: int) -> pd.DataFrame:
    """
    Fit final KMeans and relabel cluster ids by ascending mean
    providers_per_100k so cluster 1 is always the lowest-supply archetype.
    """
    model = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    raw_labels = model.fit_predict(X_scaled)

    df = df.copy()
    df["_raw_cluster"] = raw_labels

    cluster_density = (
        df.groupby("_raw_cluster")["providers_per_100k"].mean().sort_values()
    )
    rank_map = {raw: rank for rank, raw in enumerate(cluster_density.index, start=1)}
    df["cluster"] = df["_raw_cluster"].map(rank_map)
    df = df.drop(columns="_raw_cluster")

    label_names = CLUSTER_LABEL_SETS[k]
    label_map = {rank: name for rank, name in enumerate(label_names, start=1)}
    df["cluster_label"] = df["cluster"].map(label_map)

    return df


def build_cluster_summary(df: pd.DataFrame) -> pd.DataFrame:
    """per-cluster aggregate statistics with member states."""
    summary = (
        df.groupby(["cluster", "cluster_label"], as_index=False)
        .agg(
            state_count=("practice_state", "count"),
            avg_density=("providers_per_100k", "mean"),
            avg_diversity=("taxonomy_diversity", "mean"),
            avg_growth_per_100k=("recent_growth_per_100k", "mean"),
            avg_enum_year=("avg_provider_enum_year", "mean"),
            member_states=("practice_state", lambda s: ", ".join(sorted(s))),
        )
        .sort_values("cluster")
        .reset_index(drop=True)
    )
    logger.info(f"cluster summary:\n{summary.drop(columns='member_states').to_string(index=False)}")
    return summary


def render_pca_plot(df: pd.DataFrame, X_scaled: np.ndarray) -> None:
    """2D PCA scatter colored by cluster, with state-code annotations."""
    pca = PCA(n_components=2)
    coords = pca.fit_transform(X_scaled)

    palette = ["#b2182b", "#ef8a62", "#fddbc7", "#67a9cf", "#2166ac", "#053061"]

    fig, ax = plt.subplots(figsize=(11, 7))

    for cluster_id in sorted(df["cluster"].unique()):
        mask = (df["cluster"] == cluster_id).values
        label = df.loc[mask, "cluster_label"].iloc[0]
        ax.scatter(
            coords[mask, 0], coords[mask, 1],
            color=palette[(cluster_id - 1) % len(palette)],
            label=f"{cluster_id}: {label} (n={int(mask.sum())})",
            s=80, alpha=0.85, edgecolor="white", linewidth=0.8,
        )
        for x, y, name in zip(coords[mask, 0], coords[mask, 1],
                              df.loc[mask, "practice_state"].values):
            ax.annotate(name, (x, y), fontsize=7, alpha=0.65,
                        xytext=(4, 3), textcoords="offset points")

    var = pca.explained_variance_ratio_
    ax.set_xlabel(f"PC1 ({var[0]:.1%} variance)", fontsize=11, color="#475569")
    ax.set_ylabel(f"PC2 ({var[1]:.1%} variance)", fontsize=11, color="#475569")
    ax.set_title("State Supply Archetypes — K-Means clusters in PCA space",
                 fontsize=14, fontweight="bold", loc="left", pad=18)
    ax.legend(loc="best", fontsize=9, frameon=False, title="Cluster")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color("#E2E8F0")
    ax.tick_params(axis="both", colors="#94A3B8")

    PCA_PLOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(PCA_PLOT_FILE, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"saved PCA plot -> {PCA_PLOT_FILE}")


def save_results(df: pd.DataFrame, summary: pd.DataFrame,
                 k: int, scores: dict) -> None:
    """save per-state assignments, cluster summary, and metadata json."""
    output_cols = [
        "practice_state", "state_name", "cluster", "cluster_label",
        "providers_per_100k", "taxonomy_diversity",
        "recent_growth_per_100k", "avg_provider_enum_year",
    ]
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df[output_cols].to_csv(OUTPUT_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)

    metadata = {
        "selected_k": int(k),
        "silhouette_scores": scores,
        "features": CLUSTERING_FEATURES,
        "random_state": RANDOM_STATE,
        "total_states": int(df.shape[0]),
    }
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"saved clustering -> {OUTPUT_FILE}")
    logger.info(f"saved summary -> {SUMMARY_FILE}")
    logger.info(f"saved metadata -> {METADATA_FILE}")


def run_clustering_model() -> pd.DataFrame:
    """
    Full clustering workflow.
    load, scale, sweep k, fit, relabel, summarize, render PCA, save.
    """
    try:
        df = load_clustering_data()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df[CLUSTERING_FEATURES])

        best_k, scores = select_optimal_k(X_scaled)
        df = fit_clusters(df, X_scaled, best_k)
        summary = build_cluster_summary(df)

        render_pca_plot(df, X_scaled)
        save_results(df, summary, best_k, scores)
        return df

    except FileNotFoundError:
        logger.error(f"input file not found: {INPUT_FILE}")
        raise

    except ValueError as e:
        logger.error(f"data validation failed: {e}")
        raise

    except Exception as e:
        logger.error(f"unexpected error during clustering: {e}")
        raise


if __name__ == "__main__":
    run_clustering_model()
