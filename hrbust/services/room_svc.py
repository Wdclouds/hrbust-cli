"""
HRBUST Toolkit 自习室与空闲教室服务
包含按教学楼筛选、多媒体/机房教室高亮打标、单间教室全周占用矩阵
"""

from typing import List, Dict, Any
from ..core.jwzx import JwzxEngine

class RoomService:
    # 常用教学楼映射常量
    BUILDINGS = {
        "南一": {"name": "南区一号楼", "aid": "712", "id": "719"},
        "南二": {"name": "南区二号楼", "aid": "712", "id": "825"},
        "南三": {"name": "南区三号楼", "aid": "712", "id": "874"},
        "南六": {"name": "南区六号楼", "aid": "712", "id": "4330"},
        "西新主楼": {"name": "西区新主楼", "aid": "711", "id": "714"},
        "西一": {"name": "西区一号楼", "aid": "711", "id": "715"},
        "西二": {"name": "西区二号楼", "aid": "711", "id": "716"},
    }

    def __init__(self, engine: JwzxEngine):
        self.engine = engine

    def get_building_rooms(self, aid: str, building_id: str) -> List[Dict[str, Any]]:
        """
        拉取指定教学楼下的所有教室列表，并打标区分普通教室与多媒体/机房教室
        """
        url = f"{self.engine.BASE_URL}/academic/teacher/teachresource/roomschedulequery.jsdo"
        res = self.engine.session.post(url, data={"aid": aid, "buildingid": building_id}, timeout=8)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("gbk", errors="ignore"), "html.parser")

        rooms = []
        sel = soup.find("select", attrs={"name": "room"})
        if not sel:
            return rooms

        # 多媒体/特种特征关键词
        media_keywords = ["网络教学", "实验室", "多媒体", "辅助测试", "EDA", "电学", "微机", "机房", "计算机"]

        for opt in sel.find_all("option"):
            val = opt.get("value")
            name = opt.get_text(strip=True)
            if not val or val == "-1" or name == "请选择":
                continue

            is_media = any(k in name for k in media_keywords)
            rooms.append({
                "id": val,
                "name": name,
                "is_media": is_media,
                "type": "多媒体/实验" if is_media else "普通教室"
            })
        return rooms

    def get_room_schedule(self, aid: str, building_id: str, room_id: str) -> Dict[str, Any]:
        """
        获取指定教室 1~26 周的全周占用矩阵
        """
        url = f"{self.engine.BASE_URL}/academic/teacher/teachresource/roomschedule.jsdo"
        data = {
            "aid": aid,
            "buildingid": building_id,
            "room": room_id
        }
        res = self.engine.session.post(url, data=data, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content.decode("gbk", errors="ignore"), "html.parser")

        matrix = []
        table = soup.find("table", class_="form") or soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if cols:
                    matrix.append(cols)

        return {
            "room_id": room_id,
            "matrix": matrix
        }
