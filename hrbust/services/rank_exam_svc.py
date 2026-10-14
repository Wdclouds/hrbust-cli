"""
HRBUST Toolkit 全国大学英语四六级 (CET4/6) 与等级考试成绩服务 (moduleId=2022)
解析全国大学英语四六级、全国计算机等级考试 (NCRE) 成绩、各分项小分与证书编号
"""

import re
from typing import List, Dict, Any, Optional
from ..core.jwzx import JwzxEngine

class RankExamService:
    MODULE_ID = 2022  # 等级考试成绩查询模块

    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    def get_rank_exams(self) -> Dict[str, Any]:
        """
        拉取本科至今所有等级考试（四六级、计算机二级等）成绩与证书
        """
        dest_url = self.engine.access_module(self.MODULE_ID)
        soup = self.engine.get_page(dest_url)
        page_text = soup.get_text()

        if "暂无" in page_text or "没有等级考试" in page_text or "无记录" in page_text:
            return {
                "has_records": False,
                "msg": "教务系统暂未检索到等级考试成绩记录",
                "summary": {},
                "exams": []
            }

        exams: List[Dict[str, Any]] = []
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
                if len(cols) < 4 or "考试名称" in cols or "序号" in cols or "总分" in cols:
                    continue

                # 典型等级考试表格格式可能为:
                # [学期/序号, 考试名称, 考试时间, 准考证号, 总分, 听力, 阅读, 写作/翻译, 证书编号, 备注]
                exam_name = cols[1] if len(cols) > 1 else ""
                if not exam_name or "计" in exam_name[:2] and "计" in exam_name:
                    if len(cols) > 2 and ("英语" in cols[2] or "计算机" in cols[2] or "CET" in cols[2]):
                        exam_name = cols[2]

                if not any(k in exam_name for k in ("英语", "CET", "计算机", "日语", "俄语", "等级", "四级", "六级")):
                    # 尝试在整行中寻找考试名称特征
                    found = False
                    for c_idx, c_text in enumerate(cols):
                        if any(k in c_text for k in ("英语", "CET", "计算机", "四级", "六级")):
                            exam_name = c_text
                            found = True
                            break
                    if not found:
                        continue

                term_or_date = cols[0]
                m_date = re.search(r"(\d{4}[-/.]\d{1,2}|\d{4}-\d{4}-\d)", " ".join(cols[:4]))
                date_str = m_date.group(0) if m_date else term_or_date

                # 提取总分（通常在数字列中寻找 >= 0 的分值）
                score_str = ""
                hearing_str = "-"
                reading_str = "-"
                writing_str = "-"
                cert_no = "-"

                for c_idx, c_val in enumerate(cols[2:], 2):
                    if re.match(r"^\d{2,3}(\.\d+)?$", c_val):
                        if not score_str:
                            score_str = c_val
                            # 后续可能跟随听力、阅读、写作小分
                            if len(cols) > c_idx + 1 and re.match(r"^\d{1,3}(\.\d+)?$", cols[c_idx + 1]):
                                hearing_str = cols[c_idx + 1]
                            if len(cols) > c_idx + 2 and re.match(r"^\d{1,3}(\.\d+)?$", cols[c_idx + 2]):
                                reading_str = cols[c_idx + 2]
                            if len(cols) > c_idx + 3 and re.match(r"^\d{1,3}(\.\d+)?$", cols[c_idx + 3]):
                                writing_str = cols[c_idx + 3]
                            break

                # 寻找证书编号或准考证号
                for c_val in cols:
                    if len(c_val) >= 12 and re.match(r"^\d{12,}$", c_val):
                        cert_no = c_val
                        break

                # 判断通过状态
                is_passed = False
                try:
                    s_num = float(score_str)
                    if "四级" in exam_name or "CET4" in exam_name or "六级" in exam_name or "CET6" in exam_name:
                        is_passed = s_num >= 425.0
                    else:
                        is_passed = s_num >= 60.0
                except Exception:
                    is_passed = any(k in "".join(cols) for k in ("通过", "合格", "优秀", "良好"))

                exams.append({
                    "exam_name": exam_name,
                    "date": date_str,
                    "score": score_str or "合格",
                    "hearing": hearing_str,
                    "reading": reading_str,
                    "writing": writing_str,
                    "cert_no": cert_no,
                    "passed": is_passed
                })

        # 统计四六级最高分
        cet4_max = 0.0
        cet6_max = 0.0
        for e in exams:
            name = e["exam_name"]
            try:
                sc = float(e["score"])
                if "四级" in name or "CET4" in name:
                    cet4_max = max(cet4_max, sc)
                elif "六级" in name or "CET6" in name:
                    cet6_max = max(cet6_max, sc)
            except Exception:
                pass

        return {
            "has_records": len(exams) > 0,
            "msg": f"共检索到 {len(exams)} 门等级考试记录",
            "summary": {
                "total_records": len(exams),
                "cet4_max": cet4_max if cet4_max > 0 else None,
                "cet6_max": cet6_max if cet6_max > 0 else None,
                "cet4_passed": cet4_max >= 425.0,
                "cet6_passed": cet6_max >= 425.0
            },
            "exams": exams
        }
