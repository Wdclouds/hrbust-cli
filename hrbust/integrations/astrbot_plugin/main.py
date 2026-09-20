"""
HRBUST Toolkit -> AstrBot 微信机器人插件
支持在微信群中直接发送指令触发水控空闲大盘与教务早报
"""

# AstrBot 标准插件结构示例
# 在 AstrBot 中创建插件目录并将此类放入即可

class AstrBotHrbustPlugin:
    def __init__(self, context=None):
        self.context = context

    async def on_user_message(self, message: str) -> str:
        msg = message.strip()
        if msg in ["查浴室", "查水控", "洗澡"]:
            # 引入本地服务
            from hrbust.services.water_svc import WaterService
            from hrbust.core.water import WaterEngine
            from hrbust.core.auth import get_credentials, get_water_token
            import json

            token = get_water_token()
            account, _ = get_credentials()
            if not token or not account:
                return "⚠️ 未配置水控 Token 或学号，请先在终端运行 `hrbust water` 初始化。"

            raw_info = WaterEngine.aes_encrypt(json.dumps({"ano": account}), account)
            svc = WaterService()
            items = svc.get_dashboard(raw_info, token)

            reply = ["🛁 【哈理工浴室实时大盘】"]
            for item in items:
                reply.append(f"• {item['name']}: 空闲率 {item['free_rate']:.1f}% ({item['total_positions']}台机位)")
            return "\n".join(reply)

        elif msg in ["今日教务", "教务早报", "学校新闻"]:
            from hrbust.services.news_svc import NewsService
            svc = NewsService()
            items = svc.get_daily_brief()
            reply = ["📢 【哈理工今日教务与新闻】"]
            for item in items[:6]:
                reply.append(f"[{item['type']}] {item['date']} {item['title']}")
            return "\n".join(reply)

        return None
