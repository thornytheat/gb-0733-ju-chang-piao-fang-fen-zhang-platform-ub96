from fastapi import APIRouter, Depends, Request

from app.browse import Browse, isolated, snapshot_for

router = APIRouter(prefix='/api/refunds')


@router.get('/{run_id}')
def refunds(request: Request, run_id: str, browse: Browse = Depends()):
    snapshot = snapshot_for(request, run_id)
    rows = browse.choose({'accepted': snapshot['refunds'], 'isolated': isolated(snapshot, 'refunds.csv')})
    return browse.page(rows, original=snapshot['publication']['publication_id'])
