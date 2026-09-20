"""
HRBUST Toolkit 业务服务层导出
"""

from .water_svc import WaterService
from .room_svc import RoomService
from .schedule_svc import ScheduleService
from .news_svc import NewsService

__all__ = [
    "WaterService",
    "RoomService",
    "ScheduleService",
    "NewsService",
]
