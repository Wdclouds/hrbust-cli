"""
HRBUST Toolkit 一卡通水控与洗浴系统底层引擎
封装 AES-128-ECB 加解密算法、浴场状态查询、预约取码与取消
"""

import json
import base64
from typing import Dict, Any, List, Tuple, Optional
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

        ret_no = data.get("RetNo", -1)
        ret_dsp = data.get("RetDsp", "未知状态")
        book_code = data.get("BookCode", "")

        if ret_no != 0:
            return {
                "success": False,
                "ret_no": ret_no,
                "RetNo": ret_no,
                "msg": ret_dsp or "预约申请未通过",
                "RetDsp": ret_dsp or "预约申请未通过",
                "book_code": book_code,
                "BookCode": book_code,
            }

        return {
            "success": True,
            "ret_no": 0,
            "RetNo": 0,
            "book_code": book_code,
            "BookCode": book_code,
            "msg": ret_dsp or "预约成功",
            "RetDsp": ret_dsp or "预约成功",
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

    def get_acc_cost_info(self, raw_info: str, token: str) -> List[Dict[str, Any]]:
        """
        查询一卡通/水控近期消费流水与扣费账单
        :param raw_info: 加密后的查询参数 (包含 ano, startdate, enddate)
        """
        url = f"{self.BASE_URL}/GetAccCostInfo"
        params = {"info": raw_info, "token": token}
        res = self.session.get(url, params=params, timeout=8)
        data = res.json()
        if data.get("RetNo") != 0:
            raise RuntimeError(f"获取一卡通消费账单失败: {data.get('RetDsp', '未知错误')}")
        return data.get("list", [])

    # ==================== 方案 1: CAS 统一认证全自动换票 ====================
    CAS_URL = "https://auth.hrbust.edu.cn/authserver/login"
    SERVICE_URL = "https://yktks.hrbust.edu.cn/"
    SSO_CHECK_URL = "https://yktks.hrbust.edu.cn/accountapi/berserker-base/user/Sso/SsoCheck"
    PKEY_B64 = "3n4DdO47LWH2Co/WfpbdyA=="
    SIGN_PASSWORD = "kv7XjPzrDNJY0pdZ#"

    @staticmethod
    def encrypt_cas_password(password: str, salt: str) -> str:
        """金智教育 CAS 标准动态加盐 AES-128-CBC 密码加密"""
        import random
        aes_chars = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
        plain = "".join(random.choice(aes_chars) for _ in range(64)) + password
        iv_str = "".join(random.choice(aes_chars) for _ in range(16))
        key_bytes = salt.strip().encode("utf-8")[:16].ljust(16, b"\0")
        iv_bytes = iv_str.encode("utf-8")[:16].ljust(16, b"\0")
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv_bytes)
        enc = cipher.encrypt(pad(plain.encode("utf-8"), AES.block_size))
        return base64.b64encode(enc).decode("utf-8")

    def fetch_token_by_cas(self, username: str, password: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        通过哈理工统一身份认证 (CAS) 全自动单点登录并换取水控 Token
        :return: (is_success, message, token, account)
        """
        import datetime
        import urllib.parse
        from bs4 import BeautifulSoup

        # 1. 访问 CAS 登录页提取 execution 与动态 salt
        login_url = f"{self.CAS_URL}?service={urllib.parse.quote(self.SERVICE_URL)}"
        try:
            r = self.session.get(login_url, timeout=8)
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            return False, f"连接统一身份认证中心异常: {e}", None, None

        exec_tag = soup.find("input", attrs={"name": "execution"})
        execution = exec_tag.get("value", "e1s1") if exec_tag else "e1s1"

        salt = ""
        for inp in soup.find_all("input"):
            if inp.get("id") == "pwdEncryptSalt" and inp.get("value"):
                salt = str(inp.get("value") or "")
                break

        if not salt:
            return False, "未能从 CAS 页面提取到动态加密盐值", None, None

        enc_pwd = self.encrypt_cas_password(password, salt)

        # 2. 提交 CAS 登录表单
        data = {
            "username": username,
            "password": enc_pwd,
            "execution": execution,
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "rmShown": "1"
        }

        try:
            r_post = self.session.post(login_url, data=data, allow_redirects=False, timeout=8)
        except Exception as e:
            return False, f"提交 CAS 登录认证异常: {e}", None, None

        loc = r_post.headers.get("Location", "")
        if "ticket=" not in loc:
            return False, "CAS 统一认证未通过，请检查学号或统一身份认证密码", None, None

        # 提取 ticket
        parsed = urllib.parse.urlparse(loc)
        qs = urllib.parse.parse_qs(parsed.query)
        ticket = qs.get("ticket", [""])[0]

        # 3. SsoCheck 换取真实一卡通账号 ano
        try:
            r_sso = self.session.post(self.SSO_CHECK_URL, data={"ticket": ticket}, timeout=8).json()
        except Exception as e:
            return False, f"请求一卡通 SSO 验票接口异常: {e}", None, None

        if r_sso.get("Ret") not in ("0", 0):
            return False, f"一卡通 SSO 验票失败: {r_sso.get('Msg', '未知错误')}", None, None

        user_info = r_sso.get("User", {})
        account = str(user_info.get("ACCOUNT", username))

        # 4. 换取专属水控 Token
        time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "userid": account,
            "userpassword": self.SIGN_PASSWORD,
            "time": time_str
        }
        enc_info = self.aes_encrypt(json.dumps(payload, separators=(",", ":")), self.PKEY_B64)
        try:
            r_tok = self.session.get(f"{self.BASE_URL}/GetToken", params={"info": enc_info}, timeout=8).json()
        except Exception as e:
            return False, f"请求水控 GetToken 接口异常: {e}", None, account

        if r_tok.get("RetNo") != 0:
            return False, f"生成水控 Token 失败: {r_tok.get('RetDsp', '未知错误')}", None, account

        token = r_tok.get("Token")
        return True, "全自动 CAS 换票成功", token, account

    # ==================== 方案 2: 办事大厅 CAS 移动端扫码登录 ====================
    QR_TOKEN_URL = "https://auth.hrbust.edu.cn/authserver/qrCode/getToken"
    QR_CODE_URL = "https://auth.hrbust.edu.cn/authserver/qrCode/getCode"
    QR_STATUS_URL = "https://auth.hrbust.edu.cn/authserver/qrCode/getStatus.htl"

    @staticmethod
    def qr_png_to_unicode(png_bytes: bytes) -> str:
        """
        将 400x400 的 CAS 二维码 PNG 图片无损降采样为终端 Unicode 半高字符块
        使用模块尺寸精准对齐，生成手机摄像头可秒扫的纯文本二维码
        """
        import io
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(png_bytes)).convert("1")
        inv = ImageOps.invert(img.convert("L"))
        bbox = inv.getbbox()
        if not bbox:
            return ""

        x0, y0 = bbox[0], bbox[1]
        # 探测左上角 Finder pattern 宽度 (7 个 module)
        finder_px = 0
        for x in range(x0, bbox[2]):
            if img.getpixel((x, y0 + 2)) == 0:
                finder_px += 1
            else:
                break
        module_size = max(1.0, finder_px / 7.0)
        n_modules = round((bbox[2] - x0) / module_size)

        # 加 2 个 module 的白边 (quiet zone) 保证识别率
        quiet = 2
        total_dim = n_modules + 2 * quiet
        matrix = [[0] * total_dim for _ in range(quiet)]

        for r in range(n_modules):
            cy = int(y0 + (r + 0.5) * module_size)
            row = [0] * quiet
            for c in range(n_modules):
                cx = int(x0 + (c + 0.5) * module_size)
                is_dark = 1 if img.getpixel((cx, cy)) == 0 else 0
                row.append(is_dark)
            row.extend([0] * quiet)
            matrix.append(row)

        for _ in range(quiet):
            matrix.append([0] * total_dim)

        # 每 2 行纵向像素合并为 1 个 Unicode 字符 (▀ / ▄ / █ / 空格)
        lines = []
        for y in range(0, len(matrix), 2):
            line = ""
            for x in range(len(matrix[0])):
                t = matrix[y][x]
                b = matrix[y + 1][x] if (y + 1) < len(matrix) else 0
                if t and b:
                    line += "█"
                elif t and not b:
                    line += "▀"
                elif not t and b:
                    line += "▄"
                else:
                    line += " "
            lines.append(line)
        return "\n".join(lines)

    def fetch_cas_qr_session(self) -> Dict[str, Any]:
        """
        向 CAS 申请二维码会话并获取渲染后的字符二维码
        :return: {"uuid": uuid, "qr_ascii": qr_ascii, "raw_img": bytes}
        """
        import time
        ts = int(time.time() * 1000)
        res = self.session.get(f"{self.QR_TOKEN_URL}?ts={ts}", timeout=8)
        uuid = res.text.strip()
        if not uuid or not uuid.startswith("QR-"):
            raise RuntimeError(f"获取 CAS 二维码 Token 失败: {uuid}")

        img_res = self.session.get(f"{self.QR_CODE_URL}?uuid={uuid}", timeout=8)
        qr_ascii = self.qr_png_to_unicode(img_res.content)

        return {
            "uuid": uuid,
            "qr_ascii": qr_ascii,
            "raw_img": img_res.content
        }

    def check_cas_qr_status(self, uuid: str) -> str:
        """
        轮询 CAS 二维码扫描状态
        :return:
          '0': 等待扫码
          '2': 手机已扫码，等待确认
          '1': 手机已确认登录授权成功！
          '3': 二维码已超时失效
        """
        import time
        ts = int(time.time() * 1000)
        res = self.session.get(f"{self.QR_STATUS_URL}?ts={ts}&uuid={uuid}", timeout=8)
        return res.text.strip()

    def complete_cas_qr_login(self, uuid: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        当二维码状态为 '1' 时，提交扫码登录表单并换取水控 Token
        :return: (is_success, msg, token, account)
        """
        import json
        import datetime
        import urllib.parse

        # 1. 提交 qrLoginForm 表单
        login_url = f"{self.CAS_URL}?display=qrLogin&service={urllib.parse.quote(self.SERVICE_URL)}"
        post_data = {
            "lt": "",
            "uuid": uuid,
            "cllt": "qrLogin",
            "dllt": "generalLogin",
            "execution": "e1s1",
            "_eventId": "submit",
            "rmShown": "1"
        }

        try:
            r_post = self.session.post(login_url, data=post_data, allow_redirects=False, timeout=8)
        except Exception as e:
            return False, f"提交 CAS 扫码表单异常: {e}", None, None

        loc = r_post.headers.get("Location", "")
        if "ticket=" not in loc:
            return False, "CAS 扫码未返回有效票据，登录未通过", None, None

        # 提取 ticket
        parsed = urllib.parse.urlparse(loc)
        qs = urllib.parse.parse_qs(parsed.query)
        ticket = qs.get("ticket", [""])[0]

        # 2. SsoCheck 换取真实一卡通卡号
        try:
            r_sso = self.session.post(self.SSO_CHECK_URL, data={"ticket": ticket}, timeout=8).json()
        except Exception as e:
            return False, f"请求一卡通 SSO 验票接口异常: {e}", None, None

        if r_sso.get("Ret") not in ("0", 0):
            return False, f"一卡通 SSO 验票失败: {r_sso.get('Msg', '未知错误')}", None, None

        user_info = r_sso.get("User", {})
        account = str(user_info.get("ACCOUNT", ""))

        # 3. 换取水控业务专属 Token
        time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "userid": account,
            "userpassword": self.SIGN_PASSWORD,
            "time": time_str
        }
        enc_info = self.aes_encrypt(json.dumps(payload, separators=(",", ":")), self.PKEY_B64)
        try:
            r_tok = self.session.get(f"{self.BASE_URL}/GetToken", params={"info": enc_info}, timeout=8).json()
        except Exception as e:
            return False, f"请求水控 GetToken 接口异常: {e}", None, account

        if r_tok.get("RetNo") != 0:
            return False, f"生成水控 Token 失败: {r_tok.get('RetDsp', '未知错误')}", None, account

        token = r_tok.get("Token")
        return True, "扫码单点登录成功", token, account
