"""
HRBUST Toolkit -> Hermes Agent 原生工具适配器
在 Hermes 中引入此模块即可直接赋予 Agent 查浴室、查自习、查课表的能力
"""

from typing import Dict, Any, List
from ..services.water_svc import WaterService
from ..services.news_svc import NewsService
from ..core.network import check_campus_network

def hermes_get_bath_status(token: str, account: str) -> List[Dict[str, Any]]:
    """
    [Hermes Tool] 查询哈理工各浴室与热水的实时空闲大盘
    """
    if not check_campus_network():
        return [{"error": "未连接哈理工校园网"}]

    import json
    from ..core.water import WaterEngine
    raw_info = WaterEngine.aes_encrypt(json.dumps({"ano": account}), account)
    svc = WaterService()
    return svc.get_dashboard(raw_info, token)

def hermes_get_daily_news() -> List[Dict[str, Any]]:
    """
    [Hermes Tool] 获取哈理工今日最新教务公告与新闻简报
    """
    if not check_campus_network():
        return [{"error": "未连接哈理工校园网"}]
    svc = NewsService()
    return svc.get_daily_brief()
