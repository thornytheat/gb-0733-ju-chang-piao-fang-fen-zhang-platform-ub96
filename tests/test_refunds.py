from app.pipeline import compute


def test_refunds_use_published_show_share_and_leave_other_shows_intact(sample):
    rows = {row['show']: row for row in sample['funding']['ledger'] if row['ticket'] == '00107'}
    assert [(rows[show]['allocated_cents'], rows[show]['payable_cents']) for show in ('A-LAKE', 'B-RAIN', 'C-DUSK')] == [
        (3334, 3334), (3334, 3334), (3333, 0),
    ]
    assert rows['C-DUSK']['refunded_cents'] == 3333


def test_remaining_cap_is_cumulative_insufficient_rows_do_not_consume_it(sample):
    approved = [row for row in sample['refunds'] if row['ticket'] == '00107']
    assert [(row['refund_id'], row['reversal_cents'], row['cumulative_cents'], row['remaining_cents']) for row in approved] == [
        ('R107-01', -1000, 1000, 2333), ('R107-03', -2333, 3333, 0),
    ]
    caps = {row['key']: row['detail']['available_cents'] for row in sample['quarantine'] if row['code'] == 'REFUND_CAP_EXCEEDED'}
    assert caps == {'R107-02': 2333, 'R107-04': 0}


def test_partial_refund_on_a_cancelled_show_stays_unsettled(sample):
    row = next(row for row in sample['funding']['ledger'] if (row['ticket'], row['show']) == ('00108', 'C-DUSK'))
    assert (row['allocated_cents'], row['refunded_cents'], row['payable_cents'], row['unsettled_cents']) == (4001, 2000, 0, 2001)
    assert row['code'] == 'CANCELLED_RESIDUAL' and row['scan_id'] == 'S108-C'


def test_refund_event_normalization_and_conflict_are_distinct(sample):
    assert [row['refund_id'] for row in sample['refunds']].count('R108-01') == 1
    assert not any(row['refund_id'] == 'R-CONFLICT' for row in sample['refunds'])
    assert sample['reason_counts']['REFUND_ID_DUPLICATE'] == 1
    assert sample['reason_counts']['REFUND_ID_CONFLICT'] == 2


def test_invalid_refund_reasons_are_specific(sample):
    codes = {row['key']: row['code'] for row in sample['quarantine'] if row['source'] == 'refunds.csv'}
    assert codes['R110-01'] == 'REFUND_NOT_CANCELLED'
    assert codes['R108-EARLY'] == 'REFUND_TOO_EARLY'
    assert codes['R113-01'] == 'REFUND_NO_ORIGINAL'
    assert codes['R-BAD-UNIT'] == 'INVALID_UNIT'


def test_previous_approval_cannot_be_erased_by_stale_submission(upload, files):
    """TRAP-26. 送回未包含已入账退款的旧表，须保留当前批次。"""
    first = upload(files)
    stale = {**files, 'refunds.csv': b'\n'.join(files['refunds.csv'].splitlines()[:1]) + b'\n'}
    response = upload(stale)
    assert first.status_code == 201
    assert response.status_code == 409
    assert response.json()['code'] == 'REFUND_CHANGED'
    assert response.json()['detail'] == {'refund_id': 'R107-01'}


def test_same_effective_time_resolves_by_refund_id(files, source_writer):
    when = '2026-11-19T18:05:00+08:00'
    raw = source_writer('refunds.csv', [('B', '00107', 'C-DUSK', when, 2000, '分'), ('A', '00107', 'C-DUSK', when, 2000, '分')])
    snapshot = compute('cap-tie', 'unit', {**files, 'refunds.csv': raw})
    assert [row['refund_id'] for row in snapshot['refunds']] == ['A']
    issue = next(row for row in snapshot['quarantine'] if row['key'] == 'B')
    assert issue['detail']['available_cents'] == 1333


def test_refunds_endpoint_returns_signed_reversal_and_source_line(client):
    data = client.get('/api/refunds/sample', params={'q': 'R116-01'}).json()
    record, = data['items']
    assert (record['reversal_cents'], record['line'], record['right_line']) == (-250, 8, 16)
