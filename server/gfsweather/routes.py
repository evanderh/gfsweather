import os
from datetime import datetime
from fastapi import APIRouter

router = APIRouter(prefix='/api')

def get_symlink_target(symlink_path):
    if os.path.islink(symlink_path):
        return os.readlink(symlink_path)
    else:
        return None

@router.get("/forecast_cycle")
def cycle_datetime():
    current_path = os.path.join('layers', 'current')
    current_cycle = get_symlink_target(current_path)
    startDatetime = datetime.strptime(current_cycle,
                                      '%Y-%m-%dT%H/')
    hourLimit = len(os.listdir(current_path)) - 1
    
    return {
        'startDatetime': startDatetime,
        'hourLimit': hourLimit
    }
