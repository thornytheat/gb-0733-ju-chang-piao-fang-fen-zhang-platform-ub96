import re


def test_home_actions_match_live_publish_rerun_and_export(client):
    home = client.get('/')
    assert home.status_code == 200
    assert all(text in home.text for text in ('剧场票房分账台', '核销账', '差额槽', '结算账', '票房证据', '1,521.63'))
    sample_action = re.search(r'data-run-action="([^"]+)"', home.text).group(1)
    first = client.post(sample_action)
    assert first.status_code == 201 and first.json()['reused'] is False
    run_id = first.json()['run_id']
    url = f'/?run={run_id}'
    html = client.get(url).text
    assert run_id in html and '已发布' in html
    assert len(re.findall('data-show-row="C-DUSK"', html)) == 3
    rerun_action = re.search(r'data-run-action="([^"]+/rerun)"', html).group(1)
    replay = client.post(rerun_action)
    assert replay.status_code == 200 and replay.json()['reused'] is True
    assert replay.json()['manifest'] == first.json()['manifest']
    export_action = re.search(r'href="([^"]+/export)"', html).group(1)
    before = client.get(export_action)
    assert before.status_code == 200 and before.content.startswith(b'PK')
    assert before.content == client.get(export_action).content


def test_every_module_has_a_live_preview_endpoint_and_missing_run_response(client):
    expected = {'intake': 12, 'rights': 15, 'scans': 7, 'allocation': 14, 'refunds': 4, 'reconcile': 14, 'evidence': 33}
    for module, count in expected.items():
        actual = client.get(f'/api/{module}/sample')
        assert actual.status_code == 200 and actual.json()['total'] == count
        missing = client.get(f'/api/{module}/bad-run')
        assert (missing.status_code, missing.json()['code']) == (404, 'RUN_NOT_FOUND')


def test_invalid_file_manifest_never_publishes_partial_run(client, upload, files):
    files.pop('rights.csv')
    result = upload(files)
    assert (result.status_code, result.json()['code']) == (422, 'SOURCE_SET')
    assert '样例预览' in client.get('/').text


def test_invalid_view_and_page_limit_have_422_responses(client):
    missing = client.get('/api/reconcile/sample', params={'view': 'invalid'})
    assert missing.status_code == 422 and missing.json()['code'] == 'VIEW_UNKNOWN'
    assert client.get('/api/evidence/sample', params={'limit': 201}).status_code == 422
