from app.config import SAMPLE_DIR, SOURCE_COLUMNS
from app.manifest import change_identifier
from app.modules.m1_intake.reader import read_source
from app.modules.m8_changes.service import utc_stamp


def sample_sources():
    return {name: (SAMPLE_DIR / name).read_bytes() for name in SOURCE_COLUMNS}


def sample_changes():
    """内置样例换场：B-RAIN 巡演临时换到新场馆，原场次保留、未核销未退款的份额结转。"""
    entries = [{
        'old_show': 'B-RAIN', 'new_show': 'B-RAIN-2', 'title': '雨之停驻·新馆专场', 'venue': '滨江演艺中心',
        'effective_at': utc_stamp('2026-11-19T12:00:00+08:00'),
        'opens': utc_stamp('2026-11-19T18:00:00+08:00'),
        'closes': utc_stamp('2026-11-19T22:00:00+08:00'),
        'registered_at': utc_stamp('2026-11-19T09:30:00+08:00'),
    }]
    for entry in entries:
        entry['change_id'] = change_identifier('', entry)
    return entries


class SourceSet:
    def __init__(self, source_bytes, isolates):
        self.source_bytes = source_bytes
        self.isolates = isolates
        self.stats = {name: {} for name in SOURCE_COLUMNS}

    def rows(self, name):
        return read_source(self.source_bytes[name], name, self.stats[name], self.isolates)
