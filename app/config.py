from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / 'sample_data'
SAMPLE_BOOK = 'tour-demo'
PREVIEW = 'sample'
RULE_VERSION = 'theatre-1.0.0'
REPORT_ZONE = 'Asia/Shanghai'
MAX_SOURCE_BYTES = 512 * 1024
MAX_SOURCE_ROWS = 12_000
MAX_CENTS = 9_999_999_999

SOURCE_COLUMNS = {
    'tickets.csv': ('ticket', 'paid_at', 'amount', 'unit', 'status', 'note'),
    'shows.csv': ('show', 'title', 'venue', 'publication_status', 'opens', 'closes', 'cancelled_at'),
    'rights.csv': ('ticket', 'show', 'weight'),
    'scans.csv': ('scan_id', 'ticket', 'show', 'scanned_at', 'gate'),
    'refunds.csv': ('refund_id', 'ticket', 'show', 'refunded_at', 'amount', 'unit'),
}
