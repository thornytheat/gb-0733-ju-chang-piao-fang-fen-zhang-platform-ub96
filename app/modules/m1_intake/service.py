from app.contracts import cents, key, text, timestamp
from app.deduplicate import unique_records
from app.errors import Problem, RowError


def valid_tickets(rows, isolates):
    for row in rows:
        values = row.values
        try:
            record = {
                'ticket': key(values['ticket']), 'paid_at': timestamp(values['paid_at']),
                'paid_cents': cents(values['amount'], values['unit']), 'status': text(values['status']),
            }
        except RowError as exc:
            isolates.add(row, exc.code, values['ticket'])
            continue
        yield record, row


def intake(rows, isolates):
    register = unique_records(valid_tickets(rows, isolates), lambda item: item['ticket'],
                              'TICKET_DUPLICATE', 'TICKET_CONFLICT', isolates)
    tickets = {}
    for record in register:
        if record['status'] == 'paid':
            tickets[record['ticket']] = record
        else:
            isolates.add_record(record, 'TICKET_NOT_PAID', record['ticket'], status=record['status'])
    if not tickets:
        raise Problem(422, 'NO_TICKETS')
    return tickets
