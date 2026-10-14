"""
HRBUST Toolkit 水控业务服务
处理全校浴室状态拉取、排序、交互式预约出码与自动释放机位
支持 5 分钟 Token 静默自愈刷新，永不掉线
"""

import json
import time
import base64
from typing import List, Dict, Any, Optional
from ..core.water import WaterEngine

class WaterService:
    def __init__(self, engine: WaterEngine = None):
        self.engine = engine or WaterEngine()

    @staticmethod
    def is_token_valid(token: Optional[str]) -> bool:
        """检查 JWT 令牌格式及是否在 5 分钟有效期内 (保留 15 秒提前量)"""
        if not token or not isinstance(token, str) or token.count(".") != 2:
            return False
        try:
            parts = token.split(".")
            payload_bytes = base64.urlsafe_b64decode(parts[1] + "==")
            payload = json.loads(payload_bytes.decode("utf-8"))
            exp = float(payload.get("exp", 0))
            return exp > (time.time() + 15)
        except Exception:
            return False

    def _ensure_valid_token(self, account: str, token: Optional[str] = None) -> str:
        """如果 Token 缺失或已过期，根据卡号自动静默生成最新有效 Token 并持久化"""
        if self.is_token_valid(token):
            return token  # type: ignore

        from ..core.auth import set_water_token
        try:
            fresh_tok = self.engine.generate_token(account)
            payload = json.dumps({"ano": account}, separators=(",", ":"))
            raw_info = self.engine.aes_encrypt(payload, self.engine.PKEY_B64)
            set_water_token(raw_info, fresh_tok, account=account)
            return fresh_tok
        except Exception:
            return token or ""

    def get_dashboard(self, raw_info_or_account: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取并格式化全校浴室/热水实时大盘 (支持 Token 自动静默自愈)
        """
        account = raw_info_or_account
        if "{" in raw_info_or_account or len(raw_info_or_account) > 15 or raw_info_or_account.endswith("="):
            from ..core.auth import get_water_account
            account = get_water_account() or "16264"

        tok = self._ensure_valid_token(account, token)
        payload = json.dumps({"ano": account}, separators=(",", ":"))
        raw_info = self.engine.aes_encrypt(payload, self.engine.PKEY_B64)

        try:
            items = self.engine.get_bath_status(raw_info, tok)
        except Exception as e:
            if "用户授权验证失败" in str(e) or "Token" in str(e) or "token" in str(e):
                # 触发 5 分钟硬过期自愈：强制重新派发 Token 并静默重试
                tok = self.engine.generate_token(account)
                from ..core.auth import set_water_token
                set_water_token(raw_info, tok, account=account)
                items = self.engine.get_bath_status(raw_info, tok)
            else:
                raise

        # 按指定顺序展示：南区男浴(6) -> 南区女浴(7) -> 西区男浴(8) -> 西区女浴(9) -> 公寓热水(10)
        order = {6: 1, 7: 2, 8: 3, 9: 4, 10: 5}
        return sorted(items, key=lambda x: order.get(x["class_no"], 99))

    def book_bath(self, class_no: int, account: str, arg3: Optional[str] = None, arg4: Optional[str] = None) -> Dict[str, Any]:
        """
        根据场所编号与一卡通物理账号申请预约码 (支持自动自愈刷新)
        """
        token = arg4 if arg4 is not None else arg3
        tok = self._ensure_valid_token(account, token)

        payload = {"ano": account, "classno": class_no}
        raw_info = self.engine.aes_encrypt(json.dumps(payload, separators=(",", ":")), self.engine.PKEY_B64)

        try:
            return self.engine.request_book_code(raw_info, tok)
        except Exception as e:
            if "用户授权验证失败" in str(e):
                tok = self.engine.generate_token(account)
                from ..core.auth import set_water_token
                set_water_token(raw_info, tok, account=account)
                return self.engine.request_book_code(raw_info, tok)
            raise

    def cancel_bath(self, class_no: int, account: str, token: Optional[str] = None) -> Dict[str, Any]:
        """
        一键取消已占用的预约码，释放水房占用
        """
        tok = self._ensure_valid_token(account, token)
        payload = {"ano": account, "classno": class_no}
        raw_info = self.engine.aes_encrypt(json.dumps(payload, separators=(",", ":")), self.engine.PKEY_B64)

        try:
            return self.engine.cancel_book_code(raw_info, tok)
        except Exception as e:
            if "用户授权验证失败" in str(e):
                tok = self.engine.generate_token(account)
                from ..core.auth import set_water_token
                set_water_token(raw_info, tok, account=account)
                return self.engine.cancel_book_code(raw_info, tok)
            raise

    def get_cost_records(
        self, account: str, arg2: Optional[str] = None, arg3: Optional[str] = None, start_date: str = "", end_date: str = ""
    ) -> Dict[str, Any]:
        """
        查询一卡通/水控消费流水账单并计算收支统计汇总
        """
        token = arg3 if arg3 is not None and not (isinstance(arg3, str) and "-" in arg3) else arg2
        if arg3 is not None and isinstance(arg3, str) and "-" in arg3 and not start_date:
            token = arg2
            start_date = arg3

        tok = self._ensure_valid_token(account, token)
        payload = {
            "startdate": start_date or "",
            "enddate": end_date or "",
            "ano": account
        }
        raw_info = self.engine.aes_encrypt(json.dumps(payload, separators=(",", ":")), self.engine.PKEY_B64)

        try:
            raw_list = self.engine.get_acc_cost_info(raw_info, tok)
        except Exception as e:
            if "用户授权验证失败" in str(e):
                tok = self.engine.generate_token(account)
                from ..core.auth import set_water_token
                set_water_token(raw_info, tok, account=account)
                raw_list = self.engine.get_acc_cost_info(raw_info, tok)
            else:
                raise

        records = []
        total_cost = 0.0
        for item in raw_list:
            money_val = 0.0
            try:
                money_val = float(str(item.get("DealMoney", 0.0)).replace("-", "").replace("元", "").strip())
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
            from ..core.auth import set_water_token, set_cas_credentials, set_water_account
            act = account or username
            set_cas_credentials(username, password)
            set_water_account(act)
            payload = json.dumps({"ano": act}, separators=(",", ":"))
            raw_info = self.engine.aes_encrypt(payload, self.engine.PKEY_B64)
            set_water_token(raw_info, token, account=act)
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
            from ..core.auth import set_water_token, set_water_account
            act = account or ""
            if act:
                set_water_account(act)
            payload = json.dumps({"ano": act}, separators=(",", ":"))
            raw_info = self.engine.aes_encrypt(payload, self.engine.PKEY_B64)
            set_water_token(raw_info, token, account=act)
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
