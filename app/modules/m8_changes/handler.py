import json
from typing import Annotated

from fastapi import APIRouter, Form, Request, Response

from app.browse import snapshot_for
from app.errors import Problem
from app.manifest import utc_now
from app.modules.m8_changes.bundle import build_change_bundle
from app.modules.m8_changes.service import parse_registration, validate_registration

router = APIRouter(prefix='/api/changes')
ChangeKey = Annotated[str, Form(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')]
ChangeText = Annotated[str, Form(max_length=120)]


@router.get('/{book}')
def list_changes(request: Request, book: str):
    return {'book': book, 'changes': request.app.state.store.changes(book)}


@router.post('/{book}')
def register_change(request: Request, book: str,
                    old_show: ChangeKey, new_show: ChangeKey, title: ChangeText, venue: ChangeText,
                    effective_at: Annotated[str, Form()], opens: Annotated[str, Form()],
                    closes: Annotated[str, Form()]):
    store = request.app.state.store
    entry = parse_registration({'old_show': old_show, 'new_show': new_show, 'title': title, 'venue': venue,
                                'effective_at': effective_at, 'opens': opens, 'closes': closes}, utc_now())
    existing = {row['change_id']: row for row in store.changes(book)}
    if entry['change_id'] in existing:
        return Response(status_code=200,
                        content=json.dumps({'change_id': entry['change_id'], 'created': False},
                                           ensure_ascii=False).encode(),
                        media_type='application/json')
    snapshot = store.latest(book) or (request.app.state.preview if book == request.app.state.preview['manifest']['book'] else None)
    if snapshot is None:
        raise Problem(409, 'CHANGE_OLD_SHOW_UNKNOWN', {'book': book, 'reason': '账册尚无已发布批次，无法登记换场'})
    entry = validate_registration(entry, {row['show']: row for row in snapshot['shows']}, store.changes(book))
    created = store.save_change(book, entry)
    return Response(status_code=201 if created else 200,
                    content=json.dumps({'change_id': entry['change_id'], 'created': created},
                                       ensure_ascii=False).encode(),
                    media_type='application/json')


@router.get('/review/{run_id}')
def review(request: Request, run_id: str):
    snapshot = snapshot_for(request, run_id)
    return {'manifest': snapshot['manifest'], 'review': snapshot['change_review'],
            'checks': snapshot['funding']['checks'], 'totals': snapshot['funding']['totals']}


@router.get('/review/{run_id}/export')
def export_review(request: Request, run_id: str):
    snapshot = request.app.state.store.get(run_id)
    data = build_change_bundle(snapshot)
    return Response(data, media_type='application/zip',
                    headers={'Content-Disposition': f'attachment; filename="show-changes-{run_id}.zip"'})
