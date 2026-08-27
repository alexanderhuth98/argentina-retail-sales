SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW retail.v_monthly_performance
AS
WITH latest_month_by_format AS (
    SELECT monthly.retail_format, MAX(monthly.month) AS latest_month
    FROM retail.monthly_summary AS monthly
    GROUP BY monthly.retail_format
)
SELECT
    monthly.month,
    monthly.retail_format,
    monthly.nominal_sales_million_ars,
    monthly.constant_sales_million_ars,
    monthly.real_sales_index_original,
    monthly.real_sales_index_sa,
    monthly.real_sales_index_trend,
    monthly.nominal_sales_yoy_pct,
    monthly.real_sales_yoy_pct,
    monthly.real_sales_sa_mom_pct,
    monthly.is_partial_year,
    CASE WHEN monthly.month = latest.latest_month THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT) END AS is_latest_month
FROM retail.monthly_summary AS monthly
INNER JOIN latest_month_by_format AS latest
    ON latest.retail_format = monthly.retail_format;
GO

CREATE OR ALTER VIEW retail.v_payment_mix_change
AS
WITH payment_history AS (
    SELECT
        payment.month,
        payment.retail_format,
        payment.payment_method,
        payment.sales_thousand_ars,
        payment.share_pct,
        LAG(payment.share_pct, 12) OVER (
            PARTITION BY payment.retail_format, payment.payment_method
            ORDER BY payment.month
        ) AS prior_year_share_pct
    FROM retail.payment_mix AS payment
)
SELECT
    history.month,
    history.retail_format,
    history.payment_method,
    history.sales_thousand_ars,
    history.share_pct,
    history.prior_year_share_pct,
    history.share_pct - history.prior_year_share_pct AS share_yoy_change_pp
FROM payment_history AS history;
GO

CREATE OR ALTER VIEW retail.v_category_mix_change
AS
WITH category_history AS (
    SELECT
        category_row.month,
        category_row.retail_format,
        category_row.category,
        category_row.sales_thousand_ars,
        category_row.share_pct,
        category_row.comparable_across_formats,
        LAG(category_row.sales_thousand_ars, 12) OVER (
            PARTITION BY category_row.retail_format, category_row.category
            ORDER BY category_row.month
        ) AS prior_year_sales_thousand_ars
    FROM retail.category_mix AS category_row
)
SELECT
    history.month,
    history.retail_format,
    history.category,
    history.sales_thousand_ars,
    history.share_pct,
    history.comparable_across_formats,
    history.prior_year_sales_thousand_ars,
    100.0 * (history.sales_thousand_ars - history.prior_year_sales_thousand_ars)
        / NULLIF(history.prior_year_sales_thousand_ars, 0) AS nominal_sales_yoy_pct
FROM category_history AS history;
GO

CREATE OR ALTER VIEW retail.v_channel_availability
AS
SELECT
    channel_row.month,
    channel_row.retail_format,
    channel_row.channel,
    channel_row.sales_thousand_ars,
    channel_row.share_pct,
    channel_row.is_observed,
    MAX(CASE WHEN channel_row.is_observed = 1 THEN channel_row.month END) OVER (
        PARTITION BY channel_row.retail_format, channel_row.channel
    ) AS latest_observed_month
FROM retail.channel_mix AS channel_row;
GO

CREATE OR ALTER VIEW retail.v_quality_gate
AS
SELECT
    quality_check.source,
    quality_check.check_name,
    quality_check.severity,
    quality_check.status,
    quality_check.detail,
    CASE
        WHEN quality_check.severity = 'HIGH' AND quality_check.status = 'FAIL' THEN CAST(0 AS BIT)
        ELSE CAST(1 AS BIT)
    END AS passes_publication_gate
FROM retail.quality_checks AS quality_check;
GO
