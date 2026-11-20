import pytest

from app.contracts import cents
from app.errors import RowError


def test_bom_and_zero_prefixed_ticket_are_preserved(sample):
    """TRAP-02 TRAP-08"""
    first = sample['tickets'][0]
    assert first['ticket'] == '00107'
    assert first['paid_cents'] == 10_001


def test_quoted_multiline_keeps_physical_line_range(sample):
    """TRAP-03"""
    first = sample['tickets'][0]
    assert (first['line'], first['end_line']) == (2, 3)
    assert first['raw'][-1] == '巡演三联票\n手工核对纸联'
    assert sample['funding']['sources'][0]['rows'] == 22


def test_repeated_header_and_empty_line_are_counted(sample):
    """TRAP-04"""
    sources = sample['funding']['sources'][0]
    assert (sources['headers'], sources['blank'], sources['accepted'], sources['isolated']) == (2, 1, 12, 7)


def test_extra_column_enters_quarantine(sample):
    """TRAP-05"""
    wrong = next(row for row in sample['quarantine'] if row['code'] == 'COLUMN_COUNT')
    assert wrong['raw'][0] == '00992'
    assert wrong['detail'] == {'expected': 6, 'actual': 7}


def test_mixed_money_formats_are_exact(sample):
    """TRAP-06 TRAP-10 TRAP-15"""
    receipts = {item['ticket']: item['paid_cents'] for item in sample['tickets']}
    assert [receipts[code] for code in ('00110', '00111', '00112')] == [123_456, 8_888, 1_500]
    assert sum(receipts.values()) == 157_746
    assert cents('０．０１', '元') == 1


def test_missing_amount_and_conflicting_tickets_are_not_funded(sample):
    """TRAP-07 TRAP-14"""
    assert not {'00990', '00991'} & {row['ticket'] for row in sample['tickets']}
    errors = [row for row in sample['quarantine'] if row['code'] == 'TICKET_CONFLICT']
    assert [row['raw'][2] for row in errors] == ['30.00', '33.00']
    assert sample['reason_counts']['MISSING_VALUE'] == 1


def test_intake_api_filters_duplicate_evidence(client):
    response = client.get('/api/intake/sample', params={'view': 'isolated', 'q': 'TICKET_DUPLICATE'})
    data = response.json()
    assert response.status_code == 200 and data['total'] == 1
    assert data['items'][0]['detail'] == {'retained_line': 6}


def test_malformed_money_never_rounds_silently():
    for value, unit in [('99.001', '元'), ('1,23.45', '元'), ('1.0', '分'), ('0', '元')]:
        with pytest.raises(RowError, match='INVALID_AMOUNT'):
            cents(value, unit)


def test_empty_blank_and_truncated_ticket_sources(upload, files):
    for raw, code in [(b'', 'FILE_EMPTY'), (b'\n  \n', 'FILE_BLANK'),
                      (files['tickets.csv'] + b'"unterminated', 'FILE_CSV')]:
        result = upload({**files, 'tickets.csv': raw})
        assert (result.status_code, result.json()['code']) == (422, code)
