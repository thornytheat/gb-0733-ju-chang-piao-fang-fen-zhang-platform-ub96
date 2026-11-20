from collections import Counter


def settlement_rows(publication, shows, scans, refunds):
    accepted = {(scan['ticket'], scan['show']): scan for scan in scans}
    reversed_cents = Counter()
    for refund in refunds:
        reversed_cents[refund['ticket'], refund['show']] += -refund['reversal_cents']
    rows = []
    for original in publication['allocations']:
        pair = (original['ticket'], original['show'])
        show = shows[original['show']]
        scan = accepted.get(pair)
        refunded = reversed_cents[pair]
        balance = original['allocated_cents'] - refunded
        payable = balance if scan and not show['cancelled_at'] else 0
        pending = balance - payable
        code = ''
        if pending:
            code = 'CANCELLED_RESIDUAL' if show['cancelled_at'] else 'AWAITING_SCAN'
        rows.append({**original, 'refunded_cents': refunded, 'net_cents': balance,
                     'payable_cents': payable, 'unsettled_cents': pending, 'code': code,
                     'scan_id': scan['scan_id'] if scan else '', 'scan_line': scan['line'] if scan else None,
                     'cancelled_at': show['cancelled_at']})
    return rows
