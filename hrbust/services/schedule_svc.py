"""
HRBUST Toolkit 课表与学分培养方案服务
"""

import re
from typing import List, Dict, Any
from ..core.jwzx import JwzxEngine

class ScheduleService:
    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    def get_timetable(self) -> List[Dict[str, Any]]:
        """
        获取本学期课表并结构化解析为课程清单
        """
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
                        courses.append({
                            "title": lines[0],
                            "teacher": lines[1] if len(lines) > 1 else "",
                            "classroom": lines[-1] if len(lines) > 2 else "",
                            "raw": text
                        })
        return courses

    def get_curriculum_plan(self) -> List[Dict[str, Any]]:
        """
        获取四年培养方案与学分修读进度树
        """
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
