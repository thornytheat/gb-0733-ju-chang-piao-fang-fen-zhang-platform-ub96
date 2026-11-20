def test_timestamp_offsets_resolve_same_logical_scan(sample):
    """TRAP-11"""
    selected = next(row for row in sample['scans'] if row['ticket'] == '00117')
    assert (selected['scan_id'], selected['scanned_at']) == ('S117-A', '2026-11-18T10:03:00+00:00')
    repeat = next(row for row in sample['quarantine'] if row['key'] == 'S117-Y')
    assert repeat['detail']['retained_scan'] == 'S117-A'


def test_late_arriving_earlier_scan_wins_replay(sample):
    """TRAP-13"""
    retained = next(row for row in sample['scans'] if row['scan_id'] == 'S107-B')
    repeated = next(row for row in sample['quarantine'] if row['key'] == 'S107-B-LATE')
    assert (retained['line'], repeated['line']) == (4, 3)
    assert repeated['code'] == 'SCAN_REPEAT'
    assert repeated['detail']['retained_line'] == 4


def test_window_start_is_inclusive_and_close_exclusive(sample):
    """TRAP-23"""
    assert 'S107-A' in {row['scan_id'] for row in sample['scans']}
    error = next(row for row in sample['quarantine'] if row['key'] == 'S112-A')
    assert error['code'] == 'SCAN_OUTSIDE_WINDOW'


def test_historic_scan_retained_but_cancellation_boundary_is_blocked(sample):
    assert 'S108-C' in {row['scan_id'] for row in sample['scans']}
    cancelled = next(row for row in sample['quarantine'] if row['key'] == 'S107-C')
    assert cancelled['code'] == 'SCAN_AFTER_CANCELLATION'


def test_conflicting_scan_id_is_removed(sample):
    assert 'S-CLASH' not in {row['scan_id'] for row in sample['scans']}
    entries = [row for row in sample['quarantine'] if row['code'] == 'SCAN_ID_CONFLICT']
    assert len(entries) == 2
    assert {row['raw'][-1] for row in entries} == {'南门', '北门'}


def test_scan_id_exact_duplicate_and_scanner_repeat_are_distinct(sample):
    assert sample['reason_counts']['SCAN_ID_DUPLICATE'] == 1
    assert sample['reason_counts']['SCAN_REPEAT'] == 2
    assert len(sample['scans']) == 7


def test_scan_api_filters_using_preserved_ticket_id(client):
    response = client.get('/api/scans/sample', params={'q': '00107', 'show': 'B-RAIN', 'limit': 1})
    assert response.status_code == 200
    assert response.json()['items'][0]['scan_id'] == 'S107-B'
    assert response.json()['total'] == 1
