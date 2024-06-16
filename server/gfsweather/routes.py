from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import Depends, APIRouter

from database import get_session
from models import ForecastCycle, ForecastHour


router = APIRouter(prefix='/api')


@router.get("/forecast_cycle")
def cycle_datetime(session: Session = Depends(get_session)):
    start_datetime, hour_limit = session.execute(
        select(ForecastCycle.datetime, func.max(ForecastHour.hour))
        .join(ForecastCycle, ForecastHour.cycle_id == ForecastCycle.id)
        .where(ForecastCycle.is_complete == True)
        .group_by(ForecastCycle.datetime)
    ).first()
    return {
        'startDatetime': start_datetime,
        'hourLimit': hour_limit
    }
