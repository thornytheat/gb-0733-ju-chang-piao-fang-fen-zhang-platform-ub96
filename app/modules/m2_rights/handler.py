from fastapi import APIRouter, Depends, Request

from app.browse import Browse, isolated, snapshot_for

router = APIRouter(prefix='/api/rights')


@router.get('/{run_id}')
def rights(request: Request, run_id: str, browse: Browse = Depends()):
    snapshot = snapshot_for(request, run_id)
    rows = browse.choose({'accepted': snapshot['rights'], 'shows': snapshot['shows'],
                          'isolated': isolated(snapshot, 'shows.csv', 'rights.csv')})
    return browse.page(rows)
