"""
HRBUST Toolkit 水控业务服务
处理全校浴室状态拉取、排序与交互式预约
"""

from typing import List, Dict, Any
from ..core.water import WaterEngine

class WaterService:
    def __init__(self, engine: WaterEngine = None):
        self.engine = engine or WaterEngine()

    def get_dashboard(self, raw_info: str, token: str) -> List[Dict[str, Any]]:
        """获取并格式化全校浴室/热水实时大盘"""
        items = self.engine.get_bath_status(raw_info, token)
        # 按指定顺序展示：南区男浴(6) -> 南区女浴(7) -> 西区男浴(8) -> 西区女浴(9) -> 公寓热水(10)
        order = {6: 1, 7: 2, 8: 3, 9: 4, 10: 5}
        return sorted(items, key=lambda x: order.get(x["class_no"], 99))

    def book_bath(self, class_no: int, account: str, userid: str, token: str) -> Dict[str, Any]:
        """
        根据场所编号与用户信息申请预约码
        """
        import json
        payload = {"ano": account, "classno": class_no}
        raw_info = self.engine.aes_encrypt(json.dumps(payload), userid)
        return self.engine.request_book_code(raw_info, token)

    def auto_auth_and_sync(self, username: str, password: str) -> Dict[str, Any]:
        """
        通过 CAS 统一身份认证全自动换取水控 Token 并自动加密落盘
        """
        success, msg, token, account = self.engine.fetch_token_by_cas(username, password)
        if success and token:
            from ..core.auth import set_water_token
            act = account or username
            raw_info = self.engine.aes_encrypt(act, act)
            set_water_token(raw_info, token)
            return {
                "success": True,
                "msg": msg,
                "token": token,
                "account": act,
            }
        return {
            "success": False,
            "msg": msg,
            "token": None,
            "account": None,
        }
