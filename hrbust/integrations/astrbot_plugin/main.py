"""
HRBUST Toolkit -> AstrBot 微信机器人插件
支持在微信群与私聊中通过自然语言直接查询：
• 查浴室 / 洗澡空闲大盘
• 查成绩 / GPA 学业汇总
• 查考试 / 考场教室与座位号
• 查消费 / 一卡通流水账单
• 查学分 / 培养方案完成度
• 查教室 <教学楼> 空闲自习室
• 查课表 / 今日课程
• 今日教务 / 校内通告早报
"""

import re
from typing import Optional

class AstrBotHrbustPlugin:
    def __init__(self, context=None):
        self.context = context

    async def on_user_message(self, message: str) -> Optional[str]:
        msg = message.strip()
        if not msg:
            return None

        # 1. 浴室水控大盘
        if msg in ["查浴室", "查水控", "洗澡", "浴场大盘"]:
            from ...services.water_svc import WaterService
            from ...core.auth import get_credentials, get_cas_credentials, get_water_token, get_water_account

            _, token = get_water_token()
            u, _ = get_credentials()
            cas_u, _ = get_cas_credentials()
            account = get_water_account() or cas_u or u or "16264"
            if not token and not get_water_account():
                return "⚠️ 未检测到水控凭据！请在终端运行 `hrbust auth` 扫码或输入统一密码认证。"

            svc = WaterService()
            try:
                items = svc.get_dashboard(account, token)
                reply = ["🛁 【哈理工浴室与热水实时大盘】"]
                active_res = None
                for item in items:
                    free_rate = item["free_rate"]
                    rate_pct = free_rate if free_rate > 1.0 else free_rate * 100.0
                    act_kind = item.get("act_kind", 0)
                    book_code = item.get("book_code", "")
                    if act_kind == 1 and book_code:
                        active_res = f"⚠️ 当前占用: {item['name']} (出水码: {book_code})"
                        status = f"🟡已约({book_code})"
                    elif rate_pct > 70:
                        status = "🟢极佳"
                    elif rate_pct > 30:
                        status = "🟡正常"
                    else:
                        status = "🔴拥挤"
                    reply.append(f"• {item['name']}: {status} {rate_pct:.1f}% ({item['total_positions']}台机位)")
                if active_res:
                    reply.append(f"\n{active_res} (发送「取消预约」可释放机位)")
                return "\n".join(reply)
            except Exception as e:
                return f"❌ 获取浴室状态失败: {e}"

        # 1.1 微信快速预约洗澡出码
        elif msg.startswith("约洗澡") or msg.startswith("约浴室"):
            from ...services.water_svc import WaterService
            from ...core.auth import get_credentials, get_cas_credentials, get_water_token, get_water_account

            parts = msg.split()
            target_name = parts[1] if len(parts) > 1 else "南区男浴"
            name_to_class = {"南区男浴": 6, "南区女浴": 7, "西区男浴": 8, "西区女浴": 9, "公寓热水": 10}
            class_no = name_to_class.get(target_name, 6)

            _, token = get_water_token()
            u, _ = get_credentials()
            cas_u, _ = get_cas_credentials()
            account = get_water_account() or cas_u or u or "16264"
            svc = WaterService()
            try:
                res = svc.book_bath(class_no, account, token)
                if res.get("success") or res.get("RetNo") == 0:
                    code = res.get("BookCode") or res.get("book_code") or "8888"
                    return f"✅ 预约成功！\n📍 场所: {target_name}\n🔑 出水预约码: 【{code}】\n⏳ 提示: 请于 60 分钟内使用完毕。"
                else:
                    return f"❌ 预约未通过: {res.get('RetDsp') or res.get('msg')}"
            except Exception as e:
                return f"❌ 预约请求异常: {e}"

        # 1.2 微信快速取消预约释放机位
        elif msg in ["取消预约", "退水控", "释放机位", "取消洗澡"]:
            from ...services.water_svc import WaterService
            from ...core.auth import get_credentials, get_cas_credentials, get_water_token, get_water_account

            _, token = get_water_token()
            u, _ = get_credentials()
            cas_u, _ = get_cas_credentials()
            account = get_water_account() or cas_u or u or "16264"
            svc = WaterService()
            try:
                # 遍历查找当前哪个场所被占用
                items = svc.get_dashboard(account, token)
                active = next((it for it in items if it.get("act_kind") == 1 or it.get("book_code")), None)
                if not active:
                    return "💡 当前名下没有正在生效中的水房预约占用。"
                c_res = svc.cancel_bath(active["class_no"], account, token)
                if c_res.get("success") or c_res.get("RetNo") == 0:
                    return f"✔ 已成功取消【{active['name']}】的出水预约（原码: {active.get('book_code')}），机位已释放！"
                else:
                    return f"❌ 取消预约未通过: {c_res.get('msg') or c_res.get('RetDsp')}"
            except Exception as e:
                return f"❌ 取消操作异常: {e}"

        # 2. 个人成绩大盘与 GPA
        elif msg in ["查成绩", "成绩单", "查绩点", "gpa", "GPA"]:
            from ...core.auth import get_credentials
            from ...core.jwzx import JwzxEngine
            from ...services.score_svc import ScoreService

            u, p = get_credentials()
            if not u or not p:
                return "⚠️ 未绑定教务账号！请先在终端运行 `hrbust login <学号> <密码>`。"

            engine = JwzxEngine()
            if not engine.login(u, p):
                return "❌ 教务网登录失败，请检查账号密码或验证码。"

            svc = ScoreService(engine)
            res = svc.get_scores()
            if res.get("blocked"):
                return f"⚠️ 成绩受限: {res.get('reason')}"

            scores = res.get("scores", [])
            summary = res.get("summary", {})
            reply = [f"📊 【哈理工本科成绩单 (共 {len(scores)} 门)】"]
            for s in scores[-6:]:
                reply.append(f"• {s['course_name']}: {s['final_score']} (学分:{s['credit']}, 绩点:{s['gpa']})")
            reply.append(f"\n🎓 总学分: {summary.get('total_credits')} | 均分: {summary.get('weighted_avg_score')} | GPA: {summary.get('gpa')}")
            return "\n".join(reply)

        # 3. 考试安排与座位号
        elif msg in ["查考试", "考试安排", "考场", "座位号", "考试日程"]:
            from ...core.auth import get_credentials
            from ...core.jwzx import JwzxEngine
            from ...services.exam_svc import ExamService

            u, p = get_credentials()
            if not u or not p:
                return "⚠️ 未绑定教务账号！请先在终端运行 `hrbust login <学号> <密码>`。"

            engine = JwzxEngine()
            if not engine.login(u, p):
                return "❌ 教务网登录失败，请检查账号密码。"

            svc = ExamService(engine)
            res = svc.get_exams()
            exams = res.get("exams", [])
            if not exams:
                return f"💡 {res.get('msg', '当前暂无考试安排')}"

            reply = [f"📝 【哈理工期末考场与座位号 (共 {len(exams)} 门)】"]
            for e in exams[:6]:
                reply.append(f"• {e['course_name']} [{e['countdown_desc']}]\n  📅 时间: {e['exam_time']}\n  🏫 考场: {e['location']} (座位号: {e['seat_no']})")
            return "\n".join(reply)

        # 4. 一卡通消费账单流水
        elif msg in ["查消费", "一卡通账单", "消费流水", "饭卡流水", "账单"]:
            from ...core.auth import get_credentials, get_cas_credentials, get_water_token, get_water_account
            from ...services.water_svc import WaterService

            _, token = get_water_token()
            u, _ = get_credentials()
            cas_u, _ = get_cas_credentials()
            account = get_water_account() or cas_u or u or "16264"
            if not token and not get_water_account():
                return "⚠️ 未检测到水控凭据！请在终端运行 `hrbust auth` 扫码或输入统一密码认证。"

            svc = WaterService()
            try:
                res = svc.get_cost_records(account, token)
                records = res.get("records", [])
                summary = res.get("summary", {})
                if not records:
                    return "💡 近期暂无一卡通消费流水记录。"

                reply = [f"💳 【一卡通近期消费账单 (共 {summary.get('total_count')} 笔)】"]
                for r in records[:5]:
                    reply.append(f"• {r['time']}: {r['place']} (-¥{r['amount']:.2f})")
                reply.append(f"\n💰 累计支出: ¥ {summary.get('total_cost')}")
                return "\n".join(reply)
            except Exception as e:
                return f"❌ 获取一卡通账单失败: {e}"

        # 5. 培养方案学分审查
        elif msg in ["查学分", "培养方案", "毕业学分", "学分进度"]:
            from ...core.auth import get_credentials
            from ...core.jwzx import JwzxEngine
            from ...services.plan_svc import PlanService

            u, p = get_credentials()
            if not u or not p:
                return "⚠️ 未绑定教务账号！请先在终端运行 `hrbust login <学号> <密码>`。"

            engine = JwzxEngine()
            if not engine.login(u, p):
                return "❌ 教务网登录失败，请检查账号密码。"

            svc = PlanService(engine)
            res = svc.get_plan()
            if not res.get("has_plan"):
                return f"💡 {res.get('msg', '暂无教学计划数据')}"

            summary = res.get("summary", {})
            reply = [
                "🎯 【哈理工本科培养方案毕业审查】",
                f"• 计划总学分: {summary.get('total_plan_credits')} 分",
                f"• 已修得学分: {summary.get('completed_credits')} 分",
                f"• 尚欠修读学分: {summary.get('remaining_credits')} 分",
                f"• 毕业修读进度: {summary.get('completion_rate')}%"
            ]
            return "\n".join(reply)

        # 6. 空教室自习室
        elif msg.startswith("查教室") or msg.startswith("空教室"):
            from ...core.auth import get_credentials
            from ...core.jwzx import JwzxEngine
            from ...services.room_svc import RoomService

            parts = msg.split()
            building = parts[1] if len(parts) > 1 else "南一"

            u, p = get_credentials()
            if not u or not p:
                return "⚠️ 未绑定教务账号！请先在终端运行 `hrbust login <学号> <密码>`。"

            engine = JwzxEngine()
            if not engine.login(u, p):
                return "❌ 教务网登录失败，请检查账号密码。"

            svc = RoomService(engine)
            b_info = svc.BUILDINGS.get(building) or svc.BUILDINGS["南一"]
            rooms = svc.get_building_rooms(b_info["aid"], b_info["id"])
            if not rooms:
                return f"💡 {b_info['name']} 当前未检索到教室数据。"

            reply = [f"🏫 【{b_info['name']} 教室资源池 (共 {len(rooms)} 间)】"]
            for r in rooms[:10]:
                reply.append(f"• {r.get('name', '')} ({r.get('type', '普通')})")
            return "\n".join(reply)

        # 7. 今日早报与校内新闻
        elif msg in ["今日教务", "教务早报", "学校新闻", "校园动态"]:
            from ...services.news_svc import NewsService
            svc = NewsService()
            items = svc.get_daily_brief()
            reply = ["📢 【哈理工今日教务与新闻】"]
            for item in items[:6]:
                reply.append(f"[{item['type']}] {item['date']} {item['title']}")
            return "\n".join(reply)

        return None
