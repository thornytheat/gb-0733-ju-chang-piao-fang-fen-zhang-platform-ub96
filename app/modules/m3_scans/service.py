from app.contracts import key, text, timestamp
from app.deduplicate import unique_records
from app.errors import RowError


def scan_records(rows, isolates):
    for row in rows:
        values = row.values
        try:
            entry = {field: key(values[field]) for field in ('scan_id', 'ticket', 'show')}
            entry.update(scanned_at=timestamp(values['scanned_at']), gate=text(values['gate']))
        except RowError as exc:
            isolates.add(row, exc.code, values['scan_id'])
            continue
        yield entry, row


def check_scan(entry, tickets, shows, rights, retained):
    ticket, show = entry['ticket'], entry['show']
    pair = (ticket, show)
    if ticket not in tickets:
        return 'TICKET_UNKNOWN'
    if show not in shows:
        return 'SHOW_UNKNOWN'
    if pair not in rights:
        return 'RIGHT_MISSING'
    event_at = entry['scanned_at']
    performance = shows[show]
    if event_at < tickets[ticket]['paid_at']:
        return 'SCAN_BEFORE_PAYMENT'
    if performance['cancelled_at'] and event_at >= performance['cancelled_at']:
        return 'SCAN_AFTER_CANCELLATION'
    if not performance['opens'] <= event_at < performance['closes']:
        return 'SCAN_OUTSIDE_WINDOW'
    if pair in retained:
        return 'SCAN_REPEAT'
    return None


def admit(rows, tickets, shows, rights, isolates):
    candidates = unique_records(scan_records(rows, isolates), lambda item: item['scan_id'],
                                'SCAN_ID_DUPLICATE', 'SCAN_ID_CONFLICT', isolates)
    accepted = {}
    rights = {(item['ticket'], item['show']) for item in rights if item['eligible']}
    for entry in sorted(candidates, key=lambda item: (item['scanned_at'], item['scan_id'])):
        pair = (entry['ticket'], entry['show'])
        code = check_scan(entry, tickets, shows, rights, accepted)
        if code:
            earlier = accepted.get(pair)
            detail = {'retained_scan': earlier['scan_id'], 'retained_line': earlier['line']} if earlier else {}
            isolates.add_record(entry, code, entry['scan_id'], **detail)
        else:
            accepted[pair] = entry
    return list(accepted.values())
