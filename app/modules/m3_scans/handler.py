from fastapi import APIRouter, Depends, Request

from app.browse import Browse, isolated, snapshot_for

router = APIRouter(prefix='/api/scans')


@router.get('/{run_id}')
def scans(request: Request, run_id: str, browse: Browse = Depends()):
    snapshot = snapshot_for(request, run_id)
    rows = browse.choose({'accepted': snapshot['scans'], 'isolated': isolated(snapshot, 'scans.csv')})
    return browse.page(rows)
