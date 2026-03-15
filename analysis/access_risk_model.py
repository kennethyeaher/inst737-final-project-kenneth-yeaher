import pandas as pd
from pathlib import Path 

# file path 

INPUT_FILE = Path("data/model_outputs/regression_results.csv")
OUTPUT_FILE = Path("data/model_outputs/access_risk_classified.csv")

# risk tier thresholds based on residual quartiles

RISK_TIERS = {
    "high_risk": 0.25,
    "moderate_risk": 0.50,
    "adequate": 0.75,
}

def load_regression_results() -> pd.DataFrame:
    """Load regression output with residuals."""
    print("\n[ACCESS-RISK] ===== RUNNING ACCESS RISK CLASSIFICATION =====")
 
    df = pd.read_csv(INPUT_FILE)
 
    required = {"state_name", "residual", "providers_per_100k", "predicted_provider_density"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
 
    df = df.replace([float("inf"), float("-inf")], pd.NA)
    df = df.dropna(subset=["residual"]).copy()
 
    print(f"[ACCESS-RISK] States loaded: {df.shape[0]}")
    return df

def classify_risk_tiers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign access risk labels based on residual quartile position.
    Large negative residuals indicate fewer providers than predicted.
    """
    q25 = df["residual"].quantile(RISK_TIERS["high_risk"])
    q50 = df["residual"].quantile(RISK_TIERS["moderate_risk"])
    q75 = df["residual"].quantile(RISK_TIERS["adequate"])
 
    def assign_tier(residual: float) -> str:
        if residual <= q25:
            return "high_risk"
        elif residual <= q50:
            return "moderate_risk"
        elif residual <= q75:
            return "adequate"
        return "well_served"
 
    df["risk_tier"] = df["residual"].apply(assign_tier)

    # supply gap magnitude (absolute shortfall relative to prediction)
    df["supply_gap"] = df["residual"].clip(upper=0).abs()
 
    # rank states by severity (1 = most underserved)
    df["risk_rank"] = df["residual"].rank(ascending=True, method="min").astype(int)
 
    print(f"[ACCESS-RISK] Quartile thresholds — Q25: {q25:.3f}  Q50: {q50:.3f}  Q75: {q75:.3f}")
    print(f"[ACCESS-RISK] Tier counts:\n{df['risk_tier'].value_counts().to_string()}")
 
    return df

def build_risk_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate risk tier statistics for reporting."""
    summary = (
        df.groupby("risk_tier", as_index=False)
        .agg(
            state_count=("state_name", "count"),
            avg_residual=("residual", "mean"),
            avg_density=("providers_per_100k", "mean"),
            avg_supply_gap=("supply_gap", "mean"),
        )
    )
 
    # preserve logical tier ordering
    tier_order = ["high_risk", "moderate_risk", "adequate", "well_served"]
    summary["risk_tier"] = pd.Categorical(summary["risk_tier"], categories=tier_order, ordered=True)
    summary = summary.sort_values("risk_tier").reset_index(drop=True)
 
    print(f"\n[ACCESS-RISK] Tier summary:\n{summary.to_string(index=False)}")
    return summary

def save_results(df: pd.DataFrame) -> None:
    """Save classified risk dataset."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
 
    ordered_cols = [
        "practice_state",
        "state_name",
        "provider_count",
        "metro_population",
        "providers_per_100k",
        "predicted_provider_density",
        "residual",
        "risk_tier",
        "supply_gap",
        "risk_rank",
    ]
 
    df[ordered_cols].to_csv(OUTPUT_FILE, index=False)
    print(f"\n[ACCESS-RISK] Saved → {OUTPUT_FILE}")
    print("[ACCESS-RISK] ===== CLASSIFICATION COMPLETE =====")

def run_access_risk_model() -> pd.DataFrame:
    """Full access risk classification workflow."""
    df = load_regression_results()
    df = classify_risk_tiers(df)
    build_risk_summary(df)
    save_results(df)
    return df

if __name__ == "__main__":
    run_access_risk_model()