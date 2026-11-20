import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.store import Store


def test_concurrent_publication_commits_one_batch(tmp_path, files):
    store = Store(tmp_path / 'parallel.sqlite3')
    store.initialize()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: store.commit('one-ledger', files), range(6)))
    assert sum(not reused for _, reused in results) == 1
    assert len({reply['manifest']['run_id'] for reply, _ in results}) == 1
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT count(*) FROM runs').fetchone() == (1,)
        assert db.execute('SELECT count(*) FROM run_inputs').fetchone() == (5,)


def test_failure_after_publication_insert_rolls_back_all_tables(tmp_path, files):
    store = Store(tmp_path / 'atomic.sqlite3')
    store.initialize()
    with sqlite3.connect(store.path) as db:
        db.executescript("""
            CREATE TRIGGER fail_source BEFORE INSERT ON run_inputs
            WHEN NEW.source = 'rights.csv'
            BEGIN SELECT RAISE(ABORT, 'storage stopped'); END;
        """)
    with pytest.raises(sqlite3.IntegrityError, match='storage stopped'):
        store.commit('atomic-ledger', files)
    with sqlite3.connect(store.path) as db:
        for table in ('publications', 'runs', 'run_inputs'):
            assert db.execute(f'SELECT count(*) FROM {table}').fetchone() == (0,)
        db.execute('DROP TRIGGER fail_source')
    snapshot, reused = store.commit('atomic-ledger', files)
    assert not reused and snapshot['funding']['balanced']


def test_followup_cancellation_reuses_original_and_preserves_batch_history(client, upload, files):
    raw_shows = files['shows.csv'].replace(b',2026-11-19T18:00:00+08:00\n', b',\n')
    blank_refunds = files['refunds.csv'].splitlines(keepends=True)[0]
    old = {**files, 'shows.csv': raw_shows, 'refunds.csv': blank_refunds}
    original = upload(old).json()
    new_reply = upload(files)
    assert new_reply.status_code == 201
    revised = new_reply.json()
    assert revised['manifest']['origin_run'] == original['run_id']
    assert revised['manifest']['publication_id'] == original['manifest']['publication_id']
    assert revised['totals']['refunded_cents'] == 5583
    root = client.get('/').text
    assert revised['run_id'] in root and original['run_id'] not in root
    rerun = upload(old)
    assert rerun.status_code == 200 and rerun.json()['run_id'] == original['run_id']
    assert revised['run_id'] in client.get('/').text


def test_original_weights_cannot_be_rewritten_under_same_book(upload, files):
    first = upload(files)
    rights = files['rights.csv'].replace(b'00107,C-DUSK,1', b'00107,C-DUSK,5')
    changed = upload({**files, 'rights.csv': rights})
    assert first.status_code == 201
    assert (changed.status_code, changed.json()['code']) == (409, 'PUBLICATION_CHANGED')
    assert upload({**files, 'rights.csv': rights}, book='independent-book').status_code == 201


def test_new_revision_can_use_remaining_refund_capacity(client, upload, files):
    head = upload(files).json()['run_id']
    late = b'R108-FINAL,00108,C-DUSK,2026-11-19T21:00:00+08:00,2001,' + '分\n'.encode()
    changed = upload({**files, 'refunds.csv': files['refunds.csv'] + late})
    assert changed.status_code == 201
    result = changed.json()
    assert result['manifest']['previous_run'] == head
    assert result['totals']['refunded_cents'] == 7584
    items = client.get(f"/api/refunds/{result['run_id']}", params={'q': 'R108-FINAL'}).json()['items']
    assert items[0]['remaining_cents'] == 0
