import pandas as pd
import numpy as np
import os

# -------------------------------------------------------------
# STEP 1: PATH SETUP & DATA LOADING
# -------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

static_file_path = os.path.join(script_dir, "Book1(companies_static).csv")
cashflow_file_path = os.path.join(script_dir, "Book2(companies_cashflow).csv")

try:
    df_equity = pd.read_csv(static_file_path)
    df_cf = pd.read_csv(cashflow_file_path)
    print("--- Both Files Loaded! ---")
except FileNotFoundError as e:
    print(f"ERROR: Could not find files. Details: {e}")
    exit()

# *** DIAGNOSTIC STEP — prints your actual column names so you can verify ***
print("\nColumns in Static file:", df_equity.columns.tolist())
print("Columns in Cashflow file:", df_cf.columns.tolist())

# Strip hidden spaces from all column names AND the Ticker column
df_equity.columns = df_equity.columns.str.strip()
df_cf.columns = df_cf.columns.str.strip()
df_equity['Ticker'] = df_equity['Ticker'].astype(str).str.strip()
df_cf['Ticker'] = df_cf['Ticker'].astype(str).str.strip()

# -------------------------------------------------------------
# COLUMN NAME MAP — Edit these if your CSV uses different names
# After running once, check the diagnostic output above and
# adjust the RIGHT side of each line to match your actual headers
# -------------------------------------------------------------
COL_ROE        = 'ROE'           # e.g. could be 'ROE(%)' in your file
COL_PB         = 'P/B'           # FIXED: was 'P_B', slashes are common
COL_DE         = 'Debt/Equity'   # could also be 'D/E'
COL_PE         = 'P/E'           # could also be 'PE'
COL_EPS1       = 'EPS_Y1'
COL_EPS2       = 'EPS_Y2'
COL_EPS3       = 'EPS_Y3'

# -------------------------------------------------------------
# STEP 2: ENGINE A — EQUITY PROFILE SCORE
# -------------------------------------------------------------
def minmax_scale(series, invert=False):
    """Scale a pandas Series to 0-100. Set invert=True for metrics
    where lower is better (like P/E, Debt/Equity, P/B)."""
    mn, mx = series.min(), series.max()
    if mx == mn:   # all values identical — give everyone 50
        return pd.Series([50.0] * len(series), index=series.index)
    scaled = (series - mn) / (mx - mn) * 100
    return (100 - scaled) if invert else scaled

df_equity['ROE_scaled']   = minmax_scale(df_equity[COL_ROE])
df_equity['PB_scaled']    = minmax_scale(df_equity[COL_PB],  invert=True)
df_equity['Debt_scaled']  = minmax_scale(df_equity[COL_DE],  invert=True)
df_equity['PE_scaled']    = minmax_scale(df_equity[COL_PE],  invert=True)

years = np.array([1, 2, 3])
df_equity['EPS_slope'] = df_equity.apply(
    lambda row: np.polyfit(
        years,
        [row[COL_EPS1], row[COL_EPS2], row[COL_EPS3]],
        1
    )[0],
    axis=1
)
df_equity['EPS_slope_scaled'] = minmax_scale(df_equity['EPS_slope'])

df_equity['Equity_Score'] = (
    df_equity['ROE_scaled']       * 0.30 +
    df_equity['Debt_scaled']      * 0.25 +
    df_equity['EPS_slope_scaled'] * 0.25 +
    df_equity['PE_scaled']        * 0.20
)

# -------------------------------------------------------------
# STEP 3: ENGINE B — CASH FLOW STABILITY SCORE
# -------------------------------------------------------------
rev_cols = ['Rev_Q1', 'Rev_Q2', 'Rev_Q3', 'Rev_Q4', 'Rev_Q5', 'Rev_Q6']
cf_cols  = ['OCF_Q1', 'OCF_Q2', 'OCF_Q3', 'OCF_Q4', 'OCF_Q5', 'OCF_Q6']

# Check all expected columns actually exist
missing_rev = [c for c in rev_cols if c not in df_cf.columns]
missing_cf  = [c for c in cf_cols  if c not in df_cf.columns]
if missing_rev or missing_cf:
    print(f"\nWARNING — Missing cashflow columns: {missing_rev + missing_cf}")
    print("Update rev_cols / cf_cols above to match your actual headers.")

# Revenue Coefficient of Variation (lower = more stable)
df_cf['Rev_Mean']    = df_cf[rev_cols].mean(axis=1)
df_cf['Rev_Std_Dev'] = df_cf[rev_cols].std(axis=1)
df_cf['Rev_CV']      = df_cf['Rev_Std_Dev'] / df_cf['Rev_Mean'].replace(0, np.nan)
df_cf['Rev_Stability_Scaled'] = minmax_scale(df_cf['Rev_CV'].fillna(0), invert=True)

# Cash Conversion Efficiency
df_cf['Total_Rev'] = df_cf[rev_cols].sum(axis=1)
df_cf['Total_OCF'] = df_cf[cf_cols].sum(axis=1)
df_cf['Cash_Conversion_Ratio'] = df_cf['Total_OCF'] / df_cf['Total_Rev'].replace(0, np.nan)
df_cf['Cash_Conversion_Scaled'] = minmax_scale(df_cf['Cash_Conversion_Ratio'].fillna(0))

df_cf['Cash_Flow_Score'] = (
    df_cf['Rev_Stability_Scaled']   * 0.50 +
    df_cf['Cash_Conversion_Scaled'] * 0.50
)

# -------------------------------------------------------------
# STEP 4: MERGE & MASTER SCORE (60/40 as per project spec)
# -------------------------------------------------------------
df_master = pd.merge(
    df_equity[['Ticker', 'Equity_Score']],
    df_cf[['Ticker', 'Cash_Flow_Score']],
    on='Ticker'
)
df_master['Master_Score'] = (
    df_master['Equity_Score']    * 0.60 +
    df_master['Cash_Flow_Score'] * 0.40
)

# -------------------------------------------------------------
# STEP 5: RANKED SCOREBOARD
# -------------------------------------------------------------
final_ranking = df_master.sort_values('Master_Score', ascending=False).reset_index(drop=True)
final_ranking.index += 1   # rank starts at 1

print("\n" + "="*65)
print("           SME INVESTMENT SELECTION SCOREBOARD")
print("="*65)
print(final_ranking[['Ticker', 'Equity_Score', 'Cash_Flow_Score', 'Master_Score']].to_string(
    formatters={
        'Equity_Score':    '{:,.2f}'.format,
        'Cash_Flow_Score': '{:,.2f}'.format,
        'Master_Score':    '{:,.2f}'.format,
    }
))
print("="*65)

# -------------------------------------------------------------
# STEP 6: SENSITIVITY ANALYSIS — which companies are "robust picks"
# -------------------------------------------------------------
weight_combinations = [
    (0.50, 0.50, "Equal Weight"),
    (0.70, 0.30, "Equity Heavy"),
    (0.40, 0.60, "Cashflow Heavy"),
    (0.60, 0.40, "Base Case"),
]

top10_per_scenario = {}
print("\n--- SENSITIVITY ANALYSIS ---")
for eq_w, cf_w, label in weight_combinations:
    df_master[f'Score_{label}'] = (
        df_master['Equity_Score']    * eq_w +
        df_master['Cash_Flow_Score'] * cf_w
    )
    top10 = df_master.nlargest(10, f'Score_{label}')['Ticker'].tolist()
    top10_per_scenario[label] = top10
    print(f"\n{label} ({eq_w}/{cf_w}) Top 10: {top10}")

# Find companies in top 10 across ALL scenarios
all_top10_sets = [set(v) for v in top10_per_scenario.values()]
robust_picks = set.intersection(*all_top10_sets)
print(f"\n{'='*65}")
print(f"  ROBUST PICKS (top 10 in ALL 4 scenarios): {sorted(robust_picks)}")
print(f"{'='*65}")
