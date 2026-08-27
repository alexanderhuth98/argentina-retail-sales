SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'retail_ops.load_batch', N'U') IS NULL
BEGIN
    CREATE TABLE retail_ops.load_batch (
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        started_at_utc DATETIME2(0) NOT NULL,
        completed_at_utc DATETIME2(0) NULL,
        source_root NVARCHAR(4000) NOT NULL,
        load_status VARCHAR(16) NOT NULL,
        error_message NVARCHAR(2048) NULL,
        CONSTRAINT PK_load_batch PRIMARY KEY CLUSTERED (load_batch_id),
        CONSTRAINT CK_load_batch_status CHECK (load_status IN ('RUNNING', 'PUBLISHED', 'FAILED'))
    );
END;
GO

IF OBJECT_ID(N'retail.monthly_summary', N'U') IS NULL
BEGIN
    CREATE TABLE retail.monthly_summary (
        month DATE NOT NULL,
        retail_format VARCHAR(20) NOT NULL,
        nominal_sales_million_ars DECIMAL(28, 8) NOT NULL,
        constant_sales_million_ars DECIMAL(28, 8) NOT NULL,
        real_sales_index_original DECIMAL(18, 8) NOT NULL,
        real_sales_index_sa DECIMAL(18, 8) NOT NULL,
        real_sales_index_trend DECIMAL(18, 8) NOT NULL,
        nominal_sales_yoy_pct DECIMAL(18, 8) NULL,
        real_sales_yoy_pct DECIMAL(18, 8) NULL,
        real_sales_sa_mom_pct DECIMAL(18, 8) NULL,
        is_partial_year BIT NOT NULL,
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT PK_monthly_summary PRIMARY KEY CLUSTERED (month, retail_format),
        CONSTRAINT FK_monthly_summary_batch FOREIGN KEY (load_batch_id)
            REFERENCES retail_ops.load_batch (load_batch_id),
        CONSTRAINT CK_monthly_summary_format CHECK (retail_format IN ('supermarkets', 'wholesale')),
        CONSTRAINT CK_monthly_summary_month CHECK (DAY(month) = 1),
        CONSTRAINT CK_monthly_summary_values CHECK (
            nominal_sales_million_ars >= 0 AND constant_sales_million_ars >= 0
            AND real_sales_index_original >= 0 AND real_sales_index_sa >= 0
            AND real_sales_index_trend >= 0
        )
    );
END;
GO

IF OBJECT_ID(N'retail.payment_mix', N'U') IS NULL
BEGIN
    CREATE TABLE retail.payment_mix (
        month DATE NOT NULL,
        retail_format VARCHAR(20) NOT NULL,
        payment_method VARCHAR(20) NOT NULL,
        sales_thousand_ars DECIMAL(28, 6) NOT NULL,
        share_pct DECIMAL(18, 8) NOT NULL,
        is_observed BIT NOT NULL,
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT PK_payment_mix PRIMARY KEY CLUSTERED (month, retail_format, payment_method),
        CONSTRAINT FK_payment_mix_batch FOREIGN KEY (load_batch_id)
            REFERENCES retail_ops.load_batch (load_batch_id),
        CONSTRAINT CK_payment_mix_format CHECK (retail_format IN ('supermarkets', 'wholesale')),
        CONSTRAINT CK_payment_mix_method CHECK (payment_method IN ('cash', 'debit_card', 'credit_card', 'other')),
        CONSTRAINT CK_payment_mix_values CHECK (
            DAY(month) = 1 AND sales_thousand_ars >= 0 AND share_pct BETWEEN 0 AND 100
            AND is_observed = 1
        )
    );
END;
GO

IF OBJECT_ID(N'retail.category_mix', N'U') IS NULL
BEGIN
    CREATE TABLE retail.category_mix (
        month DATE NOT NULL,
        retail_format VARCHAR(20) NOT NULL,
        category VARCHAR(50) NOT NULL,
        sales_thousand_ars DECIMAL(28, 6) NOT NULL,
        share_pct DECIMAL(18, 8) NOT NULL,
        is_observed BIT NOT NULL,
        comparable_across_formats BIT NOT NULL,
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT PK_category_mix PRIMARY KEY CLUSTERED (month, retail_format, category),
        CONSTRAINT FK_category_mix_batch FOREIGN KEY (load_batch_id)
            REFERENCES retail_ops.load_batch (load_batch_id),
        CONSTRAINT CK_category_mix_format CHECK (retail_format IN ('supermarkets', 'wholesale')),
        CONSTRAINT CK_category_mix_values CHECK (
            DAY(month) = 1 AND sales_thousand_ars >= 0 AND share_pct BETWEEN 0 AND 100
            AND is_observed = 1
        )
    );
END;
GO

IF OBJECT_ID(N'retail.channel_mix', N'U') IS NULL
BEGIN
    CREATE TABLE retail.channel_mix (
        month DATE NOT NULL,
        retail_format VARCHAR(20) NOT NULL,
        channel VARCHAR(20) NOT NULL,
        sales_thousand_ars DECIMAL(28, 6) NULL,
        share_pct DECIMAL(18, 8) NULL,
        is_observed BIT NOT NULL,
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT PK_channel_mix PRIMARY KEY CLUSTERED (month, retail_format, channel),
        CONSTRAINT FK_channel_mix_batch FOREIGN KEY (load_batch_id)
            REFERENCES retail_ops.load_batch (load_batch_id),
        CONSTRAINT CK_channel_mix_format CHECK (retail_format IN ('supermarkets', 'wholesale')),
        CONSTRAINT CK_channel_mix_channel CHECK (channel IN ('showroom', 'online')),
        CONSTRAINT CK_channel_mix_values CHECK (
            DAY(month) = 1
            AND (sales_thousand_ars IS NULL OR sales_thousand_ars >= 0)
            AND (share_pct IS NULL OR share_pct BETWEEN 0 AND 100)
            AND ((is_observed = 1 AND sales_thousand_ars IS NOT NULL AND share_pct IS NOT NULL)
                OR (is_observed = 0 AND sales_thousand_ars IS NULL AND share_pct IS NULL))
        )
    );
END;
GO

IF OBJECT_ID(N'retail.quality_checks', N'U') IS NULL
BEGIN
    CREATE TABLE retail.quality_checks (
        source VARCHAR(20) NOT NULL,
        check_name VARCHAR(100) NOT NULL,
        severity VARCHAR(10) NOT NULL,
        status VARCHAR(10) NOT NULL,
        detail NVARCHAR(500) NOT NULL,
        load_batch_id UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT PK_quality_checks PRIMARY KEY CLUSTERED (source, check_name),
        CONSTRAINT FK_quality_checks_batch FOREIGN KEY (load_batch_id)
            REFERENCES retail_ops.load_batch (load_batch_id),
        CONSTRAINT CK_quality_checks_source CHECK (source IN ('supermarkets', 'wholesale')),
        CONSTRAINT CK_quality_checks_severity CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW')),
        CONSTRAINT CK_quality_checks_status CHECK (status IN ('PASS', 'FAIL'))
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'retail.monthly_summary') AND name = N'IX_monthly_summary_format_month')
    CREATE NONCLUSTERED INDEX IX_monthly_summary_format_month
        ON retail.monthly_summary (retail_format, month DESC)
        INCLUDE (nominal_sales_million_ars, real_sales_index_original, real_sales_index_sa, real_sales_yoy_pct);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'retail.payment_mix') AND name = N'IX_payment_mix_format_method_month')
    CREATE NONCLUSTERED INDEX IX_payment_mix_format_method_month
        ON retail.payment_mix (retail_format, payment_method, month DESC)
        INCLUDE (sales_thousand_ars, share_pct);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'retail.category_mix') AND name = N'IX_category_mix_format_month_share')
    CREATE NONCLUSTERED INDEX IX_category_mix_format_month_share
        ON retail.category_mix (retail_format, month DESC, share_pct DESC)
        INCLUDE (category, sales_thousand_ars, comparable_across_formats);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'retail.channel_mix') AND name = N'IX_channel_mix_format_channel_month')
    CREATE NONCLUSTERED INDEX IX_channel_mix_format_channel_month
        ON retail.channel_mix (retail_format, channel, month DESC)
        INCLUDE (sales_thousand_ars, share_pct, is_observed);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'retail.quality_checks') AND name = N'IX_quality_checks_gate')
    CREATE NONCLUSTERED INDEX IX_quality_checks_gate
        ON retail.quality_checks (severity, status)
        INCLUDE (source, check_name, detail);
GO
