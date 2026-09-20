"""
HRBUST Toolkit 基础网络会话组件
实现代理屏蔽与校园内网探针防御机制
"""

import requests
import socket

CAMPUS_PROBE_HOST = "202.118.201.228"
CAMPUS_PROBE_URL = "http://jwzx.hrbust.edu.cn/academic/getCaptcha.do"

class CampusSession(requests.Session):
    """
    校园网专用请求会话
    自动屏蔽系统/命令行环境变量代理（如 HTTP_PROXY, HTTPS_PROXY），
    强制绑定无代理直连通道，避免因外部科学上网代理截胡校园内网请求导致 502。
    """
    def __init__(self):
        super().__init__()
        # 1. 禁用从环境读取代理 (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY)
        self.trust_env = False
        # 2. 显式清空代理映射字典，强制走底层直连 Socket
        self.proxies = {
            "http": None,
            "https": None,
        }
        # 3. 注入标准桌面浏览器 User-Agent
        self.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

def check_campus_network(timeout: float = 1.5) -> bool:
    """
    极速检测当前设备是否处于哈理工校园内网直连环境下
    通过向教务在线核心服务器发送直连探针判定连通性
    """
    try:
        session = CampusSession()
        res = session.get(CAMPUS_PROBE_URL, timeout=timeout)
        return res.status_code == 200
    except Exception:
        return False
