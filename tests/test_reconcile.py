from app.modules.m6_reconcile.service import reconcile


def test_net_receipts_equal_venue_payable_and_pending(sample):
    totals = sample['funding']['totals']
    assert totals == {'paid_cents': 157746, 'allocated_cents': 154548, 'unallocated_cents': 3198,
                      'refunded_cents': 5583, 'net_cents': 152163, 'payable_cents': 135546,
                      'unsettled_cents': 16617, 'difference_cents': 0, 'gap_cents': 19002,
                      'scan_count': 7, 'ticket_count': 12}
    assert totals['net_cents'] == totals['payable_cents'] + totals['unsettled_cents']


def test_show_gap_is_explained_even_when_accounting_difference_is_zero(sample):
    show = next(row for row in sample['funding']['shows'] if row['show'] == 'C-DUSK')
    assert (show['gap_cents'], show['refunded_cents'], show['unsettled_cents'], show['difference_cents']) == (7584, 5583, 2001, 0)


def test_two_shows_are_aggregated_into_same_venue(sample):
    venue = next(row for row in sample['funding']['venues'] if row['venue'] == '海棠剧场')
    assert (venue['shows'], venue['payable_cents'], venue['allocated_cents'], venue['scan_count']) == (2, 6756, 10256, 3)


def test_source_rows_reconcile_across_all_five_files(sample):
    sources = sample['funding']['sources']
    assert sum(row['accepted'] for row in sources) == 43
    assert sum(row['rows'] for row in sources) == 83
    assert sum(row['isolated'] for row in sources) == 33
    assert sum(row['headers'] + row['blank'] for row in sources) == 7
    assert all(row['difference'] == 0 for row in sources)


def test_each_ticket_preserves_its_own_balance_not_just_global_sum(sample):
    tickets = {row['ticket']: row for row in sample['funding']['tickets']}
    assert all(row['difference_cents'] == 0 for row in tickets.values())
    assert (tickets['00109']['payable_cents'], tickets['00109']['unsettled_cents']) == (0, 1999)
    assert (tickets['00107']['net_cents'], tickets['00107']['unsettled_cents']) == (6668, 0)


def test_reconcile_detects_shift_between_two_tickets_even_if_total_matches(sample):
    publication = dict(sample['publication'])
    publication['allocations'] = [{**row, 'allocated_cents': row['allocated_cents'] + {'00110': 1, '00117': -1}.get(row['ticket'], 0)}
                                  for row in publication['allocations']]
    result = reconcile({row['ticket']: row for row in sample['tickets']}, {row['show']: row for row in sample['shows']},
                       sample['scans'], sample['refunds'], publication, sample['funding']['sources'])
    assert result['checks']['funding'] is True
    assert result['checks']['ticket_balances'] is False
    assert result['balanced'] is False


def test_reconcile_endpoint_only_returns_requested_ticket(client):
    response = client.get('/api/reconcile/sample', params={'view': 'tickets', 'q': '00108'})
    assert response.status_code == 200
    data = response.json()
    row, = data['items']
    assert (row['net_cents'], row['unsettled_cents'], row['difference_cents']) == (4001, 4001, 0)
    assert data['balanced'] is True and all(data['checks'].values())
