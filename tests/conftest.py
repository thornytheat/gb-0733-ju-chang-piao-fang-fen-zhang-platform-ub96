import csv
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.config import SOURCE_COLUMNS
from app.main import create_app
from app.pipeline import compute
from app.sources import sample_sources


@pytest.fixture
def files():
    return sample_sources()


@pytest.fixture(scope='module')
def sample():
    return compute('tour-demo', 'fixture', sample_sources())


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'ledger.sqlite3')) as session:
        yield session


@pytest.fixture
def source_writer():
    def build(source, rows):
        stream = StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(SOURCE_COLUMNS[source])
        writer.writerows(rows)
        return stream.getvalue().encode()
    return build


@pytest.fixture
def upload(client):
    def post(files, book='tour-separate'):
        return client.post('/api/runs', data={'book': book},
                           files=[('files', (name, payload, 'text/csv')) for name, payload in files.items()])
    return post
