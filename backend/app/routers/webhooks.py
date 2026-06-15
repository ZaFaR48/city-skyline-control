from fastapi import APIRouter, Depends

from ..deps import require_roles
from ..models import Role
from ..services.n8n import forward_event

router = APIRouter()


@router.post("/n8n/test", dependencies=[Depends(require_roles(Role.admin))])
async def test_n8n():
    ok = await forward_event("test.event", {"hello": "from parking control center"})
    return {"sent": ok}
