from app.contracts import key, text, timestamp
from app.deduplicate import unique_records
from app.errors import Problem, RowError


def show_records(rows, isolates):
    for row in rows:
        values = row.values
        try:
            cancelled = values['cancelled_at'].strip()
            show = {
                'show': key(values['show']), 'title': text(values['title']), 'venue': text(values['venue']),
                'publication_status': text(values['publication_status']),
                'opens': timestamp(values['opens']), 'closes': timestamp(values['closes']),
                'cancelled_at': timestamp(cancelled) if cancelled else None,
            }
            if show['publication_status'] not in {'open', 'held'}:
                raise RowError('SHOW_STATUS')
            if show['opens'] >= show['closes']:
                raise RowError('SHOW_WINDOW')
        except RowError as exc:
            isolates.add(row, exc.code, values['show'])
            continue
        yield show, row


def catalogue(rows, isolates):
    shows = {show['show']: show for show in unique_records(
        show_records(rows, isolates), lambda item: item['show'], 'SHOW_DUPLICATE', 'SHOW_CONFLICT', isolates
    )}
    if not shows:
        raise Problem(422, 'NO_SHOWS')
    return shows
