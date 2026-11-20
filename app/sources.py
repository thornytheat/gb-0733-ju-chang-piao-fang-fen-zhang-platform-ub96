from app.config import SAMPLE_DIR, SOURCE_COLUMNS
from app.modules.m1_intake.reader import read_source


def sample_sources():
    return {name: (SAMPLE_DIR / name).read_bytes() for name in SOURCE_COLUMNS}


class SourceSet:
    def __init__(self, source_bytes, isolates):
        self.source_bytes = source_bytes
        self.isolates = isolates
        self.stats = {name: {} for name in SOURCE_COLUMNS}

    def rows(self, name):
        return read_source(self.source_bytes[name], name, self.stats[name], self.isolates)
