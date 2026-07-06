# SME Financial Health Scorer

A dual-engine quantitative scoring model ranks NSE-listed small and mid-cap companies (₹1000 Cr to ₹10,000 Cr market cap) based on **equity quality** and **cash flow stability**. It includes sensitivity analysis and two independently tested assumptions.

For the full methodology, rationale for each design decision, and real results analysis, refer to SME Financial Health Scorer Analysis - https://drive.google.com/file/d/1D6LMmG9mc-IoFQY5RuFudvDndSYvjke9/view?usp=sharing

## What it does

The model screens a selection of NSE mid-cap companies using seven quantitative metrics from two independent engines. It combines these into a single ranked score and stress-tests the ranking against four different weighting assumptions. This process identifies a set of **"Robust Picks"** that remain strong regardless of the chosen weighting philosophy.

## Why dual-engine

Most screeners evaluate companies through a single lens (like ROE or P/E) and overlook those that seem strong on paper but are burning cash, or those that appear weak on valuation but consistently convert revenue into cash. This model assesses each company from two truly independent perspectives, reporting both. If a company scores well on only one engine, it gets flagged rather than hidden.

| | **Engine A, Equity Profile** | **Engine B, Cash Flow Stability** |
|---|---|---|
| Question | Is this a quality business at a reasonable price? | Is its operational execution reliable? |
| Data | ROE, D/E, EPS trend (3yr), P/E, P/B | 6 quarters revenue, 3 years OCF |
| Weight in Master Score | 60% | 40% |

## Sample

This analysis includes 35 NSE companies with a market cap between ₹1000 Cr and ₹10,000 Cr. Data was sourced manually from [Screener.in](https://www.screener.in).

## Setup

```bash
pip install pandas numpy
python sme_scorer.py
```

You will need two input CSV files in the same directory as the script:
- `Book1(companies_static).csv - https://1drv.ms/x/c/6bdbc2328869d12a/IQDr3aWCes-LSaQ3sdWtCJ_ZAWuEqs8i0l4WiOejfT12mao?e=PJ2mcd` — Ticker, P/E, P/B, ROE, Debt/Eq, EPS_Y1, EPS_Y2, EPS_Y3
- `Book2(companies_cashflow).csv - https://1drv.ms/x/c/6bdbc2328869d12a/IQAYNJxhIAfsQL6qdSVxW457Ab9MIuwjuHR9Ulncp-I9VEs?e=O4cJux` — Ticker, Rev_Q1 to Q6, Rev_Y1 to Y3, OCF_Y1 to Y3

The output will include a ranked scoreboard, a four-scenario sensitivity analysis, and `SME_Scorer_Output.csv` with the complete ranked results.

## Key results (this run, 35 companies)

**Robust Picks** — companies that rank in the top 10 across all four weighting scenarios (Base 60/40, Equal 50/50, Equity-Heavy 70/30, Cashflow-Heavy 40/60):

> Alldigi Tech, Canara Robeco, Crizac, MPS, Newgen Software, Saksoft, Vikram Solar, Websol Energy

## Assumptions tested, not just stated

Instead of claiming the scoring logic is completely accurate, we empirically checked two core assumptions against actual results:

**1. Are the two engines truly independent, or are they just re-weighting the same signal?**
The Pearson correlation between Equity_Score and Cash_Flow_Score across the sample is **−0.113** (Spearman: −0.182). This value is close to zero, confirming that the two engines capture different dimensions of quality rather than the same signal counted twice.

**2. Does the model unfairly penalize certain sectors (for instance, EPC/infrastructure) by scoring them against the full sample instead of true peers?**
We tested this directly by recalculating Cash Flow Scores within sector groups of three or more companies. The result was mixed, and not a clear confirmation: Canara Robeco's high score remained strong against true financial-services peers. K.P. Energy showed it had been unfairly penalized by the full-sample comparison (its score increased from 31.9 to 54.6 within its EPC peer group). However, SRM Contractors' score *decreased* even further within its own EPC peer group (from 24.6 to 0.0), indicating its low score reflects genuine underperformance, not sector bias. This also highlighted a limitation: with only 35 companies across about 11 sectors, most sector groups contain too few companies (less than three) for reliable within-sector normalization to be statistically valid.

Detailed information on both tests, including reasoning and what would be needed to ensure sector normalization is trustworthy at scale, is available in the guided document.

## Known limitations

- All scores are **sample-relative** — adding a new company changes every existing company's normalized score.
- **Sector normalization** is only partially validated and requires a larger sample for reliability across all sectors, not just the two tested.
- Weights (ROE 25%, others 18.75% each; 60/40 Master Score split) are **assumed reasoning,** not derived from actual forward-return regression — this is the next step to take.
- **No backtest yet.** The model has not undergone validation against actual forward returns — it currently shows internal consistency through the sensitivity and independence checks, not predictive power. This is the most important item still open.
- There is no liquidity filter — a company might score well but still have issues trading at size.

## Roadmap

-  Perform a lightweight backtest comparing top-quartile vs. bottom-quartile forward returns for the Robust Picks.
-  Expand the sample size to ensure sector-relative normalization is statistically valid across all sectors.
-  Derive weights empirically through regression against historical forward returns.
-  Implement a liquidity pre-screen.
-  Create a Streamlit dashboard with adjustable weight sliders.

## Files

```
sme_scorer.py                 - https://1drv.ms/x/c/6bdbc2328869d12a/IQB8NyU6Brw1Qqfr7KWMflMPAQTeAXKH1c5u8s6-PBVlnxY?e=vhhvBP         # main scoring script
Book1(companies_static).csv   - https://1drv.ms/x/c/6bdbc2328869d12a/IQDr3aWCes-LSaQ3sdWtCJ_ZAWuEqs8i0l4WiOejfT12mao?e=Hvwzfh         # equity input data
Book2(companies_cashflow).csv - https://1drv.ms/x/c/6bdbc2328869d12a/IQAYNJxhIAfsQL6qdSVxW457Ab9MIuwjuHR9Ulncp-I9VEs?e=I3Rfaj         # cash flow input data
SME Financial Health Scorer Analysis - https://drive.google.com/file/d/1D6LMmG9mc-IoFQY5RuFudvDndSYvjke9/view?usp=sharing
# guide for the project
```

---

*This is a screening tool, not an investment recommendation. It narrows a large universe to a shortlist for further research - it does not replace reading annual reports, assessing management quality, or conducting independent due diligence.*
