from typing import Annotated

from fastapi import Query, Request

from app.config import PREVIEW
from app.errors import Problem
from app.reasons import REASONS


class Browse:
    def __init__(self, q: Annotated[str, Query(max_length=64)] = '',
                 show: Annotated[str, Query(max_length=64)] = '',
                 view: Annotated[str, Query(max_length=20)] = 'accepted',
                 offset: Annotated[int, Query(ge=0)] = 0,
                 limit: Annotated[int, Query(ge=1, le=200)] = 50):
        self.q, self.show, self.view = q.strip().casefold(), show, view
        self.offset, self.limit = offset, limit

    def choose(self, views):
        if self.view not in views:
            raise Problem(422, 'VIEW_UNKNOWN', {'allowed': list(views)})
        return views[self.view]

    def page(self, entries, **extra):
        def matches(row):
            tokens = [str(row.get(field, '')) for field in ('ticket', 'show', 'venue', 'key', 'scan_id', 'refund_id', 'code')]
            if 'raw' in row:
                tokens.extend(row['raw'])
            return ((not self.show or self.show == row.get('show') or self.show in row.get('raw', []))
                    and (not self.q or any(self.q in token.casefold() for token in tokens)))

        found = [row for row in entries if matches(row)]
        return {'items': found[self.offset:self.offset + self.limit], 'total': len(found),
                'offset': self.offset, 'limit': self.limit, **extra}


def snapshot_for(request: Request, run_id):
    return request.app.state.preview if run_id == PREVIEW else request.app.state.store.get(run_id)


def isolated(snapshot, *sources):
    return [{**row, 'reason': REASONS[row['code']]} for row in snapshot['quarantine']
            if not sources or row['source'] in sources]
