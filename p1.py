import pandas as pd
import numpy as np
import os

# -------------------------------------------------------------
# STEP 1: PATH SETUP & DATA LOADING
# -------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

static_file_path   = os.path.join(script_dir, "Book1(companies_static).csv")
cashflow_file_path = os.path.join(script_dir, "Book2(companies_cashflow).csv")

try:
    df_equity = pd.read_csv(static_file_path)
    # thousands=',' strips Excel-style comma formatting (e.g. "1,291" -> 1291)
    df_cf     = pd.read_csv(cashflow_file_path, thousands=',')
    print("--- Both Files Loaded! ---")
except FileNotFoundError as e:
    print(f"ERROR: Could not find files. Details: {e}")
    exit()

print("\nColumns in Static file:   ", df_equity.columns.tolist())
print("Columns in Cashflow file: ", df_cf.columns.tolist())

# Strip hidden spaces from column names and Ticker
df_equity.columns = df_equity.columns.str.strip()
df_cf.columns     = df_cf.columns.str.strip()
df_equity['Ticker'] = df_equity['Ticker'].astype(str).str.strip()
df_cf['Ticker']     = df_cf['Ticker'].astype(str).str.strip()

# -------------------------------------------------------------
# COLUMN NAME MAP
# Edit the RIGHT side if your CSV uses different headers.
# -------------------------------------------------------------
COL_ROE  = 'ROE'
COL_PB   = 'P/B'
COL_DE   = 'Debt/Eq'
COL_PE   = 'P/E'
COL_EPS1 = 'EPS_Y1'
COL_EPS2 = 'EPS_Y2'
COL_EPS3 = 'EPS_Y3'

# -------------------------------------------------------------
# HELPER — force any column to numeric, coercing bad values to NaN
# Handles residual string issues not caught by thousands=','
# -------------------------------------------------------------
def force_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df

numeric_rev = ['Rev_Q1','Rev_Q2','Rev_Q3','Rev_Q4','Rev_Q5','Rev_Q6',
               'Rev_Y1','Rev_Y2','Rev_Y3']
numeric_ocf = ['OCF_Y1','OCF_Y2','OCF_Y3']
df_cf = force_numeric(df_cf, numeric_rev + numeric_ocf)

numeric_eq  = [COL_ROE, COL_PB, COL_DE, COL_PE, COL_EPS1, COL_EPS2, COL_EPS3]
df_equity   = force_numeric(df_equity, numeric_eq)

# -------------------------------------------------------------
# SHARED UTILITY — MIN-MAX SCALER
# Maps any Series to 0-100. invert=True for metrics where
# lower is better (P/E, P/B, Debt/Eq).
# -------------------------------------------------------------
def minmax_scale(series, invert=False):
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    scaled = (series - mn) / (mx - mn) * 100
    return (100 - scaled) if invert else scaled

# -------------------------------------------------------------
# STEP 2: ENGINE A — EQUITY PROFILE SCORE
#
# Weights:
#   ROE          25.00%  — elevated via DuPont structural argument
#   Debt/Eq      18.75%  — equal-weighted with remaining four
#   EPS Slope    18.75%  — equal-weighted
#   P/E          18.75%  — equal-weighted
#   P/B          18.75%  — equal-weighted
# -------------------------------------------------------------
df_equity['ROE_scaled']  = minmax_scale(df_equity[COL_ROE])
df_equity['PB_scaled']   = minmax_scale(df_equity[COL_PB],  invert=True)
df_equity['Debt_scaled'] = minmax_scale(df_equity[COL_DE],  invert=True)
df_equity['PE_scaled']   = minmax_scale(df_equity[COL_PE],  invert=True)

years = np.array([1, 2, 3])

def safe_eps_slope(row):
    try:
        vals = [float(row[COL_EPS1]), float(row[COL_EPS2]), float(row[COL_EPS3])]
        if any(pd.isna(v) for v in vals):
            return np.nan
        return np.polyfit(years, vals, 1)[0]
    except (ValueError, TypeError):
        return np.nan

df_equity['EPS_slope'] = df_equity.apply(safe_eps_slope, axis=1)

missing_slope_tickers = df_equity.loc[df_equity['EPS_slope'].isna(), 'Ticker'].tolist()
if missing_slope_tickers:
    print(f"\nNOTE — EPS slope imputed (sample median) for: {missing_slope_tickers}")
    print("       Reason: missing or non-numeric EPS history in source data.")
df_equity['EPS_slope'] = df_equity['EPS_slope'].fillna(df_equity['EPS_slope'].median())
df_equity['EPS_slope_scaled'] = minmax_scale(df_equity['EPS_slope'])

df_equity['Equity_Score'] = (
    df_equity['ROE_scaled']       * 0.2500 +
    df_equity['Debt_scaled']      * 0.1875 +
    df_equity['EPS_slope_scaled'] * 0.1875 +
    df_equity['PE_scaled']        * 0.1875 +
    df_equity['PB_scaled']        * 0.1875
)

# -------------------------------------------------------------
# STEP 3: ENGINE B — CASH FLOW STABILITY SCORE
#
# Leg 1 — Revenue Stability (50%):
#   CV of 6 quarterly revenue figures (lower CV = more stable)
#
# Leg 2 — Cash Conversion Ratio (50%):
#   3-year total OCF / 3-year total Revenue (annual figures)
#   Both legs cover the same 3-year window for consistency.
#
# NOTE: Rev Stability uses quarterly data; Cash Conversion uses
#       annual data. Periods overlap but are not identical —
#       documented as a known limitation.
# -------------------------------------------------------------
rev_cols     = ['Rev_Q1','Rev_Q2','Rev_Q3','Rev_Q4','Rev_Q5','Rev_Q6']
rev_ann_cols = ['Rev_Y1','Rev_Y2','Rev_Y3']
ocf_ann_cols = ['OCF_Y1','OCF_Y2','OCF_Y3']

# Check all expected columns exist
all_missing = ([c for c in rev_cols     if c not in df_cf.columns] +
               [c for c in rev_ann_cols if c not in df_cf.columns] +
               [c for c in ocf_ann_cols if c not in df_cf.columns])
if all_missing:
    print(f"\nWARNING — Missing cashflow columns: {all_missing}")

# ── Leg 1: Revenue Stability (quarterly CV) ───────────────────
df_cf['Rev_Mean']    = df_cf[rev_cols].mean(axis=1, skipna=True)
df_cf['Rev_Std_Dev'] = df_cf[rev_cols].std(axis=1,  skipna=True)
df_cf['Rev_CV']      = df_cf['Rev_Std_Dev'] / df_cf['Rev_Mean'].replace(0, np.nan)

missing_rev_rows = df_cf.loc[df_cf[rev_cols].isna().any(axis=1), 'Ticker'].tolist()
if missing_rev_rows:
    print(f"\nNOTE — Partial quarterly revenue for: {missing_rev_rows}")
    print("       CV computed on available quarters only.")

df_cf['Rev_Stability_Scaled'] = minmax_scale(
    df_cf['Rev_CV'].fillna(df_cf['Rev_CV'].median()), invert=True
)

# ── Leg 2: Cash Conversion Ratio (annual) ────────────────────
df_cf['Total_Rev_Annual'] = df_cf[rev_ann_cols].sum(axis=1, skipna=True)
df_cf['Total_OCF_Annual'] = df_cf[ocf_ann_cols].sum(axis=1, skipna=True)
df_cf['Cash_Conversion_Ratio'] = (
    df_cf['Total_OCF_Annual']
    / df_cf['Total_Rev_Annual'].replace(0, np.nan)
)

df_cf['Cash_Conversion_Scaled'] = minmax_scale(
    df_cf['Cash_Conversion_Ratio'].fillna(df_cf['Cash_Conversion_Ratio'].median())
)

# ── Combined Cash Flow Score ──────────────────────────────────
df_cf['Cash_Flow_Score'] = (
    df_cf['Rev_Stability_Scaled']   * 0.50 +
    df_cf['Cash_Conversion_Scaled'] * 0.50
)

# -------------------------------------------------------------
# STEP 4: MERGE & MASTER SCORE
# 60% Equity / 40% Cash Flow
# Inner join — companies missing from either file are excluded.
# -------------------------------------------------------------
df_master = pd.merge(
    df_equity[['Ticker', 'Equity_Score']],
    df_cf[['Ticker', 'Cash_Flow_Score']],
    on='Ticker', how='inner'
)
df_master['Master_Score'] = (
    df_master['Equity_Score']    * 0.60 +
    df_master['Cash_Flow_Score'] * 0.40
)
# -------------------------------------------------------------
# STEP 4.5: ENGINE INDEPENDENCE CHECK
# Are Equity_Score and Cash_Flow_Score actually measuring
# different things, or largely moving together?
# -------------------------------------------------------------
engine_corr = df_master['Equity_Score'].corr(df_master['Cash_Flow_Score'])
print("\n" + "="*70)
print("  ENGINE INDEPENDENCE CHECK")
print("="*70)
print(f"  Correlation (Equity_Score vs Cash_Flow_Score): {engine_corr:.3f}")

if abs(engine_corr) < 0.2:
    verdict = "Low correlation — engines are capturing largely independent signal."
elif abs(engine_corr) < 0.5:
    verdict = "Moderate correlation — some overlap, but engines still add distinct information."
else:
    verdict = "High correlation — engines are moving together; the 8/10 robust-pick overlap may partly reflect this rather than pure assumption-resilience."
print(f"  {verdict}")
print("="*70)

# -------------------------------------------------------------
# STEP 5: RANKED SCOREBOARD
# -------------------------------------------------------------
final_ranking = df_master.sort_values(
    'Master_Score', ascending=False
).reset_index(drop=True)
final_ranking.index += 1

print("\n" + "="*70)
print("        SME FINANCIAL HEALTH SCORER — RANKED SCOREBOARD")
print("="*70)
print(final_ranking[['Ticker','Equity_Score','Cash_Flow_Score','Master_Score']].to_string(
    formatters={
        'Equity_Score':    '{:>6.2f}'.format,
        'Cash_Flow_Score': '{:>6.2f}'.format,
        'Master_Score':    '{:>6.2f}'.format,
    }
))
print("="*70)
print(f"  Companies ranked: {len(final_ranking)}")
print("="*70)

# -------------------------------------------------------------
# STEP 6: SENSITIVITY ANALYSIS & ROBUST PICKS
# -------------------------------------------------------------
weight_combinations = [
    (0.60, 0.40, "Base Case      "),
    (0.50, 0.50, "Equal Weight   "),
    (0.70, 0.30, "Equity Heavy   "),
    (0.40, 0.60, "Cashflow Heavy "),
]

top10_per_scenario = {}
print("\n" + "="*70)
print("  SENSITIVITY ANALYSIS")
print("="*70)

for eq_w, cf_w, label in weight_combinations:
    col  = f'Score_{label.strip()}'
    df_master[col] = (
        df_master['Equity_Score']    * eq_w +
        df_master['Cash_Flow_Score'] * cf_w
    )
    top10 = df_master.nlargest(10, col)['Ticker'].tolist()
    top10_per_scenario[label.strip()] = top10
    print(f"\n  {label}({eq_w}/{cf_w})  Top 10:")
    for i, t in enumerate(top10, 1):
        print(f"    {i:>2}. {t}")

all_top10_sets = [set(v) for v in top10_per_scenario.values()]
robust_picks   = set.intersection(*all_top10_sets)

print(f"\n{'='*70}")
print(f"  ROBUST PICKS — top 10 in ALL 4 scenarios:")
if robust_picks:
    for t in sorted(robust_picks):
        print(f"    • {t}")
else:
    print("    None — no company appeared in the top 10 across all four scenarios.")
    print("    Consider reviewing top 12 overlap or checking for data gaps.")
print(f"{'='*70}")

# -------------------------------------------------------------
# STEP 7: EXPORT FULL RESULTS
# -------------------------------------------------------------
export_path = os.path.join(script_dir, "SME_Scorer_Output.csv")
df_master.sort_values('Master_Score', ascending=False).reset_index(drop=True).to_csv(
    export_path, index_label='Rank'
)
print(f"\n  Full results exported to: SME_Scorer_Output.csv")
