from fastapi import APIRouter, Depends, Request

from app.browse import Browse, snapshot_for

router = APIRouter(prefix='/api/allocation')


@router.get('/{run_id}')
def allocations(request: Request, run_id: str, browse: Browse = Depends()):
    publication = snapshot_for(request, run_id)['publication']
    rows = browse.choose({'accepted': publication['allocations'], 'unassigned': publication['unassigned']})
    return browse.page(rows, publication_id=publication['publication_id'], origin_run=publication['origin_run'])
