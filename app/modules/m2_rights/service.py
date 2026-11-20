from app.contracts import key, weight
from app.deduplicate import unique_records
from app.errors import RowError
from app.modules.m2_rights.shows import catalogue


def right_records(rows, tickets, shows, isolates):
    for row in rows:
        values = row.values
        try:
            ticket, show = key(values['ticket']), key(values['show'])
            if ticket not in tickets:
                raise RowError('TICKET_UNKNOWN')
            if show not in shows:
                raise RowError('SHOW_UNKNOWN')
            record = {'ticket': ticket, 'show': show, 'weight': weight(values['weight']),
                      'eligible': shows[show]['publication_status'] == 'open'}
        except RowError as exc:
            isolates.add(row, exc.code, f"{values['ticket']}/{values['show']}")
            continue
        yield record, row


def resolve(show_rows, right_rows, tickets, isolates):
    shows = catalogue(show_rows, isolates)
    rights = list(unique_records(right_records(right_rows, tickets, shows, isolates),
                                 lambda item: (item['ticket'], item['show']),
                                 'RIGHT_DUPLICATE', 'RIGHT_CONFLICT', isolates))
    rights.sort(key=lambda item: (item['ticket'], item['show']))
    return shows, rights
