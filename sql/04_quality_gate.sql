SET NOCOUNT ON;
GO

CREATE OR ALTER PROCEDURE retail_ops.assert_published_quality
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (
        SELECT 1
        FROM retail.quality_checks AS quality_check
        WHERE quality_check.severity = 'HIGH'
    )
        THROW 51020, 'No HIGH quality checks are available.', 1;

    IF EXISTS (
        SELECT 1
        FROM retail.quality_checks AS quality_check
        WHERE quality_check.severity = 'HIGH' AND quality_check.status <> 'PASS'
    )
        THROW 51021, 'Published data failed a HIGH quality check.', 1;

    IF EXISTS (
        SELECT monthly.month, monthly.retail_format
        FROM retail.monthly_summary AS monthly
        GROUP BY monthly.month, monthly.retail_format
        HAVING COUNT_BIG(1) <> 1
    )
        THROW 51022, 'monthly_summary grain is invalid.', 1;

    IF EXISTS (
        SELECT payment.month, payment.retail_format
        FROM retail.payment_mix AS payment
        GROUP BY payment.month, payment.retail_format
        HAVING ABS(SUM(payment.share_pct) - 100.0) > 0.01
    )
        THROW 51023, 'Payment shares do not reconcile to 100 percent.', 1;

    IF EXISTS (
        SELECT category_row.month, category_row.retail_format
        FROM retail.category_mix AS category_row
        GROUP BY category_row.month, category_row.retail_format
        HAVING ABS(SUM(category_row.share_pct) - 100.0) > 0.01
    )
        THROW 51024, 'Category shares do not reconcile to 100 percent.', 1;

    IF EXISTS (
        SELECT channel_row.month, channel_row.retail_format
        FROM retail.channel_mix AS channel_row
        WHERE channel_row.is_observed = 1
        GROUP BY channel_row.month, channel_row.retail_format
        HAVING COUNT_BIG(1) <> 2 OR ABS(SUM(channel_row.share_pct) - 100.0) > 0.01
    )
        THROW 51025, 'Observed channel shares do not reconcile to 100 percent.', 1;
END;
GO
