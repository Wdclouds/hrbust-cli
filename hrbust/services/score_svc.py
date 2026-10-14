"""
HRBUST Toolkit 个人全科学分与成绩查询服务 (moduleId=2020)
包含各学期明细解析、加权平均分与 GPA 绩点自动计算、未评教拦截友好防御
"""

import re
from typing import List, Dict, Any, Optional
from ..core.jwzx import JwzxEngine

class ScoreService:
    MODULE_ID = 2020  # 个人成绩查询模块

    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    @staticmethod
    def _parse_score_value(score_str: str) -> float:
        """成绩分值提取与等级分转换"""
        score_str = score_str.strip()
        try:
            return float(score_str)
        except ValueError:
            grade_map = {
                "优秀": 95.0,
                "优": 95.0,
                "良好": 85.0,
                "良": 85.0,
                "中等": 75.0,
                "中": 75.0,
                "及格": 65.0,
                "合格": 65.0,
                "不及格": 50.0,
                "不合格": 50.0,
            }
            return grade_map.get(score_str, 0.0)

    @staticmethod
    def _parse_gpa_value(gpa_str: str, score_val: float) -> float:
        """绩点提取与标准折算"""
        try:
            val = float(gpa_str.strip())
            if val > 0:
                return val
        except Exception:
            pass
        # 标准 4.0 / 5.0 换算保底
        if score_val >= 90:
            return 4.0 + (score_val - 90) * 0.1
        elif score_val >= 80:
            return 3.0 + (score_val - 80) * 0.1
        elif score_val >= 70:
            return 2.0 + (score_val - 70) * 0.1
        elif score_val >= 60:
            return 1.0 + (score_val - 60) * 0.1
        return 0.0

    def get_scores(self, term: Optional[str] = None) -> Dict[str, Any]:
        """
        拉取本科至今所有学期的各科成绩与汇总
        :param term: 可选学期过滤，如 '2024-2025-1'
        """
        dest_url = self.engine.access_module(self.MODULE_ID)
        soup = self.engine.get_page(dest_url)
        page_text = soup.get_text()

        # 1. 识别未评教等拦截
        is_evaluation = any(k in page_text for k in ("评教", "教学评价", "评估", "教学质量评价"))
        is_blocked = any(k in page_text for k in ("未完成", "不可查看", "尚未", "不能", "禁止", "请先"))
        if is_evaluation and is_blocked:
            return {
                "blocked": True,
                "reason": "教务处提示未完成期末评教，成绩查看被系统锁定，请先登录教务在线完成教学评价",
                "scores": [],
                "summary": {
                    "total_courses": 0,
                    "total_credits": 0.0,
                    "weighted_avg_score": 0.0,
                    "gpa": 0.0,
                }
            }

        # 2. 解析成绩数据表格
        scores: List[Dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cols) < 5 or "课程名称" in cols or "序号" in cols:
                    continue

                # 提取常见列模式
                # 典型教务表格列: [学期, 课程代码, 课程名称, 课程性质, 学分, 平时, 期末, 总评/综合, 绩点]
                term_val = cols[0]
                if not re.search(r"\d{4}", term_val):
                    continue

                course_name = cols[2] if len(cols) > 2 else ""
                category = cols[3] if len(cols) > 3 else "必修"
                
                try:
                    credit = float(cols[4])
                except (ValueError, IndexError):
                    credit = 0.0

                score_raw = cols[7] if len(cols) > 7 else cols[-2] if len(cols) >= 6 else ""
                gpa_raw = cols[8] if len(cols) > 8 else cols[-1] if len(cols) >= 7 else ""

                score_num = self._parse_score_value(score_raw)
                gpa_num = self._parse_gpa_value(gpa_raw, score_num)

                scores.append({
                    "term": term_val,
                    "course_name": course_name,
                    "category": category,
                    "credit": credit,
                    "regular_score": cols[5] if len(cols) > 5 else "",
                    "exam_score": cols[6] if len(cols) > 6 else "",
                    "final_score": score_raw,
                    "score_val": score_num,
                    "gpa": gpa_num,
                    "passed": score_num >= 60.0 or score_raw in ("优秀", "良好", "中等", "及格", "合格"),
                })

        # 3. 按学期过滤
        if term:
            scores = [s for s in scores if term in s.get("term", "")]

        # 4. 加权汇总统计
        total_credits = sum(s["credit"] for s in scores if s["credit"] > 0)
        weighted_score_sum = sum(s["score_val"] * s["credit"] for s in scores if s["credit"] > 0)
        weighted_gpa_sum = sum(s["gpa"] * s["credit"] for s in scores if s["credit"] > 0)

        weighted_avg = round(weighted_score_sum / total_credits, 2) if total_credits > 0 else 0.0
        final_gpa = round(weighted_gpa_sum / total_credits, 2) if total_credits > 0 else 0.0

        return {
            "blocked": False,
            "reason": "",
            "scores": scores,
            "summary": {
                "total_courses": len(scores),
                "total_credits": round(total_credits, 1),
                "passed_courses": len([s for s in scores if s["passed"]]),
                "weighted_avg_score": weighted_avg,
                "gpa": final_gpa,
            }
        }
