-- =============================================================
-- Paid Channel Funnel Analysis
-- Purpose: Calculate full funnel metrics per channel per month
--          from impressions to Closed Won.
-- Tables:  ad_spend, leads, pipeline
-- Dialect: BigQuery / DuckDB compatible
-- =============================================================

WITH

-- Step 1: Ad spend aggregated by channel and month
channel_spend AS (
  SELECT
    channel,
    DATE_TRUNC(date, MONTH) AS month,
    SUM(spend_nok)          AS total_spend,
    SUM(impressions)        AS total_impressions,
    SUM(clicks)             AS total_clicks
  FROM ad_spend
  GROUP BY 1, 2
),

-- Step 2: Lead volume by channel and month
lead_volume AS (
  SELECT
    source_channel                   AS channel,
    DATE_TRUNC(created_date, MONTH)  AS month,
    COUNT(*)                         AS total_leads,
    COUNTIF(icp_score >= 60)         AS qualified_leads,   -- ICP-fit threshold
    COUNTIF(stage = 'MQL')           AS mqls,
    COUNTIF(stage IN ('SQL','Opportunity','Closed Won')) AS sqls
  FROM leads
  GROUP BY 1, 2
),

-- Step 3: Pipeline and closed revenue by channel and month
pipeline_value AS (
  SELECT
    source_channel                      AS channel,
    DATE_TRUNC(close_date, MONTH)       AS month,
    COUNT(*)                            AS opportunities,
    COUNTIF(stage = 'Closed Won')       AS closed_won,
    SUM(IF(stage='Closed Won', arr, 0)) AS closed_arr
  FROM pipeline
  GROUP BY 1, 2
)

-- Final: Join and calculate rates + unit economics
SELECT
  s.channel,
  s.month,

  -- Spend and volume
  s.total_spend,
  s.total_impressions,
  s.total_clicks,
  l.total_leads,
  l.qualified_leads,
  l.mqls,
  l.sqls,
  p.opportunities,
  p.closed_won,
  p.closed_arr,

  -- Funnel rates
  SAFE_DIVIDE(s.total_clicks, s.total_impressions)  AS ctr,
  SAFE_DIVIDE(l.total_leads, s.total_clicks)        AS lead_rate,
  SAFE_DIVIDE(l.mqls, l.total_leads)                AS mql_rate,
  SAFE_DIVIDE(l.sqls, l.mqls)                       AS sql_rate,
  SAFE_DIVIDE(p.closed_won, l.sqls)                 AS win_rate,

  -- Unit economics
  SAFE_DIVIDE(s.total_spend, l.total_leads)         AS cpl,          -- Cost per Lead
  SAFE_DIVIDE(s.total_spend, l.mqls)                AS cpm_ql,       -- Cost per MQL
  SAFE_DIVIDE(s.total_spend, l.sqls)                AS cp_sql,       -- Cost per SQL
  SAFE_DIVIDE(s.total_spend, p.closed_won)          AS cac,          -- Customer Acquisition Cost

  -- Quality signal
  SAFE_DIVIDE(l.qualified_leads, l.total_leads)     AS icp_match_rate

FROM channel_spend s
LEFT JOIN lead_volume   l ON s.channel = l.channel AND s.month = l.month
LEFT JOIN pipeline_value p ON s.channel = p.channel AND s.month = p.month

ORDER BY s.month DESC, s.total_spend DESC;

-- ---------------------------------------------------------------
-- INTERPRETATION GUIDE
-- CAC < LTV/3          = healthy. LTV = avg ARR * gross margin / churn rate.
-- MQL rate < 10%       = targeting problem or landing page mismatch.
-- ICP match rate < 30% = wrong audience; review creative targeting.
-- Win rate < 15%       = Sales handoff or qualification process issue.
-- ---------------------------------------------------------------
