from app.contracts import cents, key, timestamp
from app.deduplicate import unique_records
from app.errors import Problem, RowError
from app.modules.m5_refunds.rules import check_refund


def refund_records(rows, isolates):
    for row in rows:
        values = row.values
        try:
            entry = {field: key(values[field]) for field in ('refund_id', 'ticket', 'show')}
            entry.update(refunded_at=timestamp(values['refunded_at']),
                         requested_cents=cents(values['amount'], values['unit']))
        except RowError as exc:
            isolates.add(row, exc.code, values['refund_id'])
            continue
        yield entry, row


def reverse(rows, tickets, shows, publication, isolates):
    originals = {(row['ticket'], row['show']): row for row in publication['allocations']}
    running, approved = {}, []
    candidates = unique_records(refund_records(rows, isolates), lambda item: item['refund_id'],
                                'REFUND_ID_DUPLICATE', 'REFUND_ID_CONFLICT', isolates)
    for event in sorted(candidates, key=lambda item: (item['refunded_at'], item['refund_id'])):
        code, detail = check_refund(event, tickets, shows, originals, running)
        if code:
            isolates.add_record(event, code, event['refund_id'], **detail)
            continue
        pair = (event['ticket'], event['show'])
        original = originals[pair]
        running[pair] = detail['used_cents'] + event['requested_cents']
        approved.append({**event, **detail, 'reversal_cents': -event['requested_cents'],
                         'cumulative_cents': running[pair], 'remaining_cents': detail['original_cents'] - running[pair],
                         'publication_id': publication['publication_id'], 'right_line': original['right_line'],
                         'show_line': shows[event['show']]['line'],
                         'cancelled_at': shows[event['show']]['cancelled_at']})
    return approved


def preserve_approved(prior, proposed):
    fields = ('ticket', 'show', 'refunded_at', 'reversal_cents', 'publication_id', 'cancelled_at')
    by_id = {row['refund_id']: tuple(row[field] for field in fields) for row in proposed}
    for event in prior:
        if by_id.get(event['refund_id']) != tuple(event[field] for field in fields):
            raise Problem(409, 'REFUND_CHANGED', {'refund_id': event['refund_id']})
