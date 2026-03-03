# Paid Channel Performance Analysis

## Problem

A B2B SaaS company is spending ~NOK 800,000/month across Google Ads, LinkedIn Ads, and Meta Ads. The VP of Marketing suspects budget is misallocated but does not have channel-level CPA, pipeline conversion, or CAC/LTV data to make the case internally. The question: **which channels are actually generating qualified pipeline, and which are burning budget on low-quality leads?**

## Approach

1. **Channel-level funnel analysis** — SQL queries against CRM + ad platform exports to calculate impressions → click → lead → MQL → SQL → Closed Won rates per channel.
2. **CAC and LTV calculation** — blended and channel-level Customer Acquisition Cost vs. estimated 12-month LTV.
3. **Lead quality scoring** — Python script that scores inbound leads by ICP fit (firmographics + behaviour) to separate volume from value.
4. **Budget reallocation model** — simple optimisation: given fixed total budget, allocate to maximise pipeline at target CPA.

## Data

Synthetic data modelling a B2B SaaS company with 3 paid channels:

| Table | Description |
|-------|-------------|
| `ad_spend.csv` | Monthly spend per channel and campaign |
| `leads.csv` | Lead records with source, date, ICP score, stage |
| `pipeline.csv` | Opportunity records with ARR, stage, close date |
| `channel_funnel.csv` | Aggregated funnel metrics per channel per month |

## Key Files

```
/sql
  01_channel_funnel.sql         → Funnel metrics by channel (impressions to Closed Won)
  02_cac_ltv_by_channel.sql     → CAC and LTV calculation per channel
  03_lead_quality_distribution.sql → Lead volume vs ICP-qualified volume split
  04_budget_efficiency.sql      → Cost per MQL, SQL, and Opportunity by channel
/notebooks
  paid_channel_analysis.py      → Full Python analysis + visualisations
/data
  ad_spend.csv
  leads.csv
  pipeline.csv
README.md
```

## Key Findings

| Channel | Monthly Spend | Leads | MQL Rate | SQL Rate | CPA (Closed Won) | LTV:CAC |
|---------|--------------|-------|----------|----------|------------------|---------|
| Google Ads (Brand) | NOK 80k | 340 | 38% | 22% | NOK 18,200 | 4.1x |
| Google Ads (Non-brand) | NOK 220k | 890 | 12% | 6% | NOK 68,000 | 0.9x |
| LinkedIn Ads | NOK 310k | 210 | 51% | 31% | NOK 24,500 | 3.4x |
| Meta Ads | NOK 190k | 1,240 | 4% | 1.5% | NOK 112,000 | 0.3x |

**Key insight:** Google non-brand and Meta are operating below LTV:CAC = 1. LinkedIn and Google Brand are the only channels generating positive unit economics.

## Business Recommendations

1. **Cut Meta Ads by 70%.** LTV:CAC of 0.3x means each closed deal costs more than the customer is worth. Reallocate to LinkedIn.
2. **Pause or restructure Google Non-brand.** High volume, low quality. Narrow targeting to bottom-funnel keywords only (demo, pricing, comparison). Expect 60% volume drop, 3x improvement in CPA.
3. **Increase LinkedIn budget by NOK 180k/month.** Highest ICP match rate (51% MQL). Unit economics positive at 3.4x. Test ABM campaigns for top-100 target accounts.
4. **Protect Google Brand budget.** Lowest CPA, highest conversion rate. Never cut this line.
5. **Implement lead scoring in CRM.** 74% of leads have ICP score < 40. Routing all leads to Sales wastes capacity. Auto-disqualify below score 35.

## How to Run

```bash
# SQL: run against your warehouse or DuckDB with the CSVs
duckdb < sql/01_channel_funnel.sql

# Python analysis
pip install pandas matplotlib seaborn
python notebooks/paid_channel_analysis.py
```

## Stack

- SQL (BigQuery / DuckDB compatible)
- Python 3.11, pandas, matplotlib, seaborn
- Google Ads, LinkedIn Campaign Manager exports
- Salesforce / HubSpot CRM export
