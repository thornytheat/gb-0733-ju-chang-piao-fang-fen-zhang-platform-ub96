from app.pipeline import compute


def test_gb18030_show_titles_decode_without_corruption(sample):
    """TRAP-01"""
    assert sample['funding']['sources'][1]['encoding'] == 'gb18030'
    assert sample['shows'][0]['title'] == '湖边来信'


def test_hold_and_later_cancellation_have_distinct_eligibility(sample):
    rights = {(right['ticket'], right['show']): right['eligible'] for right in sample['rights']}
    assert rights[('00109', 'D-HOLD')] is False
    assert rights[('00107', 'C-DUSK')] is True


def test_conflicting_rights_lose_both_rows(sample):
    errors = [row for row in sample['quarantine'] if row['code'] == 'RIGHT_CONFLICT']
    assert [(row['key'], row['raw'][2]) for row in errors] == [('00114/A-LAKE', '1'), ('00114/A-LAKE', '2')]
    assert [row['show'] for row in sample['rights'] if row['ticket'] == '00114'] == ['B-RAIN']


def test_normalized_same_weight_retains_original_source(sample):
    right = next(row for row in sample['rights'] if row['show'] == 'E-MATINEE')
    assert (right['weight'], right['raw'][2], right['line']) == (3, '３', 15)
    duplicate = next(row for row in sample['quarantine'] if row['code'] == 'RIGHT_DUPLICATE')
    assert duplicate['line'] == 21 and duplicate['detail']['retained_line'] == right['line']


def test_reference_and_window_failures_have_separate_reason_codes(sample):
    codes = {(row['source'], row['key']): row['code'] for row in sample['quarantine']}
    assert codes['rights.csv', '00118/X-UNKNOWN'] == 'SHOW_UNKNOWN'
    assert codes['rights.csv', '00990/A-LAKE'] == 'TICKET_UNKNOWN'
    assert codes['shows.csv', 'X-BAD'] == 'SHOW_WINDOW'


def test_header_only_rights_is_a_real_no_entitlement_batch(files, source_writer):
    snapshot = compute('empty-rights', 'unit', {**files, 'rights.csv': source_writer('rights.csv', [])})
    assert snapshot['funding']['sources'][2]['status'] == 'HEADER_ONLY'
    assert snapshot['rights'] == []
    assert snapshot['funding']['totals']['unsettled_cents'] == 157_746


def test_rights_api_can_inspect_cancelled_show_definition(client):
    data = client.get('/api/rights/sample', params={'view': 'shows', 'show': 'C-DUSK'}).json()
    assert data['total'] == 1
    assert data['items'][0]['cancelled_at'] == '2026-11-19T10:00:00+00:00'
