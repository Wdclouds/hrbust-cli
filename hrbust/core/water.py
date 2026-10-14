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

    def generate_token(self, account: str) -> str:
        """
        根据物理一卡通卡号与硬件私钥动态生成 5 分钟业务 Token
        零 Cookie、零密码依赖，毫秒级就绪
        """
        import json
        import datetime
        time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        tok_payload = {
            "userid": str(account),
            "userpassword": self.SIGN_PASSWORD,
            "time": time_str
        }
        enc_tok = self.aes_encrypt(json.dumps(tok_payload, separators=(",", ":")), self.PKEY_B64)
        res = self.session.get(f"{self.BASE_URL}/GetToken", params={"info": enc_tok}, timeout=8).json()
        if res.get("RetNo") == 0 and res.get("Token"):
            return res.get("Token")
        raise RuntimeError(f"生成水控Token失败: {res.get('RetDsp', '未知错误')}")

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
                "act_kind": item.get("Actkind", 0),
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
    ECARD_CAS_SERVICE = "https://ecard.hrbust.edu.cn/plat-pc/serviceclassification"
    ECARD_SSO_ENTRY = "https://ecard.hrbust.edu.cn/berserker-auth/cas/login/wisedu?targetUrl=https://ecard.hrbust.edu.cn/plat/?name=loginTransit"
    OAUTH_TOKEN_URL = "https://ecard.hrbust.edu.cn/berserker-auth/oauth/token"
    OAUTH_BASIC_AUTH = "Basic bW9iaWxlX3NlcnZpY2VfcGxhdGZvcm06bW9iaWxlX3NlcnZpY2VfcGxhdGZvcm1fc2VjcmV0"
    REDIRECT_URL_TEMPLATE = "https://ecard.hrbust.edu.cn/berserker-base/redirect?type=app&synjones-auth={access_token}&appId=113&synAccessSource=pc"
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

    def _exchange_ecard_ticket_to_water_token(self, ecard_ticket: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        核心换票流水线：
        一卡通 ST 票据 -> OAuth access_token -> Berserker 分发 -> SsoCheck 真实 ACCOUNT -> 生成水控 Token
        :return: (is_success, msg, token, account)
        """
        import re
        import json
        import datetime

        # 1. 换取校园卡平台 OAuth 访问令牌
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.OAUTH_BASIC_AUTH
        }
        token_data = {
            "username": ecard_ticket,
            "password": ecard_ticket,
            "grant_type": "password",
            "scope": "all",
            "loginFrom": "pc",
            "logintype": "sso"
        }
        try:
            r_tok = self.session.post(self.OAUTH_TOKEN_URL, headers=token_headers, data=token_data, timeout=8).json()
        except Exception as e:
            return False, f"请求校园卡平台 OAuth Token 异常: {e}", None, None

        access_token = r_tok.get("access_token")
        if not access_token:
            err = r_tok.get("message") or r_tok.get("error_description") or "未知原因"
            return False, f"一卡通平台票据换取失败: {err}", None, None

        # 2. 携带 synjones-auth 请求 redirect 跳转以获取控水系统票据
        redir_url = self.REDIRECT_URL_TEMPLATE.format(access_token=access_token)
        auth_headers = {
            "Authorization": f"Bearer {access_token}",
            "synjones-auth": f"Bearer {access_token}"
        }
        try:
            r_redir = self.session.get(redir_url, headers=auth_headers, allow_redirects=False, timeout=8)
        except Exception as e:
            return False, f"请求水控系统应用跳转异常: {e}", None, None

        jump_loc = r_redir.headers.get("Location", "")
        m_ticket = re.search(r"ticket=([^&]+)", jump_loc)
        if not m_ticket:
            return False, "未能从一卡通平台提取到水控服务票据", None, None
        yktks_ticket = m_ticket.group(1)

        # 3. 访问 SsoCheck 换取真实一卡通账号 ACCOUNT (ano)
        try:
            r_sso = self.session.post(self.SSO_CHECK_URL, data={"ticket": yktks_ticket}, timeout=8).json()
        except Exception as e:
            return False, f"水控单点验票异常: {e}", None, None

        if str(r_sso.get("Ret")) != "0":
            return False, f"水控单点验票失败: {r_sso.get('Msg', '未知错误')}", None, None

        user_info = r_sso.get("User") or {}
        account = str(user_info.get("ACCOUNT") or user_info.get("account") or "")
        if not account:
            return False, "未能获取到一卡通真实账号 (ACCOUNT)", None, None

        # 4. 调用 GetToken 派发实时可用的业务 Token
        time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        tok_payload = {
            "userid": account,
            "userpassword": self.SIGN_PASSWORD,
            "time": time_str
        }
        enc_tok = self.aes_encrypt(json.dumps(tok_payload, separators=(",", ":")), self.PKEY_B64)
        try:
            r_token = self.session.get(f"{self.BASE_URL}/GetToken", params={"info": enc_tok}, timeout=8).json()
        except Exception as e:
            return False, f"请求水控 GetToken 接口异常: {e}", None, account

        if r_token.get("RetNo") != 0:
            return False, f"生成水控 Token 失败: {r_token.get('RetDsp', '未知错误')}", None, account

        token = r_token.get("Token")
        return True, "认证并打通水控成功", token, account

    def fetch_token_by_cas(self, username: str, password: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        通过哈理工统一身份认证 (CAS) 账号密码登录并换取真实一卡通与水控 Token
        :return: (is_success, message, token, account)
        """
        import re
        import urllib.parse
        from bs4 import BeautifulSoup

        # 1. 访问官方 SSO 入口，经重定向到达 CAS 登录页
        try:
            r_cas_page = self.session.get(self.ECARD_SSO_ENTRY, allow_redirects=True, timeout=8)
            soup = BeautifulSoup(r_cas_page.text, "html.parser")
        except Exception as e:
            return False, f"连接统一身份认证中心异常: {e}", None, None

        salt_tag = soup.find(id="pwdEncryptSalt")
        if not salt_tag or not salt_tag.get("value"):
            return False, "未能从 CAS 统一认证页提取到动态加密盐值", None, None

        salt = str(salt_tag.get("value") or "")
        exec_tag = soup.find("input", {"name": "execution"})
        execution = exec_tag.get("value", "e1s1") if exec_tag and hasattr(exec_tag, "get") else "e1s1"

        enc_pwd = self.encrypt_cas_password(password, salt)
        post_data = {
            "username": username,
            "password": enc_pwd,
            "execution": execution,
            "_eventId": "submit",
            "cllt": "userNameLogin",
            "dllt": "generalLogin",
            "lt": "",
            "rmShown": "1"
        }

        # 2. 提交 CAS 登录表单
        try:
            r_cas_submit = self.session.post(r_cas_page.url, data=post_data, allow_redirects=False, timeout=8)
        except Exception as e:
            return False, f"提交统一身份认证表单异常: {e}", None, None

        cas_loc = r_cas_submit.headers.get("Location", "")
        if "ticket=" not in cas_loc and "callback" not in cas_loc:
            return False, "统一身份认证未通过，请检查学号或统一身份认证密码", None, None

        # 3. 访问 callback 页面换取 ecard ticket
        try:
            r_cb = self.session.get(cas_loc, allow_redirects=False, timeout=8)
            cb_loc = r_cb.headers.get("Location", "")
            r_target = self.session.get(cb_loc, allow_redirects=False, timeout=8)
            transit_url = r_target.headers.get("Location", "")
        except Exception as e:
            return False, f"统一认证回调换票异常: {e}", None, None

        m_ticket = re.search(r"ticket=([^&]+)", transit_url)
        if not m_ticket:
            return False, "未能从认证跳转中获取一卡通 ticket", None, None

        ecard_ticket = urllib.parse.unquote(m_ticket.group(1))
        return self._exchange_ecard_ticket_to_water_token(ecard_ticket)

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
        当二维码状态为 '1' (手机已确认) 时，提交扫码登录表单并通过一卡通全自动换取水控 Token
        :return: (is_success, msg, token, account)
        """
        import re
        import urllib.parse

        service_param = "https://ecard.hrbust.edu.cn/berserker-auth/cas/callback/wisedu?redirectUrl=https%3A%2F%2Fecard.hrbust.edu.cn%2Fplat%2F%3Fname%3DloginTransit"
        login_url = f"{self.CAS_URL}?display=qrLogin&service={urllib.parse.quote(service_param, safe='')}"
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

        cas_loc = r_post.headers.get("Location", "")
        if not cas_loc:
            return False, "CAS 扫码未返回有效重定向，登录未通过", None, None

        # 访问 callback 页面换取 ecard ticket
        try:
            r_cb = self.session.get(cas_loc, allow_redirects=False, timeout=8)
            cb_loc = r_cb.headers.get("Location", "")
            r_target = self.session.get(cb_loc, allow_redirects=False, timeout=8)
            transit_url = r_target.headers.get("Location", "")
        except Exception as e:
            return False, f"扫码认证回调换票异常: {e}", None, None

        m_ticket = re.search(r"ticket=([^&]+)", transit_url)
        if not m_ticket:
            return False, "未能从扫码跳转中获取一卡通 ticket", None, None

        ecard_ticket = urllib.parse.unquote(m_ticket.group(1))
        return self._exchange_ecard_ticket_to_water_token(ecard_ticket)
