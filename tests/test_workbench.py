from app.presentation import NAMES


def test_seven_workbench_entries(client):
    for path, label in NAMES.items():
        response = client.get('/' + path)
        assert response.status_code == 200 and label.encode() in response.data


def test_main_page_and_clean_form(client):
    response = client.get('/')
    assert '滞期费分档对照'.encode() in response.data and b'160.00 USD' in response.data
    response = client.post('/ledger', data={'sample': 'clean'})
    assert b'0.00 USD' in response.data and b'160.00 USD' not in response.data


def test_bad_custom_source_recovers_in_place(client, dirty):
    dirty['events'] = 'bad,name\nvalue,keep\n'
    response = client.post('/notice', data={'sample': 'custom', **dirty})
    assert b'BAD_HEADER' in response.data and b'value,keep' in response.data


def test_api_path_all_stages(client):
    for path, key in [('intake', 'statistics'), ('notice', 'decisions'), ('exceptions', 'segments'), ('clock', 'counted'), ('ledger', 'differences')]:
        reply = client.post('/api/' + path, json={'sample': 'dirty'})
        assert reply.status_code == 200 and key in reply.json


def test_review_page_states_direction_and_confirmable(client):
    html = client.get('/ledger').data
    assert '本次方向'.encode() in html and '可确认金额'.encode() in html
    assert '160.00 USD'.encode() in html and '待补证'.encode() in html


def test_unsettled_gap_is_not_confirmed_money(client, dirty):
    dirty['terms'] = dirty['terms'].replace(',20,30,35,', ',20,30,80,')
    html = client.post('/ledger', data={'sample': 'custom', **dirty}).data
    assert '方向待定'.encode() in html and '暂不确认任何金额'.encode() in html
    assert '冲销暂挂'.encode() in html


def test_despatch_reversal_is_stated_not_zero(client, dirty):
    late = dict(dirty)
    late['stops'] = dirty['stops'] + 'S90,RAIN,2026-12-31T23:00Z,2027-01-01T01:30Z\n'
    html = client.post('/ledger', data={'sample': 'custom', **late}).data
    assert '速遣'.encode() in html and '全额冲销船方 155.00 USD 发票，记 -155.00 USD'.encode() in html
    assert '不按零处理'.encode() in html

