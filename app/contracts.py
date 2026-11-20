import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal

from app.config import MAX_CENTS
from app.errors import RowError

SENTINELS = {'', '-', 'N/A', 'NULL', '未知'}
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}')
MONEY = re.compile(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?')
TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})')


def text(value):
    stripped = value.strip()
    if stripped.upper() in SENTINELS:
        raise RowError('MISSING_VALUE')
    return stripped


def key(value):
    value = text(value)
    if not KEY.fullmatch(value):
        raise RowError('INVALID_KEY')
    return value


def timestamp(value):
    value = text(value)
    if not TIME.fullmatch(value):
        raise RowError('INVALID_TIME')
    try:
        return datetime.fromisoformat(value).astimezone(UTC).isoformat(timespec='seconds')
    except (ValueError, OverflowError) as exc:
        raise RowError('INVALID_TIME') from exc


def cents(value, unit):
    value = unicodedata.normalize('NFKC', text(value))
    unit = text(unit)
    if unit not in {'元', '分'}:
        raise RowError('INVALID_UNIT')
    if len(value) > 24 or not MONEY.fullmatch(value) or (unit == '分' and '.' in value):
        raise RowError('INVALID_AMOUNT')
    number = Decimal(value.replace(',', '')) * (100 if unit == '元' else 1)
    if not 0 < number <= MAX_CENTS:
        raise RowError('INVALID_AMOUNT')
    return int(number)


def weight(value):
    value = unicodedata.normalize('NFKC', text(value))
    if not re.fullmatch(r'[0-9]{1,5}', value) or not 0 < int(value) <= 10_000:
        raise RowError('INVALID_WEIGHT')
    return int(value)
