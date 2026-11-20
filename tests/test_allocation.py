from app.modules.m4_allocation.rules import split_cents


def test_equal_remainders_use_stable_show_key_and_conserve(sample):
    """TRAP-24. 逐场四舍五入得到 100.02 元，原实收为 100.01 元。"""
    entries = [row for row in sample['publication']['allocations'] if row['ticket'] == '00107']
    assert [(row['show'], row['allocated_cents']) for row in entries] == [
        ('A-LAKE', 3334), ('B-RAIN', 3334), ('C-DUSK', 3333),
    ]
    assert sum(round(10_001 / 3) for _ in entries) == 10_002
    assert sum(row['allocated_cents'] for row in entries) == 10_001


def test_weighted_split_respects_larger_remainder_first(sample):
    entries = {row['show']: row for row in sample['publication']['allocations'] if row['ticket'] == '00108'}
    assert entries['C-DUSK']['allocated_cents'] == 4001
    assert entries['C-DUSK']['rank'] == 1
    assert entries['A-LAKE']['allocated_cents'] == 2000


def test_zero_eligible_amount_preserves_unassigned_ticket(sample):
    rows = sample['publication']['unassigned']
    assert {row['ticket']: row['unsettled_cents'] for row in rows} == {'00109': 1999, '00113': 999, '00118': 200}
    assert not {row['show'] for row in sample['publication']['allocations']} & {'D-HOLD', 'X-UNKNOWN'}


def test_one_cent_can_yield_zero_cent_shares_in_stable_order():
    result = dict(split_cents(1, {'C': 1, 'B': 1, 'A': 1}))
    assert [result[show]['allocated_cents'] for show in 'ABC'] == [1, 0, 0]
    assert [result[show]['rank'] for show in 'ABC'] == [1, 2, 3]


def test_denominator_excludes_conflicting_rights(sample):
    row, = [row for row in sample['publication']['allocations'] if row['ticket'] == '00114']
    assert (row['show'], row['denominator'], row['allocated_cents']) == ('B-RAIN', 1, 1001)


def test_each_ticket_allocates_full_paid_amount(sample):
    original = sample['publication']
    for receipt in sample['tickets']:
        ticket = receipt['ticket']
        paid = sum(row['allocated_cents'] for row in original['allocations'] if row['ticket'] == ticket)
        reserve = sum(row['unsettled_cents'] for row in original['unassigned'] if row['ticket'] == ticket)
        assert paid + reserve == receipt['paid_cents']


def test_allocation_endpoint_exposes_rounding_evidence(client):
    data = client.get('/api/allocation/sample', params={'q': '00107', 'show': 'C-DUSK'}).json()
    row, = data['items']
    assert (row['denominator'], row['floor_cents'], row['extra_cents'], row['remainder']) == (3, 3333, 0, 2)
    assert row['right_line'] == 2 and data['publication_id'].startswith('pub_')
