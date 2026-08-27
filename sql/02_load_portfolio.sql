SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

CREATE OR ALTER PROCEDURE retail_ops.load_portfolio_csvs
    @portfolio_data_path NVARCHAR(4000)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @load_batch_id UNIQUEIDENTIFIER = NEWID();
    DECLARE @started_at_utc DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @lock_result INT;
    DECLARE @root NVARCHAR(4000) = RTRIM(@portfolio_data_path);
    DECLARE @escaped_root NVARCHAR(4000);
    DECLARE @sql NVARCHAR(MAX);

    IF NULLIF(@root, N'') IS NULL
        THROW 51000, 'portfolio_data_path is required.', 1;
    IF RIGHT(@root, 1) NOT IN (N'\', N'/')
        SET @root = @root + N'\';
    SET @escaped_root = REPLACE(@root, N'''', N'''''' );

    EXEC @lock_result = sys.sp_getapplock
        @Resource = N'argentina-retail-sales:portfolio-load',
        @LockMode = N'Exclusive',
        @LockOwner = N'Session',
        @LockTimeout = 0;
    IF @lock_result < 0
        THROW 51001, 'Another portfolio load is running.', 1;

    CREATE TABLE #monthly_summary (
        month NVARCHAR(40), retail_format NVARCHAR(40), nominal_sales_million_ars NVARCHAR(80),
        constant_sales_million_ars NVARCHAR(80), real_sales_index_original NVARCHAR(80),
        real_sales_index_sa NVARCHAR(80), real_sales_index_trend NVARCHAR(80),
        nominal_sales_yoy_pct NVARCHAR(80), real_sales_yoy_pct NVARCHAR(80),
        real_sales_sa_mom_pct NVARCHAR(80), is_partial_year NVARCHAR(20)
    );
    CREATE TABLE #payment_mix (
        month NVARCHAR(40), retail_format NVARCHAR(40), payment_method NVARCHAR(40),
        sales_thousand_ars NVARCHAR(80), share_pct NVARCHAR(80), is_observed NVARCHAR(20)
    );
    CREATE TABLE #category_mix (
        month NVARCHAR(40), retail_format NVARCHAR(40), category NVARCHAR(100),
        sales_thousand_ars NVARCHAR(80), share_pct NVARCHAR(80), is_observed NVARCHAR(20),
        comparable_across_formats NVARCHAR(20)
    );
    CREATE TABLE #channel_mix (
        month NVARCHAR(40), retail_format NVARCHAR(40), channel NVARCHAR(40),
        sales_thousand_ars NVARCHAR(80), share_pct NVARCHAR(80), is_observed NVARCHAR(20)
    );
    CREATE TABLE #quality_checks (
        source NVARCHAR(40), check_name NVARCHAR(150), severity NVARCHAR(20),
        status NVARCHAR(20), detail NVARCHAR(1000)
    );

    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO retail_ops.load_batch (
            load_batch_id, started_at_utc, completed_at_utc, source_root, load_status, error_message
        )
        VALUES (@load_batch_id, @started_at_utc, NULL, @root, 'RUNNING', NULL);

        SET @sql = N'BULK INSERT #monthly_summary FROM ''' + @escaped_root
            + N'monthly_summary.csv'' WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', CODEPAGE = ''65001'', TABLOCK);';
        EXEC sys.sp_executesql @sql;
        SET @sql = N'BULK INSERT #payment_mix FROM ''' + @escaped_root
            + N'payment_mix.csv'' WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', CODEPAGE = ''65001'', TABLOCK);';
        EXEC sys.sp_executesql @sql;
        SET @sql = N'BULK INSERT #category_mix FROM ''' + @escaped_root
            + N'category_mix.csv'' WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', CODEPAGE = ''65001'', TABLOCK);';
        EXEC sys.sp_executesql @sql;
        SET @sql = N'BULK INSERT #channel_mix FROM ''' + @escaped_root
            + N'channel_mix.csv'' WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', CODEPAGE = ''65001'', TABLOCK);';
        EXEC sys.sp_executesql @sql;
        SET @sql = N'BULK INSERT #quality_checks FROM ''' + @escaped_root
            + N'quality_checks.csv'' WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', CODEPAGE = ''65001'', TABLOCK);';
        EXEC sys.sp_executesql @sql;

        IF NOT EXISTS (SELECT 1 FROM #monthly_summary AS monthly)
           OR NOT EXISTS (SELECT 1 FROM #payment_mix AS payment)
           OR NOT EXISTS (SELECT 1 FROM #category_mix AS category_row)
           OR NOT EXISTS (SELECT 1 FROM #channel_mix AS channel_row)
           OR NOT EXISTS (SELECT 1 FROM #quality_checks AS quality_check)
            THROW 51013, 'Every portfolio CSV must contain at least one data row.', 1;

        IF NOT EXISTS (
            SELECT 1 FROM #quality_checks AS quality_check WHERE quality_check.severity = N'HIGH'
        ) OR EXISTS (
            SELECT 1
            FROM #quality_checks AS quality_check
            WHERE quality_check.severity = N'HIGH' AND quality_check.status <> N'PASS'
        )
            THROW 51002, 'Publication blocked: every HIGH source check must be present and PASS.', 1;

        IF EXISTS (
            SELECT 1
            FROM #monthly_summary AS monthly
            WHERE TRY_CONVERT(DATE, monthly.month, 23) IS NULL
               OR monthly.retail_format NOT IN (N'supermarkets', N'wholesale')
               OR TRY_CONVERT(DECIMAL(28, 8), monthly.nominal_sales_million_ars) IS NULL
               OR TRY_CONVERT(DECIMAL(28, 8), monthly.constant_sales_million_ars) IS NULL
               OR TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_original) IS NULL
               OR TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_sa) IS NULL
               OR TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_trend) IS NULL
               OR (NULLIF(monthly.nominal_sales_yoy_pct, N'') IS NOT NULL
                   AND TRY_CONVERT(DECIMAL(18, 8), monthly.nominal_sales_yoy_pct) IS NULL)
               OR (NULLIF(monthly.real_sales_yoy_pct, N'') IS NOT NULL
                   AND TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_yoy_pct) IS NULL)
               OR (NULLIF(monthly.real_sales_sa_mom_pct, N'') IS NOT NULL
                   AND TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_sa_mom_pct) IS NULL)
               OR monthly.is_partial_year NOT IN (N'True', N'False')
        )
            THROW 51003, 'monthly_summary.csv contains invalid required values.', 1;

        IF EXISTS (
            SELECT TRY_CONVERT(DATE, monthly.month, 23), monthly.retail_format
            FROM #monthly_summary AS monthly
            GROUP BY TRY_CONVERT(DATE, monthly.month, 23), monthly.retail_format
            HAVING COUNT_BIG(1) > 1
        )
            THROW 51004, 'monthly_summary.csv violates its month and retail_format key.', 1;

        IF EXISTS (
            SELECT 1
            FROM #payment_mix AS payment
            WHERE TRY_CONVERT(DATE, payment.month, 23) IS NULL
               OR payment.retail_format NOT IN (N'supermarkets', N'wholesale')
               OR payment.payment_method NOT IN (N'cash', N'debit_card', N'credit_card', N'other')
               OR TRY_CONVERT(DECIMAL(28, 6), payment.sales_thousand_ars) IS NULL
               OR TRY_CONVERT(DECIMAL(18, 8), payment.share_pct) IS NULL
               OR payment.is_observed <> N'True'
        )
            THROW 51005, 'payment_mix.csv contains invalid values.', 1;

        IF EXISTS (
            SELECT TRY_CONVERT(DATE, payment.month, 23), payment.retail_format, payment.payment_method
            FROM #payment_mix AS payment
            GROUP BY TRY_CONVERT(DATE, payment.month, 23), payment.retail_format, payment.payment_method
            HAVING COUNT_BIG(1) > 1
        )
            THROW 51006, 'payment_mix.csv violates its documented key.', 1;

        IF EXISTS (
            SELECT 1
            FROM #category_mix AS category_row
            WHERE TRY_CONVERT(DATE, category_row.month, 23) IS NULL
               OR category_row.retail_format NOT IN (N'supermarkets', N'wholesale')
               OR NULLIF(category_row.category, N'') IS NULL
               OR TRY_CONVERT(DECIMAL(28, 6), category_row.sales_thousand_ars) IS NULL
               OR TRY_CONVERT(DECIMAL(18, 8), category_row.share_pct) IS NULL
               OR category_row.is_observed <> N'True'
               OR category_row.comparable_across_formats NOT IN (N'True', N'False')
        )
            THROW 51007, 'category_mix.csv contains invalid values.', 1;

        IF EXISTS (
            SELECT TRY_CONVERT(DATE, category_row.month, 23), category_row.retail_format, category_row.category
            FROM #category_mix AS category_row
            GROUP BY TRY_CONVERT(DATE, category_row.month, 23), category_row.retail_format, category_row.category
            HAVING COUNT_BIG(1) > 1
        )
            THROW 51008, 'category_mix.csv violates its documented key.', 1;

        IF EXISTS (
            SELECT 1
            FROM #channel_mix AS channel_row
            WHERE TRY_CONVERT(DATE, channel_row.month, 23) IS NULL
               OR channel_row.retail_format NOT IN (N'supermarkets', N'wholesale')
               OR channel_row.channel NOT IN (N'showroom', N'online')
               OR channel_row.is_observed NOT IN (N'True', N'False')
               OR (channel_row.is_observed = N'True' AND (
                    TRY_CONVERT(DECIMAL(28, 6), channel_row.sales_thousand_ars) IS NULL
                    OR TRY_CONVERT(DECIMAL(18, 8), channel_row.share_pct) IS NULL
               ))
               OR (channel_row.is_observed = N'False' AND (
                    NULLIF(channel_row.sales_thousand_ars, N'') IS NOT NULL
                    OR NULLIF(channel_row.share_pct, N'') IS NOT NULL
               ))
        )
            THROW 51009, 'channel_mix.csv contains invalid availability or values.', 1;

        IF EXISTS (
            SELECT TRY_CONVERT(DATE, channel_row.month, 23), channel_row.retail_format, channel_row.channel
            FROM #channel_mix AS channel_row
            GROUP BY TRY_CONVERT(DATE, channel_row.month, 23), channel_row.retail_format, channel_row.channel
            HAVING COUNT_BIG(1) > 1
        )
            THROW 51010, 'channel_mix.csv violates its documented key.', 1;

        IF EXISTS (
            SELECT 1
            FROM #quality_checks AS quality_check
            WHERE quality_check.source NOT IN (N'supermarkets', N'wholesale')
               OR NULLIF(quality_check.check_name, N'') IS NULL
               OR quality_check.severity NOT IN (N'HIGH', N'MEDIUM', N'LOW')
               OR quality_check.status NOT IN (N'PASS', N'FAIL')
               OR NULLIF(quality_check.detail, N'') IS NULL
        )
            THROW 51011, 'quality_checks.csv contains invalid values.', 1;

        IF EXISTS (
            SELECT quality_check.source, quality_check.check_name
            FROM #quality_checks AS quality_check
            GROUP BY quality_check.source, quality_check.check_name
            HAVING COUNT_BIG(1) > 1
        )
            THROW 51012, 'quality_checks.csv violates its source and check key.', 1;

        DELETE FROM retail.channel_mix;
        DELETE FROM retail.category_mix;
        DELETE FROM retail.payment_mix;
        DELETE FROM retail.monthly_summary;
        DELETE FROM retail.quality_checks;

        INSERT INTO retail.monthly_summary (
            month, retail_format, nominal_sales_million_ars, constant_sales_million_ars,
            real_sales_index_original, real_sales_index_sa, real_sales_index_trend,
            nominal_sales_yoy_pct, real_sales_yoy_pct, real_sales_sa_mom_pct,
            is_partial_year, load_batch_id
        )
        SELECT
            TRY_CONVERT(DATE, monthly.month, 23), CONVERT(VARCHAR(20), monthly.retail_format),
            TRY_CONVERT(DECIMAL(28, 8), monthly.nominal_sales_million_ars),
            TRY_CONVERT(DECIMAL(28, 8), monthly.constant_sales_million_ars),
            TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_original),
            TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_sa),
            TRY_CONVERT(DECIMAL(18, 8), monthly.real_sales_index_trend),
            TRY_CONVERT(DECIMAL(18, 8), NULLIF(monthly.nominal_sales_yoy_pct, N'')),
            TRY_CONVERT(DECIMAL(18, 8), NULLIF(monthly.real_sales_yoy_pct, N'')),
            TRY_CONVERT(DECIMAL(18, 8), NULLIF(monthly.real_sales_sa_mom_pct, N'')),
            CASE monthly.is_partial_year WHEN N'True' THEN 1 ELSE 0 END,
            @load_batch_id
        FROM #monthly_summary AS monthly;

        INSERT INTO retail.payment_mix (
            month, retail_format, payment_method, sales_thousand_ars, share_pct,
            is_observed, load_batch_id
        )
        SELECT
            TRY_CONVERT(DATE, payment.month, 23), CONVERT(VARCHAR(20), payment.retail_format),
            CONVERT(VARCHAR(20), payment.payment_method),
            TRY_CONVERT(DECIMAL(28, 6), payment.sales_thousand_ars),
            TRY_CONVERT(DECIMAL(18, 8), payment.share_pct), 1, @load_batch_id
        FROM #payment_mix AS payment;

        INSERT INTO retail.category_mix (
            month, retail_format, category, sales_thousand_ars, share_pct,
            is_observed, comparable_across_formats, load_batch_id
        )
        SELECT
            TRY_CONVERT(DATE, category_row.month, 23),
            CONVERT(VARCHAR(20), category_row.retail_format),
            CONVERT(VARCHAR(50), category_row.category),
            TRY_CONVERT(DECIMAL(28, 6), category_row.sales_thousand_ars),
            TRY_CONVERT(DECIMAL(18, 8), category_row.share_pct), 1,
            CASE category_row.comparable_across_formats WHEN N'True' THEN 1 ELSE 0 END,
            @load_batch_id
        FROM #category_mix AS category_row;

        INSERT INTO retail.channel_mix (
            month, retail_format, channel, sales_thousand_ars, share_pct,
            is_observed, load_batch_id
        )
        SELECT
            TRY_CONVERT(DATE, channel_row.month, 23),
            CONVERT(VARCHAR(20), channel_row.retail_format),
            CONVERT(VARCHAR(20), channel_row.channel),
            TRY_CONVERT(DECIMAL(28, 6), NULLIF(channel_row.sales_thousand_ars, N'')),
            TRY_CONVERT(DECIMAL(18, 8), NULLIF(channel_row.share_pct, N'')),
            CASE channel_row.is_observed WHEN N'True' THEN 1 ELSE 0 END,
            @load_batch_id
        FROM #channel_mix AS channel_row;

        INSERT INTO retail.quality_checks (
            source, check_name, severity, status, detail, load_batch_id
        )
        SELECT
            CONVERT(VARCHAR(20), quality_check.source),
            CONVERT(VARCHAR(100), quality_check.check_name),
            CONVERT(VARCHAR(10), quality_check.severity),
            CONVERT(VARCHAR(10), quality_check.status),
            CONVERT(NVARCHAR(500), quality_check.detail), @load_batch_id
        FROM #quality_checks AS quality_check;

        UPDATE retail_ops.load_batch
        SET completed_at_utc = SYSUTCDATETIME(), load_status = 'PUBLISHED'
        WHERE load_batch_id = @load_batch_id;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
        INSERT INTO retail_ops.load_batch (
            load_batch_id, started_at_utc, completed_at_utc, source_root, load_status, error_message
        )
        VALUES (
            @load_batch_id, @started_at_utc, SYSUTCDATETIME(), @root, 'FAILED',
            LEFT(ERROR_MESSAGE(), 2048)
        );
        EXEC sys.sp_releaseapplock
            @Resource = N'argentina-retail-sales:portfolio-load', @LockOwner = N'Session';
        THROW;
    END CATCH;

    EXEC sys.sp_releaseapplock
        @Resource = N'argentina-retail-sales:portfolio-load', @LockOwner = N'Session';
END;
GO
