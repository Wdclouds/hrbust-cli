"""
HRBUST Toolkit (哈尔滨理工大学数字化校园全栈工具箱)
"""

__version__ = "1.0.0"
__author__ = "Haiying Kou (Wdclouds)"

from .core.network import CampusSession, check_campus_network
from .core.jwzx import JwzxEngine
from .core.water import WaterEngine
from .services.water_svc import WaterService
from .services.room_svc import RoomService
from .services.schedule_svc import ScheduleService
from .services.news_svc import NewsService

__all__ = [
    "CampusSession",
    "check_campus_network",
    "JwzxEngine",
    "WaterEngine",
    "WaterService",
    "RoomService",
    "ScheduleService",
    "NewsService",
]
