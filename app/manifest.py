import hashlib
import json
from datetime import UTC, datetime

from app.config import RULE_VERSION, SOURCE_COLUMNS
from app.errors import Problem


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def input_manifest(sources):
    if set(sources) != set(SOURCE_COLUMNS):
        raise Problem(422, 'SOURCE_SET', {'expected': list(SOURCE_COLUMNS)})
    return [{'source': name, 'sha256': checksum(sources[name]), 'bytes': len(sources[name])}
            for name in SOURCE_COLUMNS]


def run_identifier(book, inputs, changes_digest=None):
    material = [book, RULE_VERSION, inputs, changes_digest or 'no-changes']
    return 'run_' + checksum(canonical(material))[:24]


def changes_digest(changes):
    material = [[row['change_id'], row['old_show'], row['new_show'], row['effective_at'],
                 row['title'], row['venue'], row['opens'], row['closes']] for row in changes]
    return checksum(canonical(material))


def change_identifier(book, entry):
    material = [book, entry['old_show'], entry['new_show'], entry['effective_at'],
                entry['title'], entry['venue'], entry['opens'], entry['closes']]
    return 'chg_' + checksum(canonical(material))[:20]


def publication_digest(tickets, shows, rights):
    def project(row, fields):
        return [row[field] for field in fields]

    material = {
        'tickets': [project(tickets[key], ('ticket', 'paid_at', 'paid_cents')) for key in sorted(tickets)],
        'shows': [project(shows[key], ('show', 'title', 'venue', 'publication_status', 'opens', 'closes'))
                  for key in sorted(shows)],
        'rights': [project(row, ('ticket', 'show', 'weight')) for row in rights],
    }
    return checksum(canonical(material))


def utc_now():
    return datetime.now(UTC).isoformat(timespec='seconds')
