import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.errors import Problem
from app.manifest import canonical, input_manifest, run_identifier
from app.pipeline import compute

SCHEMA = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('PRAGMA journal_mode = WAL')
            db.executescript(SCHEMA)

    def latest(self, book=None):
        with closing(self.connect()) as db:
            if book is None:
                row = db.execute('SELECT payload FROM runs ORDER BY sequence DESC LIMIT 1').fetchone()
            else:
                row = db.execute('SELECT payload FROM runs WHERE book = ? ORDER BY sequence DESC LIMIT 1',
                                 (book,)).fetchone()
        return json.loads(row[0]) if row else None

    def get(self, run_id):
        with closing(self.connect()) as db:
            row = db.execute('SELECT payload FROM runs WHERE id = ?', (run_id,)).fetchone()
        if not row:
            raise Problem(404, 'RUN_NOT_FOUND', {'run_id': run_id})
        return json.loads(row[0])

    def inputs(self, run_id):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT source, data FROM run_inputs WHERE run_id = ?', (run_id,)).fetchall()
        if not rows:
            raise Problem(404, 'RUN_NOT_FOUND', {'run_id': run_id})
        return dict(rows)

    def commit(self, book, sources):
        inputs = input_manifest(sources)
        identifier = run_identifier(book, inputs)
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT payload FROM runs WHERE id = ?', (identifier,)).fetchone()
            if existing:
                return json.loads(existing[0]), True
            origin = db.execute('SELECT payload FROM publications WHERE book = ?', (book,)).fetchone()
            head = db.execute('SELECT payload FROM runs WHERE book = ? ORDER BY sequence DESC LIMIT 1', (book,)).fetchone()
            snapshot = compute(book, identifier, sources, json.loads(origin[0]) if origin else None,
                               json.loads(head[0]) if head else None)
            if origin is None:
                db.execute('INSERT INTO publications VALUES (?, ?)', (book, canonical(snapshot['publication'])))
            db.execute('INSERT INTO runs SELECT ?, ?, ?, COALESCE(MAX(sequence), 0) + 1 FROM runs',
                       (identifier, book, canonical(snapshot)))
            db.executemany('INSERT INTO run_inputs VALUES (?, ?, ?)',
                           [(identifier, name, data) for name, data in sources.items()])
        return snapshot, False
