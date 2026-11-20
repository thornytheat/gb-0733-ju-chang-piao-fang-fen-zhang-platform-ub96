def check_refund(event, tickets, shows, originals, running):
    ticket, show = event['ticket'], event['show']
    pair = (ticket, show)
    if ticket not in tickets:
        return 'TICKET_UNKNOWN', {}
    if show not in shows:
        return 'SHOW_UNKNOWN', {}
    original = originals.get(pair)
    if not original:
        return 'REFUND_NO_ORIGINAL', {}
    cancellation = shows[show]['cancelled_at']
    if cancellation is None:
        return 'REFUND_NOT_CANCELLED', {}
    if event['refunded_at'] < max(cancellation, tickets[ticket]['paid_at']):
        return 'REFUND_TOO_EARLY', {'cancelled_at': cancellation}
    cap = original['allocated_cents']
    used = running.get(pair, 0)
    detail = {'original_cents': cap, 'used_cents': used, 'available_cents': cap - used,
              'requested_cents': event['requested_cents']}
    if event['requested_cents'] > detail['available_cents']:
        return 'REFUND_CAP_EXCEEDED', detail
    return None, detail
