"""
HRBUST Toolkit 课表与学分培养方案服务
支持教务在线实时同步、本地 SQLite (campus.db) 离线快照持久化与弱网/离线自动降级
"""

import re
from typing import List, Dict, Any, Optional
from ..core.jwzx import JwzxEngine
from ..core.db import save_schedule_snapshot, get_cached_schedule

class ScheduleService:
    def __init__(self, engine: Optional[JwzxEngine] = None):
        self.engine = engine

    def get_timetable(self, force_refresh: bool = False, term: str = "current") -> List[Dict[str, Any]]:
        """
        获取本学期课表并结构化解析为课程清单
        自动同步持久化到本地 SQLite (campus.db)；断网或教务网维护时平滑降级使用本地快照
        """
        # 1. 尝试从教务在线实时拉取
        if self.engine:
            try:
                dest_url = self.engine.access_module(2000)
                soup = self.engine.get_page(dest_url)

                courses = []
                tables = soup.find_all("table")
                for table in tables:
                    rows = table.find_all("tr")
                    for r in rows:
                        cells = r.find_all(["td", "th"])
                        for cell in cells:
                            text = cell.get_text(separator="\n", strip=True)
                            if not text or "星期" in text or "大节" in text:
                                continue
                            lines = [l.strip() for l in text.splitlines() if l.strip()]
                            if len(lines) >= 2:
                                course_name = lines[0]
                                teacher = lines[1] if len(lines) > 1 else ""
                                room = lines[-1] if len(lines) > 2 else ""
                                courses.append({
                                    "title": course_name,
                                    "name": course_name,
                                    "teacher": teacher,
                                    "classroom": room,
                                    "room": room,
                                    "raw": text,
                                    "day_of_week": "",
                                    "session": "",
                                    "weeks": "",
                                    "is_cached": False
                                })

                if courses:
                    # 存入本地 SQLite 快照库
                    save_schedule_snapshot(courses, term=term)
                    return courses

            except Exception:
                # 在线拉取失败，尝试降级读取本地快照
                pass

        # 2. 离线降级读取本地缓存快照
        cached = get_cached_schedule(term=term)
        if cached.get("has_cache"):
            courses = cached.get("courses", [])
            for c in courses:
                c["is_cached"] = True
                c["cached_at"] = cached.get("updated_at")
            return courses

        return []

    def get_current_timetable(self) -> List[Dict[str, Any]]:
        """获取当前学期大课表（别名兼顾 CLI 与自动化集成）"""
        return self.get_timetable()

    def get_curriculum_plan(self) -> List[Dict[str, Any]]:
        """
        获取四年培养方案与学分修读进度树
        """
        if not self.engine:
            return []
        dest_url = self.engine.access_module(2070)
        soup = self.engine.get_page(dest_url)

        plan = []
        table = soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if cols and len(cols) >= 4:
                    plan.append({
                        "course_name": cols[0],
                        "credits": cols[1],
                        "suggested_term": cols[2] if len(cols) > 2 else "",
                        "category": cols[3] if len(cols) > 3 else ""
                    })
        return plan
