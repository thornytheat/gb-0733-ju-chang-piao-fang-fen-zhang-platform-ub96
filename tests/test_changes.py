"""换场登记、结转守恒与新旧场并存的业务回归。"""
import csv
import io
from zipfile import ZipFile

from app.manifest import changes_digest
from app.modules.m8_changes.service import (
    apply_changes,
    parse_registration,
    validate_registration,
)
from app.pipeline import compute
from app.sources import sample_changes
from app.store import Store


def change_form(**overrides):
    base = {'old_show': 'B-RAIN', 'new_show': 'B-RAIN-9', 'title': '换场测试场', 'venue': '测试新馆',
            'effective_at': '2026-11-19T12:00:00+08:00', 'opens': '2026-11-19T18:00:00+08:00',
            'closes': '2026-11-19T22:00:00+08:00'}
    base.update(overrides)
    return base


def test_registration_normalizes_to_utc_and_has_stable_id():
    entry = parse_registration(change_form(), '2026-11-19T09:30:00+08:00')
    assert entry['effective_at'] == '2026-11-19T04:00:00+00:00'
    assert entry['opens'] == '2026-11-19T10:00:00+00:00'
    assert entry['change_id'].startswith('chg_') and len(entry['change_id']) == 24
    again = parse_registration(change_form(), '2026-11-19T09:30:00+08:00')
    assert again['change_id'] == entry['change_id']


def test_registration_validates_unknown_old_show_and_duplicate_new_show(sample):
    shows = {row['show']: row for row in sample['shows']}
    entry = parse_registration(change_form(old_show='NO-SUCH'), '2026-11-19T09:30:00+00:00')
    from app.errors import Problem
    try:
        validate_registration(entry, shows, sample['changes'])
    except Problem as exc:
        assert exc.code == 'CHANGE_OLD_SHOW_UNKNOWN'
    else:
        raise AssertionError('应当拒收未知原场次')
    taken = parse_registration(change_form(old_show='A-LAKE', new_show='B-RAIN-2'),
                               '2026-11-19T09:30:00+00:00')
    try:
        validate_registration(taken, shows, sample['changes'])
    except Problem as exc:
        assert exc.code == 'CHANGE_NEW_SHOW_EXISTS'
    else:
        raise AssertionError('应当拒收已占用的新场次键')


def test_cancelled_show_cannot_be_transferred(sample):
    from app.errors import Problem
    shows = {row['show']: row for row in sample['shows']}
    entry = parse_registration(change_form(old_show='C-DUSK', new_show='C-DUSK-2'),
                               '2026-11-19T09:30:00+08:00')
    try:
        validate_registration(entry, shows, [])
    except Problem as exc:
        assert exc.code == 'CHANGE_TARGET_SUPERSEDED'
    else:
        raise AssertionError('停演场不能再换场')


def test_window_check_rejects_effective_after_opening():
    from app.errors import Problem
    try:
        parse_registration(change_form(effective_at='2026-11-19T19:00:00+08:00'),
                           '2026-11-19T09:30:00+08:00')
    except Problem as exc:
        assert exc.code == 'CHANGE_WINDOW_INVALID'
    else:
        raise AssertionError('生效时刻晚于核销起点应当拒收')


def test_apply_changes_conserves_funds_and_keeps_original_publication(sample):
    base_shows = {row['show']: row for row in sample['shows'] if not row.get('transferred_from')}
    base_rights = [row for row in sample['rights'] if row.get('source') != 'transfer']
    old_scans = [row for row in sample['scans'] if row['show'] in base_shows]
    catalogue, rights, adjusted, carries = apply_changes(
        sample['publication'], base_shows, base_rights, sample['changes'], old_scans, sample['refunds'])
    original = sum(row['allocated_cents'] for row in sample['publication']['allocations'])
    assert sum(row['allocated_cents'] for row in adjusted) + sum(row['carried_cents'] for row in carries) == original
    for row in carries:
        matching = next(item for item in adjusted
                        if item['ticket'] == row['ticket'] and item['show'] == row['old_show'])
        assert matching['retained_cents'] + row['carried_cents'] == \
            next(item for item in sample['publication']['allocations']
                 if item['ticket'] == row['ticket'] and item['show'] == row['old_show'])['allocated_cents']
    assert catalogue['B-RAIN']['superseded_by'] == 'B-RAIN-2'
    assert catalogue['B-RAIN-2']['transferred_from'] == 'B-RAIN'


def test_scanned_old_show_share_is_retained_not_carried(sample):
    card = sample['change_review']['cards'][0]
    by_ticket = {row['ticket']: row for row in card['entries']}
    # 旧场全部 6 张票都在核对卡内；已核销的票全额保留，未核销的票全额结转
    assert set(by_ticket) == {'00107', '00110', '00111', '00114', '00116', '00117'}
    assert by_ticket['00107']['carried_cents'] == 0 and by_ticket['00107']['retained_cents'] == 3334
    assert by_ticket['00111']['retained_cents'] == 0 and by_ticket['00111']['carried_cents'] == 6666
    totals = card['totals']
    assert totals['original_cents'] == totals['retained_cents'] + totals['carried_cents']
    assert card['conserved'] is True
    # 结转行本身只包含有未结额的票
    assert {row['ticket'] for row in sample['carries']} == {'00111', '00114', '00116'}


def test_change_digest_changes_run_identifier_but_keeps_publication(client, upload, files):
    first = upload(files)
    assert first.status_code == 201
    run_before = first.json()['run_id']
    store = client.app.state.store
    entry = parse_registration(change_form(new_show='B-RAIN-9'), '2026-11-19T09:30:00+08:00')
    snapshot = store.latest('tour-separate')
    entry = validate_registration(entry, {row['show']: row for row in snapshot['shows']}, [])
    assert store.save_change('tour-separate', entry) is True
    second = upload(files)
    assert second.status_code == 201 and second.json()['run_id'] != run_before
    assert second.json()['manifest']['publication_id'] == first.json()['manifest']['publication_id']


def test_rerun_same_inputs_and_changes_reuses_run_without_duplicates(client, upload, files):
    upload(files)
    store = client.app.state.store
    entry = parse_registration(change_form(new_show='B-RAIN-9'), '2026-11-19T09:30:00+08:00')
    snapshot = store.latest('tour-separate')
    entry = validate_registration(entry, {row['show']: row for row in snapshot['shows']}, [])
    store.save_change('tour-separate', entry)
    first = upload(files).json()
    replay = upload(files)
    assert replay.status_code == 200 and replay.json()['run_id'] == first['run_id']
    import sqlite3
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM show_changes WHERE book = 'tour-separate'").fetchone() == (1,)
        runs = [row[0] for row in db.execute('SELECT id FROM runs')]
        assert runs.count(first['run_id']) == 1


def test_duplicate_registration_is_idempotent_and_conflicting_content_rejected(client, upload, files):
    upload(files)
    store = client.app.state.store
    entry = parse_registration(change_form(new_show='B-RAIN-9'), '2026-11-19T09:30:00+08:00')
    snapshot = store.latest('tour-separate')
    entry = validate_registration(entry, {row['show']: row for row in snapshot['shows']}, [])
    assert store.save_change('tour-separate', entry) is True
    assert store.save_change('tour-separate', dict(entry)) is False
    from app.errors import Problem
    conflict = dict(entry, venue='被篡改的场馆')
    try:
        store.save_change('tour-separate', conflict)
    except Problem as exc:
        assert exc.code == 'CHANGE_CONFLICT'
    else:
        raise AssertionError('同编号不同内容必须拒收')


def test_failed_registration_leaves_ledger_untouched(client, upload, files):
    upload(files)
    store = client.app.state.store
    bad = client.post('/api/changes/tour-separate', data=change_form(old_show='NO-SUCH'))
    assert bad.status_code == 422 and bad.json()['code'] == 'CHANGE_OLD_SHOW_UNKNOWN'
    assert store.changes('tour-separate') == []


def test_http_registration_is_idempotent_for_identical_content(client):
    client.post('/api/runs/sample')
    payload = {'old_show': 'B-RAIN', 'new_show': 'B-RAIN-2', 'title': '雨之停驻·新馆专场',
               'venue': '滨江演艺中心', 'effective_at': '2026-11-19T12:00:00+08:00',
               'opens': '2026-11-19T18:00:00+08:00', 'closes': '2026-11-19T22:00:00+08:00'}
    first = client.post('/api/changes/tour-demo', data=payload)
    second = client.post('/api/changes/tour-demo', data=payload)
    assert first.status_code == 200 and first.json()['created'] is False
    assert second.status_code == 200 and second.json() == first.json()
    rows = client.get('/api/changes/tour-demo').json()['changes']
    assert len(rows) == 1


def test_change_review_endpoint_and_export_bundle(client, upload, files):
    upload(files)
    store = client.app.state.store
    entry = parse_registration(change_form(new_show='B-RAIN-9'), '2026-11-19T09:30:00+08:00')
    snapshot = store.latest('tour-separate')
    entry = validate_registration(entry, {row['show']: row for row in snapshot['shows']}, [])
    store.save_change('tour-separate', entry)
    run_id = upload(files).json()['run_id']
    review = client.get(f'/api/changes/review/{run_id}')
    assert review.status_code == 200 and review.json()['review']['balanced'] is True
    response = client.get(f'/api/changes/review/{run_id}/export')
    assert response.status_code == 200 and response.content.startswith(b'PK')
    with ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {'evidence/show-changes.csv', 'evidence/carry-ledger.csv',
                'evidence/change-review.csv', 'evidence/change-totals.csv', 'manifest.json'} <= names
        rows = list(csv.DictReader(io.StringIO(archive.read('evidence/carry-ledger.csv').decode('utf-8-sig'))))
        assert rows and all(int(row['allocated_cents']) == int(row['carried_cents']) for row in rows)
        totals = list(csv.DictReader(io.StringIO(archive.read('evidence/change-totals.csv').decode('utf-8-sig'))))
        assert totals and int(totals[0]['retained_cents']) + int(totals[0]['carried_cents']) == int(totals[0]['original_cents'])


def test_changes_page_renders_and_sample_change_is_seeded(client):
    page = client.get('/changes')
    assert page.status_code == 200 and '巡演换场核对' in page.text
    listed = client.get('/api/changes/tour-demo').json()
    assert listed['changes'] and listed['changes'][0]['new_show'] == 'B-RAIN-2'


def test_new_show_refund_uses_carry_cap(sample):
    carried = next(row for row in sample['carries'] if row['ticket'] == '00111')
    assert carried['allocated_cents'] == 6666
    # 新场退款限额来自结转额，而非原分账表
    origins = {(row['ticket'], row['show']): row for row in sample['carries']}
    assert origins[('00111', 'B-RAIN-2')]['allocated_cents'] == 6666


def test_changes_digest_is_stable_for_same_registrations():
    once = changes_digest(sample_changes())
    twice = changes_digest(sample_changes())
    assert once == twice


def test_new_show_refund_reverses_against_carry_cap_end_to_end(files):
    files['refunds.csv'] = files['refunds.csv'] + (
        b'R200-01,00111,B-RAIN-2,2026-11-20T10:00:00+08:00,10.00,\xe5\x85\x83\n'
        b'R200-02,00114,B-RAIN-2,2026-11-20T10:00:00+08:00,99999,\xe5\x88\x86\n'
        b'R200-03,00116,B-RAIN-2,2026-11-18T10:00:00+08:00,50,\xe5\x88\x86\n')
    snap = compute('tour-demo', 'carry-refund', files, sample_changes())
    assert snap['funding']['balanced'] is True
    new_refund = next(row for row in snap['refunds'] if row['refund_id'] == 'R200-01')
    assert (new_refund['show'], new_refund['remaining_cents']) == ('B-RAIN-2', 5666)
    codes = {row['key']: row['code'] for row in snap['quarantine'] if row['key'].startswith('R200')}
    assert codes == {'R200-02': 'REFUND_CARRY_EXCEEDED', 'R200-03': 'REFUND_TOO_EARLY'}
    ledger = next(row for row in snap['funding']['ledger']
                  if (row['ticket'], row['show']) == ('00111', 'B-RAIN-2'))
    assert (ledger['allocated_cents'], ledger['refunded_cents'],
            ledger['payable_cents'], ledger['unsettled_cents']) == (6666, 1000, 5666, 0)


def test_pipeline_without_changes_keeps_legacy_shape(files):
    snap = compute('plain-book', 'plain-run', files)
    assert snap['manifest']['changes_digest'] is None and snap['changes'] == []
    assert snap['carries'] == [] and snap['funding']['checks']['carry_conservation'] is True
    assert snap['funding']['totals']['carried_cents'] == 0
