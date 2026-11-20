from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceRow:
    source: str
    line: int
    end_line: int
    fields: tuple[str, ...]
    values: dict[str, str]

    def evidence(self):
        return {
            'source': self.source, 'line': self.line, 'end_line': self.end_line,
            'raw': list(self.fields),
        }


class Isolations:
    def __init__(self):
        self.rows: list[dict[str, Any]] = []

    def add(self, row, code, key='', **detail):
        self.rows.append({**row.evidence(), 'code': code, 'key': key, 'detail': detail})

    def add_record(self, record, code, key='', **detail):
        origin = {field: record[field] for field in ('source', 'line', 'end_line', 'raw')}
        self.rows.append({**origin, 'code': code, 'key': key, 'detail': detail})
