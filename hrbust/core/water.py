"""
HRBUST Toolkit 一卡通水控与洗浴系统底层引擎
封装 AES-128-ECB 加解密算法、浴场状态查询、预约取码与取消
"""

import json
import base64
from typing import Dict, Any, List
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from .network import CampusSession

class WaterEngine:
    """一卡通水控平台底层客户端 (yktks.hrbust.edu.cn)"""
    BASE_URL = "https://yktks.hrbust.edu.cn/waterapi/api"

    # 全校浴场与热水点枚举常量
    CLASS_SOUTH_MALE = 6     # 南区男浴
    CLASS_SOUTH_FEMALE = 7   # 南区女浴
    CLASS_WEST_MALE = 8      # 西区男浴
    CLASS_WEST_FEMALE = 9    # 西区女浴
    CLASS_APARTMENT = 10     # 公寓热水

    LOCATION_NAMES = {
        6: "南区男浴",
        7: "南区女浴",
        8: "西区男浴",
        9: "西区女浴",
        10: "公寓热水"
    }

    def __init__(self):
        self.session = CampusSession()

    @staticmethod
    def aes_encrypt(data_str: str, key_str: str) -> str:
        """
        前端同款 AES-128-ECB 加密逻辑 (PKCS7 填充)
        如果 key_str 是 base64 串则解码，否则自动补充/截断至 16 字节
        """
        try:
            key_bytes = base64.b64decode(key_str)
            if len(key_bytes) not in (16, 24, 32):
                key_bytes = key_str.encode("utf-8")[:16].ljust(16, b"\0")
        except Exception:
            key_bytes = key_str.encode("utf-8")[:16].ljust(16, b"\0")

        cipher = AES.new(key_bytes, AES.MODE_ECB)
        padded = pad(data_str.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(encrypted).decode("utf-8")

    def get_bath_status(self, raw_info: str, token: str) -> List[Dict[str, Any]]:
        """
        获取全校各浴室与热水的实时机位与空闲率大盘
        """
        url = f"{self.BASE_URL}/AccUseHzWatch"
        params = {"info": raw_info, "token": token}
        res = self.session.get(url, params=params, timeout=6)
        data = res.json()

        if data.get("RetNo") != 0:
            raise RuntimeError(f"获取浴室状态失败: {data.get('RetDsp', '未知错误')}")

        result = []
        for item in data.get("List", []):
            pos_num = item.get("PosNum", 0)
            use_free_rate = item.get("UseFreeRate", 0) / 100.0
            book_rate = item.get("BookRate", 0) / 100.0
            result.append({
                "class_no": item.get("ClassNo"),
                "name": item.get("ClassName", "").strip(),
                "total_positions": pos_num,
                "warn_positions": item.get("WarnPosNum", 0),
                "free_rate": use_free_rate,
                "book_rate": book_rate,
                "book_code": item.get("BookCode", "")
            })
        return result

    def request_book_code(self, raw_info: str, token: str) -> Dict[str, Any]:
        """
        申请出水预约码 (有效期 60 分钟)
        """
        url = f"{self.BASE_URL}/BookCodeReq"
        params = {"info": raw_info, "token": token}
        res = self.session.get(url, params=params, timeout=6)
        data = res.json()

        if data.get("RetNo") != 0:
            return {"success": False, "msg": data.get("RetDsp", "预约申请未通过")}

        return {
            "success": True,
            "book_code": data.get("BookCode"),
            "msg": data.get("RetDsp", "预约成功")
        }

    def cancel_book_code(self, raw_info: str, token: str) -> Dict[str, Any]:
        """
        一键取消已占用的预约码，释放机位
        """
        url = f"{self.BASE_URL}/BookCodeReqCancel"
        params = {"info": raw_info, "token": token}
        res = self.session.get(url, params=params, timeout=6)
        data = res.json()
        return {
            "success": data.get("RetNo") == 0,
            "msg": data.get("RetDsp", "取消操作完成")
        }
