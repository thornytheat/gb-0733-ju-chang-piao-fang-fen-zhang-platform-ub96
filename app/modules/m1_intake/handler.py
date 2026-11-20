from fastapi import APIRouter, Depends, Request

from app.browse import Browse, isolated, snapshot_for

router = APIRouter(prefix='/api/intake')


@router.get('/{run_id}')
def receipts(request: Request, run_id: str, browse: Browse = Depends()):
    snapshot = snapshot_for(request, run_id)
    rows = browse.choose({'accepted': snapshot['tickets'], 'isolated': isolated(snapshot, 'tickets.csv')})
    return browse.page(rows, source=snapshot['funding']['sources'][0])
