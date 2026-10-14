"""
HRBUST Toolkit -> Hermes Agent 原生工具适配器
直接赋予 Hermes 查成绩、查考场座位号、查课表、查空教室、查一卡通消费、查水控与查新闻的全栈能力
"""

from typing import Dict, Any, List, Optional
from ..core.network import check_campus_network
from ..core.auth import get_credentials, get_cas_credentials, get_water_token, get_water_account
from ..core.jwzx import JwzxEngine
from ..services.water_svc import WaterService
from ..services.news_svc import NewsService
from ..services.room_svc import RoomService
from ..services.schedule_svc import ScheduleService
from ..services.score_svc import ScoreService
from ..services.exam_svc import ExamService
from ..services.plan_svc import PlanService

def _get_authenticated_jwzx() -> Optional[JwzxEngine]:
    u, p = get_credentials()
    if not u or not p:
        return None
    engine = JwzxEngine()
    if engine.login(u, p):
        return engine
    return None

def hermes_get_bath_status() -> Dict[str, Any]:
    """[Hermes Tool] 查询哈理工各浴室与热水的实时空闲率大盘 (支持 5 分钟 Token 自动自愈)"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    _, token = get_water_token()
    u, _ = get_credentials()
    cas_u, _ = get_cas_credentials()
    account = get_water_account() or cas_u or u or "16264"
    if not token and not get_water_account():
        return {"error": "未在网上办事大厅认证，请先运行 hrbust auth 扫码或登录"}

    svc = WaterService()
    try:
        items = svc.get_dashboard(account, token)
        return {"success": True, "items": items}
    except Exception as e:
        return {"error": str(e)}

def hermes_book_bath(class_no: int = 6) -> Dict[str, Any]:
    """[Hermes Tool] 申请浴室出水预约码 (class_no: 6=南区男浴, 7=南区女浴, 8=西区男浴, 9=西区女浴, 10=公寓热水)"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    _, token = get_water_token()
    u, _ = get_credentials()
    cas_u, _ = get_cas_credentials()
    account = get_water_account() or cas_u or u or "16264"
    svc = WaterService()
    try:
        return svc.book_bath(class_no, account, token)
    except Exception as e:
        return {"error": str(e)}

def hermes_cancel_bath(class_no: int = 6) -> Dict[str, Any]:
    """[Hermes Tool] 取消当前正在生效中的水房预约占用，释放机位"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    _, token = get_water_token()
    u, _ = get_credentials()
    cas_u, _ = get_cas_credentials()
    account = get_water_account() or cas_u or u or "16264"
    svc = WaterService()
    try:
        return svc.cancel_bath(class_no, account, token)
    except Exception as e:
        return {"error": str(e)}

def hermes_get_scores(term: Optional[str] = None) -> Dict[str, Any]:
    """[Hermes Tool] 查询本科全科成绩、学分与加权平均 GPA"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    engine = _get_authenticated_jwzx()
    if not engine:
        return {"error": "教务在线未登录，请先运行 hrbust login 绑定学号密码"}
    svc = ScoreService(engine)
    return svc.get_scores(term=term)

def hermes_get_exams(term: Optional[str] = None) -> Dict[str, Any]:
    """[Hermes Tool] 查询期末/期中考试科目、考试时间、考场教学楼与座位号"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    engine = _get_authenticated_jwzx()
    if not engine:
        return {"error": "教务在线未登录，请先运行 hrbust login 绑定学号密码"}
    svc = ExamService(engine)
    return svc.get_exams(term=term)

def hermes_get_card_records(start: str = "", end: str = "") -> Dict[str, Any]:
    """[Hermes Tool] 查询一卡通近期洗浴与热水消费流水账单与支出总计"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    _, token = get_water_token()
    u, _ = get_credentials()
    cas_u, _ = get_cas_credentials()
    account = get_water_account() or cas_u or u or "16264"
    if not token and not get_water_account():
        return {"error": "未在网上办事大厅认证，请先运行 hrbust auth 扫码或登录"}
    svc = WaterService()
    try:
        return svc.get_cost_records(account, token, start_date=start, end_date=end)
    except Exception as e:
        return {"error": str(e)}

def hermes_get_plan(category: Optional[str] = None) -> Dict[str, Any]:
    """[Hermes Tool] 查询本科培养方案大纲、已修/尚欠学分与毕业修读完成度"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    engine = _get_authenticated_jwzx()
    if not engine:
        return {"error": "教务在线未登录，请先运行 hrbust login 绑定学号密码"}
    svc = PlanService(engine)
    return svc.get_plan(category_filter=category)

def hermes_get_free_rooms(building: str = "南一", media_only: bool = False) -> Dict[str, Any]:
    """[Hermes Tool] 检索指定教学楼当前的全部教室资源与多媒体打标"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    engine = _get_authenticated_jwzx()
    if not engine:
        return {"error": "教务在线未登录，请先运行 hrbust login 绑定学号密码"}
    svc = RoomService(engine)
    b_info = svc.BUILDINGS.get(building) or svc.BUILDINGS["南一"]
    rooms = svc.get_building_rooms(b_info["aid"], b_info["id"])
    if media_only:
        rooms = [r for r in rooms if r["is_media"]]
    return {"building": b_info["name"], "total": len(rooms), "rooms": rooms}

def hermes_get_daily_news() -> Dict[str, Any]:
    """[Hermes Tool] 获取哈理工今日最新教务公告与校内新闻简报"""
    if not check_campus_network():
        return {"error": "未连接哈理工校园网"}
    svc = NewsService()
    return {"brief": svc.get_daily_brief()}
