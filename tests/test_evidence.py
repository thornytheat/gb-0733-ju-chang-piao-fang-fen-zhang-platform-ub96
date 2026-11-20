import csv
import io
import json
from zipfile import ZipFile

from app.manifest import checksum
from app.modules.m7_evidence.csv_out import make_csv


def open_evidence(client):
    run_id = client.post('/api/runs/sample').json()['run_id']
    response = client.get(f'/api/evidence/{run_id}/export')
    return run_id, response, ZipFile(io.BytesIO(response.content))


def test_download_links_manifest_original_and_inputs(client, files):
    run_id, response, archive = open_evidence(client)
    with archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['run_id'] == manifest['origin_run'] == run_id
        assert manifest['rule_version'] == 'theatre-1.0.0'
        assert [row['sha256'] for row in manifest['inputs']] == [checksum(raw) for raw in files.values()]
        assert response.headers['content-disposition'] == f'attachment; filename="theatre-{run_id}.zip"'


def test_zip_integrity_manifest_covers_all_evidence_members(client):
    _, _, archive = open_evidence(client)
    with archive:
        data = json.loads(archive.read('manifest.json'))
        assert set(data['hashes']) == set(archive.namelist()) - {'manifest.json'}
        assert all(digest == checksum(archive.read(name)) for name, digest in data['hashes'].items())


def test_export_keeps_leading_zero_and_negative_cents(client):
    _, _, archive = open_evidence(client)
    with archive:
        rows = list(csv.DictReader(io.StringIO(archive.read('evidence/refunds.csv').decode('utf-8-sig'))))
        assert [(row['ticket'], row['reversal_cents']) for row in rows] == [
            ('00107', '-1000'), ('00108', '-2000'), ('00116', '-250'), ('00107', '-2333'),
        ]


def test_original_sources_are_byte_exact_for_gb18030_and_multiline(client, files):
    _, _, archive = open_evidence(client)
    with archive:
        assert archive.read('original-source/shows.csv') == files['shows.csv']
        assert archive.read('source/tickets.csv') == files['tickets.csv']


def test_reason_code_counts_match_export_rows(client):
    _, _, archive = open_evidence(client)
    with archive:
        content = archive.read('evidence/quarantine.csv').decode('utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(content)))
        assert len(rows) == 33
        exceeded = next(row for row in rows if row['key'] == 'R107-02')
        assert exceeded['code'] == 'REFUND_CAP_EXCEEDED'
        assert json.loads(exceeded['detail'])['available_cents'] == 2333


def test_evidence_endpoint_handles_filter_and_unknown_run(client):
    page = client.get('/api/evidence/sample', params={'q': 'REFUND_CAP_EXCEEDED', 'limit': 1, 'offset': 1})
    assert page.json()['total'] == 2
    assert page.json()['items'][0]['key'] == 'R107-04'
    missing = client.get('/api/evidence/does-not-exist/export')
    assert (missing.status_code, missing.json()['code']) == (404, 'RUN_NOT_FOUND')


def test_text_cells_guard_formula_start_without_touching_money():
    data = make_csv([{'note': ' =1+1', 'reversal_cents': -1000}], ('note', 'reversal_cents'))
    row, = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
    assert row == {'note': "' =1+1", 'reversal_cents': '-1000'}
