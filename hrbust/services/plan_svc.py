"""
HRBUST Toolkit 本科培养方案与个人教学计划服务 (moduleId=2070)
解析专业培养方案各模块学分要求、已修得学分、尚欠学分与毕业修读完成度
"""

import re
from typing import List, Dict, Any, Optional
from ..core.jwzx import JwzxEngine

class PlanService:
    MODULE_ID = 2070  # 个人教学计划与培养方案模块

    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    def get_plan(self, category_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        拉取本科专业个人教学计划，统计各模块学分完成度
        :param category_filter: 可选课程类别过滤（如 '必修', '选修', '通识'）
        """
        dest_url = self.engine.access_module(self.MODULE_ID)
        soup = self.engine.get_page(dest_url)
        page_text = soup.get_text()

        # 1. 识别未开放或无法查看提示
        if "暂无教学计划" in page_text or "未安排教学计划" in page_text:
            return {
                "has_plan": False,
                "msg": "教务系统暂未检索到当前年级专业的教学计划大纲",
                "summary": {},
                "courses": []
            }

        # 2. 解析计划表格
        courses: List[Dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cols) < 5 or "课程名称" in cols or "序号" in cols or "学分" in cols[2:4]:
                    continue

                # 典型教务计划表格:
                # [学期/序号, 课程代码, 课程名称, 课程性质/类别, 学分, 建议修读学期, 考核方式, 修读状态/完成情况]
                course_code = cols[1] if len(cols) > 1 else ""
                course_name = cols[2] if len(cols) > 2 else ""
                if not course_name or course_name in ("总计", "合计", "小计"):
                    continue

                category = cols[3] if len(cols) > 3 else "必修"
                
                credit_val = 0.0
                try:
                    credit_val = float(cols[4])
                except (ValueError, IndexError):
                    m_cr = re.search(r"(\d+(\.\d+)?)", "".join(cols[3:6]))
                    if m_cr:
                        credit_val = float(m_cr.group(1))

                suggest_term = cols[5] if len(cols) > 5 else ""
                exam_method = cols[6] if len(cols) > 6 else "考试"
                status_raw = cols[7] if len(cols) > 7 else cols[-1] if len(cols) >= 6 else "未修"

                # 判断是否已修读完成
                is_completed = any(k in status_raw for k in ("已修", "通过", "及格", "已选", "合格", "免修")) or (
                    re.search(r"^\d+(\.\d+)?$", status_raw) and float(status_raw) >= 60.0
                )

                courses.append({
                    "course_code": course_code,
                    "course_name": course_name,
                    "category": category,
                    "credit": credit_val,
                    "suggest_term": suggest_term,
                    "exam_method": exam_method,
                    "status_desc": "已修得" if is_completed else ("未修读" if "未" in status_raw else status_raw),
                    "completed": is_completed
                })

        # 3. 按课程性质过滤
        if category_filter:
            courses = [c for c in courses if category_filter in c["category"]]

        # 4. 学分与模块指标统计
        total_plan_credits = sum(c["credit"] for c in courses)
        completed_credits = sum(c["credit"] for c in courses if c["completed"])
        remaining_credits = max(0.0, total_plan_credits - completed_credits)
        completion_rate = round((completed_credits / total_plan_credits) * 100.0, 1) if total_plan_credits > 0 else 0.0

        # 分类汇总统计
        categories_breakdown: Dict[str, Dict[str, float]] = {}
        for c in courses:
            cat = c["category"]
            if cat not in categories_breakdown:
                categories_breakdown[cat] = {"total": 0.0, "completed": 0.0}
            categories_breakdown[cat]["total"] += c["credit"]
            if c["completed"]:
                categories_breakdown[cat]["completed"] += c["credit"]

        return {
            "has_plan": len(courses) > 0,
            "msg": f"共规划 {len(courses)} 门培养方案课程",
            "summary": {
                "total_courses": len(courses),
                "completed_courses": len([c for c in courses if c["completed"]]),
                "remaining_courses": len([c for c in courses if not c["completed"]]),
                "total_plan_credits": round(total_plan_credits, 1),
                "completed_credits": round(completed_credits, 1),
                "remaining_credits": round(remaining_credits, 1),
                "completion_rate": completion_rate,
                "categories": categories_breakdown
            },
            "courses": courses
        }
