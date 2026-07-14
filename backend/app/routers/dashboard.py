from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import DashboardSummaryOut
from ..services.dashboard import build_dashboard_summary
from ..services.performance import record_result_count


router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryOut)
async def summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await build_dashboard_summary(db)
    record_result_count(result.total_stations)
    return result
