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

    def get_cost_records(
        self, account: str, userid: str, token: str, start_date: str = "", end_date: str = ""
    ) -> Dict[str, Any]:
        """
        查询一卡通/水控消费流水账单并计算收支统计汇总
        """
        import json
        payload = {
            "startdate": start_date or "",
            "enddate": end_date or "",
            "ano": account
        }
        raw_info = self.engine.aes_encrypt(json.dumps(payload), userid)
        raw_list = self.engine.get_acc_cost_info(raw_info, token)

        records = []
        total_cost = 0.0
        for item in raw_list:
            money_val = 0.0
            try:
                money_val = float(str(item.get("DealMoney", 0.0)).replace("-", "").strip())
            except Exception:
                pass
            total_cost += money_val

            records.append({
                "place": item.get("ClassName", "校园一卡通扣费").strip(),
                "time": item.get("DealTime", ""),
                "amount": money_val,
                "raw_money": str(item.get("DealMoney", ""))
            })

        return {
            "records": records,
            "summary": {
                "total_count": len(records),
                "total_cost": round(total_cost, 2),
            }
        }

    def login_by_password(self, username: str, password: str) -> Dict[str, Any]:
        """
        网上办事大厅 / 统一身份认证 (CAS) 账号密码登录
        通过哈理工统一身份认证中心验明身份并自动换取一卡通/水控 Token
        """
        success, msg, token, account = self.engine.fetch_token_by_cas(username, password)
        if success and token:
            from ..core.auth import set_water_token, set_cas_credentials
            act = account or username
            set_cas_credentials(username, password)
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

    # 兼容历史别名
    auto_auth_and_sync = login_by_password

    def start_qr_login(self) -> Dict[str, Any]:
        """
        发起 CAS 网上办事大厅移动端扫码登录会话
        返回 uuid 与 Unicode 终端字符二维码
        """
        return self.engine.fetch_cas_qr_session()

    def check_qr_status(self, uuid: str) -> str:
        """
        查询当前二维码扫描状态 ('0':等待, '2':已扫待确认, '1':成功, '3':失效)
        """
        return self.engine.check_cas_qr_status(uuid)

    def finish_qr_login(self, uuid: str) -> Dict[str, Any]:
        """
        扫码确认完成后执行换票并持久化加密存储 Token
        """
        success, msg, token, account = self.engine.complete_cas_qr_login(uuid)
        if success and token:
            from ..core.auth import set_water_token
            act = account or ""
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
