from concurrent.futures import ThreadPoolExecutor

from app.modules.runs.service import archive


def test_dirty_repeat_is_single_atomic_record(client):
    body = {'sample': 'dirty'}
    first = client.post('/api/runs', json=body)
    again = client.post('/api/runs', json=body)
    assert (first.status_code, again.status_code, again.json['created']) == (201, 200, False)
    assert first.json['snapshot'] == again.json['snapshot']
    assert len(client.get('/api/runs').json['runs']) == 1


def test_bad_run_leaves_no_history(client, dirty):
    dirty['terms'] = ''
    reply = client.post('/api/runs', json={'sources': dirty})
    assert (reply.status_code, reply.json) == (422, {'code': 'EMPTY_FILE', 'source': 'terms'})
    assert client.get('/api/runs').json['runs'] == []


def test_competing_retries_commit_once(tmp_path, dirty):
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(lambda _: archive(tmp_path / 'db', dirty), range(8)))
    assert sum(inserted for _, inserted in reports) == 1
    assert len({report['run_id'] for report, _ in reports}) == 1


def test_different_sample_creates_distinct_run(client):
    keys = [client.post('/api/runs', json={'sample': sample}).json['run_id'] for sample in ('clean', 'dirty')]
    assert len(set(keys)) == 2
    assert {r['run_id'] for r in client.get('/api/runs').json['runs']} == set(keys)


def test_manifest_hash_of_raw_source(client, dirty):
    import hashlib
    report = client.post('/api/runs', json={'sample': 'dirty'}).json['snapshot']
    assert report['source_sha256']['events'] == hashlib.sha256(dirty['events'].encode()).hexdigest()
    assert report['parameters']['currency'] == 'USD'


def test_missing_run_has_404(client):
    assert client.get('/api/runs/unknown').json['code'] == 'UNKNOWN_RUN'


def test_late_stop_flips_direction_and_old_version_survives(client, dirty):
    first = client.post('/api/runs', json={'sample': 'dirty'}).json
    assert first['snapshot']['results']['ledger']['direction'] == 'DEMURRAGE'

    late = dict(dirty)
    late['stops'] = dirty['stops'] + 'S90,RAIN,2026-12-31T23:00Z,2027-01-01T01:30Z\n'
    second = client.post('/api/runs', json={'sources': late}).json
    assert second['created'] is True
    assert second['snapshot']['results']['ledger']['direction'] == 'DESPATCH'

    # The earlier demurrage archive must remain readable alongside the new one.
    old = client.get('/api/runs/' + first['run_id']).json
    assert old['results']['ledger']['direction'] == 'DEMURRAGE'
    assert {r['run_id'] for r in client.get('/api/runs').json['runs']} == {first['run_id'], second['run_id']}


def test_same_round_rerun_does_not_double_book(client, dirty):
    late = dict(dirty)
    late['stops'] = dirty['stops'] + 'S90,RAIN,2026-12-31T23:00Z,2027-01-01T01:30Z\n'
    first = client.post('/api/runs', json={'sources': late}).json
    again = client.post('/api/runs', json={'sources': late}).json
    assert (first['created'], again['created'], again['run_id']) == (True, False, first['run_id'])
    assert len(client.get('/api/runs').json['runs']) == 1

