from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import MAX_SOURCE_BYTES, SAMPLE_BOOK, SOURCE_COLUMNS
from app.errors import Problem
from app.sources import sample_sources

router = APIRouter(prefix='/api/runs')
Book = Annotated[str, Form(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')]


def publish(request, book, sources):
    result, reused = request.app.state.store.commit(book, sources)
    return JSONResponse({'run_id': result['manifest']['run_id'], 'reused': reused, 'manifest': result['manifest'],
                         'totals': result['funding']['totals'], 'isolated': len(result['quarantine'])},
                        status_code=200 if reused else 201)


@router.post('/sample')
def publish_sample(request: Request):
    return publish(request, SAMPLE_BOOK, sample_sources())


@router.post('')
def publish_files(request: Request, book: Book, files: Annotated[list[UploadFile], File()]):
    names = [item.filename for item in files]
    if len(names) != len(SOURCE_COLUMNS) or set(names) != set(SOURCE_COLUMNS):
        raise Problem(422, 'SOURCE_SET', {'expected': list(SOURCE_COLUMNS)})
    sources = {}
    for item in files:
        raw = item.file.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise Problem(413, 'FILE_LIMIT', {'source': item.filename})
        sources[item.filename] = raw
    return publish(request, book, sources)


@router.post('/{run_id}/rerun')
def rerun(request: Request, run_id: str):
    store = request.app.state.store
    snapshot = store.get(run_id)
    return publish(request, snapshot['manifest']['book'], store.inputs(run_id))
