"""
HRBUST Toolkit 生态适配器导出
"""

from .hermes_tool import hermes_get_bath_status, hermes_get_daily_news
from .astrbot_plugin.main import AstrBotHrbustPlugin

__all__ = [
    "hermes_get_bath_status",
    "hermes_get_daily_news",
    "AstrBotHrbustPlugin",
]
