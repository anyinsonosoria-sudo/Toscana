CREATE TABLE IF NOT EXISTS monthly_report_dispatch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    report_period TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    subject TEXT,
    error_message TEXT,
    started_at TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_type, report_period, recipient_email)
);

CREATE INDEX IF NOT EXISTS idx_monthly_report_dispatch_period
ON monthly_report_dispatch_log(report_type, report_period);