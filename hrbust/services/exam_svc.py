"""
HRBUST Toolkit 期末/期中考试日程与考场座位号查询服务 (moduleId=2030)
解析考试科目、考试性质、时间地点、考场教室、座位号与倒计时计算
"""

import re
import datetime
from typing import List, Dict, Any, Optional
from ..core.jwzx import JwzxEngine

class ExamService:
    MODULE_ID = 2030  # 学生考试安排模块

    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    @staticmethod
    def _parse_countdown(time_str: str) -> Dict[str, Any]:
        """
        根据考试时间字符串计算倒计时
        例如 '2026-11-20 08:30-10:30' 或 '2026-06-15'
        """
        if not time_str:
            return {"status": "待排考", "days_left": None, "desc": "时间待定"}

        m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", time_str)
        if not m:
            return {"status": "未指定", "days_left": None, "desc": time_str}

        try:
            exam_date = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            today = datetime.date.today()
            diff = (exam_date - today).days

            if diff < 0:
                return {"status": "已结束", "days_left": diff, "desc": "已考完"}
            elif diff == 0:
                return {"status": "今天考试", "days_left": 0, "desc": "🔥 今日考试"}
            elif diff == 1:
                return {"status": "即将考试", "days_left": 1, "desc": "⚡ 明天考试"}
            elif diff <= 7:
                return {"status": "紧迫", "days_left": diff, "desc": f"还有 {diff} 天"}
            else:
                return {"status": "备考中", "days_left": diff, "desc": f"还有 {diff} 天"}
        except Exception:
            return {"status": "解析异常", "days_left": None, "desc": time_str}

    def get_exams(self, term: Optional[str] = None) -> Dict[str, Any]:
        """
        拉取学生本学期或历史所有科目的考试安排
        :param term: 可选学期过滤，如 '2024-2025-1'
        """
        dest_url = self.engine.access_module(self.MODULE_ID)
        soup = self.engine.get_page(dest_url)
        page_text = soup.get_text()

        # 1. 识别未开放排考或暂无考试提示
        if "暂无考试" in page_text or "未安排" in page_text or "没有安排考试" in page_text:
            return {
                "has_exams": False,
                "msg": "教务处当前学期暂未发布正式考试安排日程",
                "exams": []
            }

        # 2. 解析考试数据表格
        exams: List[Dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cols) < 5 or "课程名称" in cols or "序号" in cols or "考试时间" in cols:
                    continue

                # 典型教务表格列可能为:
                # [学期, 课程代码, 课程名称, 考试性质(正常/补考), 考试时间, 考场地点, 考场教室, 座位号, 准考证号, 备注]
                term_val = cols[0]
                if not re.search(r"\d{4}", term_val):
                    continue

                course_name = cols[2] if len(cols) > 2 else ""
                exam_type = cols[3] if len(cols) > 3 else "正常考试"
                exam_time = cols[4] if len(cols) > 4 else ""
                room_loc = cols[5] if len(cols) > 5 else ""
                seat_no = cols[6] if len(cols) > 6 else ""

                # 部分表格若考场和教室分两列，则合并
                if len(cols) >= 8 and re.search(r"^\d+$", cols[7]):
                    # cols[5]是楼栋, cols[6]是教室, cols[7]是座位号
                    room_loc = f"{cols[5]} {cols[6]}".strip()
                    seat_no = cols[7]
                elif len(cols) >= 7 and re.search(r"^\d+$", cols[6]):
                    seat_no = cols[6]

                countdown = self._parse_countdown(exam_time)

                exams.append({
                    "term": term_val,
                    "course_name": course_name,
                    "exam_type": exam_type,
                    "exam_time": exam_time,
                    "location": room_loc or "考场未公布",
                    "seat_no": seat_no or "待排定",
                    "status": countdown["status"],
                    "days_left": countdown["days_left"],
                    "countdown_desc": countdown["desc"]
                })

        # 3. 按学期过滤
        if term:
            exams = [e for e in exams if term in e.get("term", "")]

        # 4. 按倒计时优先排序：未结束的在最前（按剩余天数升序），已结束的在后
        def _sort_key(item: Dict[str, Any]):
            dl = item.get("days_left")
            if dl is None:
                return (2, 9999)
            elif dl >= 0:
                return (0, dl)
            else:
                return (1, -dl)

        exams = sorted(exams, key=_sort_key)

        return {
            "has_exams": len(exams) > 0,
            "msg": f"共检索到 {len(exams)} 门课程考试安排",
            "exams": exams
        }
