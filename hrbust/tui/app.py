"""
HRBUST TUI Command Center (Textual)
哈尔滨理工大学数字化校园命令中枢：居中 ASCII Logo + 底部常驻命令条 + 右侧 1/4 学校动态侧边栏
"""

import sys
import os
import shlex
from typing import List, Dict, Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Button,
    Label,
    Static,
    Input,
)

from ..core.network import check_campus_network
from ..core.auth import (
    get_credentials,
    set_credentials,
    get_cas_credentials,
    set_cas_credentials,
    get_water_token,
    set_water_token,
    clear_all_credentials,
)
from ..core.jwzx import JwzxEngine
from ..core.water import WaterEngine
from ..services.water_svc import WaterService
from ..services.room_svc import RoomService
from ..services.schedule_svc import ScheduleService
from ..services.news_svc import NewsService
from ..services.score_svc import ScoreService
from ..services.exam_svc import ExamService
from ..services.plan_svc import PlanService

ASCII_LOGO = r"""
██╗  ██╗██████╗ ██████╗ ██╗   ██╗███████╗████████╗
██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝╚══██╔══╝
███████║██████╔╝██████╔╝██║   ██║███████╗   ██║   
██╔══██║██╔══██╗██╔══██╗██║   ██║╚════██║   ██║   
██║  ██║██║  ██║██████╔╝╚██████╔╝███████║   ██║   
╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚══════╝   ╚═╝   
"""


class HrbustTuiApp(App):
    """哈理工数字化校园命令中枢 TUI"""

    TITLE = "HRBUST Toolkit · 数字化校园命令中枢"
    SUB_TITLE = "v1.1.0 · TUI Command Deck"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
        Binding("escape", "show_home", "返回主页", show=True, priority=True),
        Binding("r", "refresh_active", "刷新数据", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.water_engine = WaterEngine()
        self.water_svc = WaterService(self.water_engine)
        self.news_svc = NewsService()
        self.jwzx_engine: Optional[JwzxEngine] = None
        self.current_water_status: List[Dict[str, Any]] = []
        self.current_rooms: List[Dict[str, Any]] = []
        self.active_view = "hero"  # hero, water, room, schedule, news, status

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # 顶部全局状态指示条
        with Horizontal(classes="top-status-bar"):
            yield Static("🌐 [bold]校园网直连:[/bold] 正在探测...", id="net-status-label")
            yield Static("  |  👤 [bold]当前学号:[/bold] 未绑定", id="user-status-label")
            yield Static("  |  💧 [bold]水控凭据:[/bold] 未就绪", id="water-status-label")

        # 核心两列水平分割布局：左侧 3/4 主工作区 + 右侧 1/4 学校动态侧边栏
        with Horizontal(classes="layout-columns"):
            # ========== 左侧 3/4 核心操作甲板 ==========
            with Vertical(id="main-deck"):
                with Vertical(id="workspace-view"):
                    # 1. 默认首页：居中大 ASCII Logo 与快捷引导卡片
                    with Vertical(id="hero-view"):
                        yield Static(ASCII_LOGO, classes="ascii-logo")
                        yield Label("哈尔滨理工大学数字化校园全栈终端控制中心 · COMMAND DECK", classes="hero-subtitle")

                        with Vertical(classes="quick-guide-panel"):
                            yield Label("⌨️ [bold cyan]常用交互命令快捷指引[/bold cyan]", classes="guide-title")
                            yield Label("• 💧 浴室水控大盘: 输入 [bold yellow]water[/bold yellow] 查看空闲率并一键秒约出码", classes="guide-item")
                            yield Label("• 🏫 空闲自习教室: 输入 [bold yellow]room 南一[/bold yellow] (加 -m 筛选多媒体机房)", classes="guide-item")
                            yield Label("• 📅 学业今日课表: 输入 [bold yellow]today[/bold yellow] 或 [bold yellow]schedule[/bold yellow] 查看排课矩阵", classes="guide-item")
                            yield Label("• 📊 个人成绩大盘: 输入 [bold yellow]score[/bold yellow] 查看各科学分与加权平均 GPA", classes="guide-item")
                            yield Label("• 📝 考场与座位号: 输入 [bold yellow]exam[/bold yellow] 查看期末考试时间、考场教室与座位号", classes="guide-item")
                            yield Label("• 💳 一卡通消费流水: 输入 [bold yellow]card[/bold yellow] 查看洗浴开水扣费账单与总计", classes="guide-item")
                            yield Label("• 🎯 培养方案学分审查: 输入 [bold yellow]plan[/bold yellow] 查看已修/尚欠学分与毕业进度", classes="guide-item")
                            yield Label("• 📢 教务公告新闻: 输入 [bold yellow]news[/bold yellow] 或 [bold yellow]notice[/bold yellow] 查看官方通告", classes="guide-item")
                            yield Label("• 📰 通告正文阅读: 输入 [bold yellow]read <文章ID>[/bold yellow] 或在列表中按 Enter", classes="guide-item")
                            yield Label("• 🏛️ 办事大厅认证中心: 输入 [bold yellow]auth[/bold yellow] 官方扫码或账号密码打通水控与账单", classes="guide-item")
                            yield Label("• 🛡️ 账号凭据保险箱: 输入 [bold yellow]status[/bold yellow] / 输入 [bold yellow]logout[/bold yellow] 登出", classes="guide-item")
                            yield Label("• 🏠 返回本主页: 输入 [bold yellow]home[/bold yellow] 或按键盘 [bold yellow]Esc[/bold yellow] 键", classes="guide-item")

                    # 2. 浴室水控大盘视图
                    with Vertical(id="water-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("🚿 [bold cyan]全校浴室与热水实时大盘[/bold cyan]", classes="view-header-title")
                            yield Button("⚡ 一键预约选中机位", id="btn-water-book-deck", classes="primary")
                            yield Button("🔄 刷新", id="btn-water-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-1")
                        yield DataTable(id="table-water-deck")
                        with Vertical(classes="voucher-card"):
                            yield Label("💡 提示: 上下键选中场所后点击预约，或直接在表格按 Enter 即可秒级出码", id="voucher-deck-label")

                    # 3. 自习教室检索视图
                    with Vertical(id="room-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("🏫 [bold cyan]教学楼空闲教室检索[/bold cyan]", id="label-room-title", classes="view-header-title")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-2")
                        yield DataTable(id="table-room-deck")

                    # 4. 学业课表大盘视图
                    with Vertical(id="schedule-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("📅 [bold cyan]个人学期课表与教室排布[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 重新同步", id="btn-schedule-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-3")
                        yield DataTable(id="table-schedule-deck")

                    # 5. 教务公告新闻大盘视图
                    with Vertical(id="news-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("📢 [bold cyan]教务处官方最新公告与新闻[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 刷新", id="btn-news-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-4")
                        yield DataTable(id="table-news-deck")

                    # 6. 安全状态与保险箱视图
                    with Vertical(id="status-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("🛡️ [bold cyan]HRBUST 凭据与系统独立认证状态[/bold cyan]", classes="view-header-title")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-5")
                        with VerticalScroll():
                            with Vertical(classes="panel-box"):
                                yield Label("🔑 [bold cyan]1. 教务在线 (JWZX) 凭据[/bold cyan]")
                                yield Label("当前绑定学号: [dim]未配置[/dim]", id="status-deck-user")
                            with Vertical(classes="panel-box"):
                                yield Label("🏛️ [bold cyan]2. 网上办事大厅 / 统一身份认证 (CAS)[/bold cyan]")
                                yield Label("办事大厅凭据状态: [dim]未认证[/dim]", id="status-deck-water")
                            with Vertical(classes="panel-box"):
                                yield Label("💡 [bold yellow]独立认证指引[/bold yellow]")
                                yield Label("• 教务在线登录: 底部输入 [bold cyan]login <学号> <教务网密码>[/bold cyan] (查课表、成绩单、考试、自习室、培养方案)")
                                yield Label("• 办事大厅认证: 底部输入 [bold cyan]auth[/bold cyan] (进入专属认证中心，支持官方扫码或统一认证密码)")
                                yield Label("• 彻底清空销毁: 底部输入 [bold cyan]logout[/bold cyan] (一键销毁本地密文保险箱)")

                    # 7. 个人全科成绩与 GPA 大盘视图
                    with Vertical(id="score-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("📊 [bold cyan]全科学分与绩点 GPA 大盘[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 重新拉取", id="btn-score-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-6")
                        with Vertical(classes="voucher-card"):
                            yield Label("📊 正在统计学业汇总...", id="score-summary-deck-label")
                        yield DataTable(id="table-score-deck")

                    # 8. 校内公告与新闻正文详情阅读器
                    with Vertical(id="article-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("📰 [bold cyan]通告正文详情阅读器[/bold cyan]", classes="view-header-title")
                            yield Button("⬅️ 返回通告列表", id="btn-article-back-news")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-7")
                        with VerticalScroll(id="article-scroll-container"):
                            yield Label("加载中...", id="article-deck-title")
                            yield Label("", id="article-deck-meta")
                            yield Label("", id="article-deck-content")
                            yield Label("", id="article-deck-attachments")

                    # 9. 网上办事大厅 / 统一身份认证中心 (E-Hall Portal)
                    with Vertical(id="auth-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("🏛️ [bold cyan]哈理工网上办事大厅 / 统一身份认证中心 (E-Hall Portal)[/bold cyan]", classes="view-header-title")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-8")
                        with VerticalScroll(id="auth-scroll-container"):
                            yield Label("生活水控与一卡通服务隶属于网上办事大厅，与老教务网密码独立物理隔离", classes="auth-header-desc")
                            with Horizontal(id="auth-deck-split"):
                                # 官方选项一: 移动端扫码登录
                                with Vertical(classes="auth-card", id="auth-qr-card"):
                                    yield Label("📱 [bold yellow]官方选项一：移动端扫码登录[/bold yellow]", classes="auth-card-title")
                                    yield Label("[dim]使用微信 / 今日校园 / 哈理工移动端 扫描屏幕二维码[/dim]", classes="auth-card-sub")
                                    yield Label("", id="qr-code-display")
                                    yield Label("正在申请二维码...", id="qr-status-display")
                                    yield Button("🔄 重新生成二维码", id="btn-qr-refresh-deck")

                                # 官方选项二: 办事大厅统一认证密码登录
                                with Vertical(classes="auth-card", id="auth-pwd-card"):
                                    yield Label("🔑 [bold yellow]官方选项二：统一认证密码登录[/bold yellow]", classes="auth-card-title")
                                    yield Label("[dim]请输入哈理工全校统一身份认证密码 (与教务网密码相互独立)[/dim]", classes="auth-card-sub")
                                    yield Label("学号 (Account):")
                                    yield Input(placeholder="请输入学号 (如 2306010309)...", id="input-cas-user")
                                    yield Label("统一身份认证密码 (Password):")
                                    yield Input(placeholder="请输入办事大厅统一密码...", password=True, id="input-cas-pass")
                                    yield Button("🔑 提交统一身份认证", id="btn-cas-submit-deck", classes="primary")
                                    yield Label("", id="label-cas-submit-status")

                    # 10. 期末/期中考试安排与考场座位号大盘视图
                    with Vertical(id="exam-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("📝 [bold cyan]期末/期中考试日程与考场座位号大盘[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 重新拉取", id="btn-exam-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-9")
                        with Vertical(classes="voucher-card"):
                            yield Label("📝 正在检索考场与座位号日程...", id="exam-summary-deck-label")
                        yield DataTable(id="table-exam-deck")

                    # 11. 一卡通消费流水账单大盘视图
                    with Vertical(id="card-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("💳 [bold cyan]一卡通洗浴与热水消费流水大盘[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 重新拉取", id="btn-card-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-10")
                        with Vertical(classes="voucher-card"):
                            yield Label("💳 正在检索一卡通近期消费流水账单...", id="card-summary-deck-label")
                        yield DataTable(id="table-card-deck")

                    # 12. 个人培养方案与学分审查大盘视图
                    with Vertical(id="plan-view", classes="view-panel"):
                        with Horizontal(classes="view-header-bar"):
                            yield Label("🎯 [bold cyan]本科专业培养方案与学分完成度大盘[/bold cyan]", classes="view-header-title")
                            yield Button("🔄 重新拉取", id="btn-plan-refresh-deck")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-11")
                        with Vertical(classes="voucher-card"):
                            yield Label("🎯 正在审查培养方案学分进度...", id="plan-summary-deck-label")
                        yield DataTable(id="table-plan-deck")

                # 最下方常驻命令输入条
                with Horizontal(id="command-container"):
                    yield Static("❯", id="command-prompt-symbol")
                    yield Input(
                        placeholder="在此键入指令 (如: water, room 南一, today, news, status, help, exit)...",
                        id="command-input",
                    )

            # ========== 右侧 1/4 学校公告栏 ==========
            with Vertical(id="news-sidebar"):
                with Horizontal(classes="sidebar-header"):
                    yield Label("📢 今日校园动态", classes="sidebar-title")
                    yield Button("🔄", id="btn-sidebar-refresh", classes="primary")

                with VerticalScroll(id="news-scroll-container"):
                    yield Label("正在拉取教务处最新动态...", id="news-loading-hint")

        yield Footer()

    def on_mount(self) -> None:
        """应用初始化挂载"""
        self._init_data_tables()
        self._update_status_bar()
        self.action_show_home()
        self.action_load_sidebar_news()

    def _init_data_tables(self) -> None:
        """初始化表格结构"""
        t_water = self.query_one("#table-water-deck", DataTable)
        t_water.cursor_type = "row"
        t_water.add_columns("序号", "场所名称", "总机位", "当前空闲率", "拥挤度评级")

        t_room = self.query_one("#table-room-deck", DataTable)
        t_room.cursor_type = "row"
        t_room.add_columns("序号", "教室编号 / 房间名称", "设备类别", "所属教学楼")

        t_sched = self.query_one("#table-schedule-deck", DataTable)
        t_sched.cursor_type = "row"
        t_sched.add_columns("序号", "课程名称", "任课教师", "上课教室", "课程详情与节次")

        t_news = self.query_one("#table-news-deck", DataTable)
        t_news.cursor_type = "row"
        t_news.add_columns("发布日期", "分类", "公告 / 新闻标题", "文章 ID")

        t_score = self.query_one("#table-score-deck", DataTable)
        t_score.cursor_type = "row"
        t_score.add_columns("序号", "学年学期", "课程名称", "课程性质", "学分", "平时", "期末", "综合成绩", "绩点")

        t_exam = self.query_one("#table-exam-deck", DataTable)
        t_exam.cursor_type = "row"
        t_exam.add_columns("序号", "学年学期", "考试课程", "性质", "考试时间", "考场地点", "座位号", "备考状态")

        t_card = self.query_one("#table-card-deck", DataTable)
        t_card.cursor_type = "row"
        t_card.add_columns("序号", "交易时间", "消费场所 / 扣费项目", "扣款金额")

        t_plan = self.query_one("#table-plan-deck", DataTable)
        t_plan.cursor_type = "row"
        t_plan.add_columns("序号", "课程代码", "课程名称", "类别", "学分", "建议学期", "考核方式", "修读状态")

    def _update_status_bar(self) -> None:
        """刷新顶部状态指示条"""
        try:
            u, p = get_credentials()
            cas_u, _ = get_cas_credentials()
            _, w_tok = get_water_token()
            is_campus = check_campus_network()
            net_text = "🟢 [bold green]已直连校园网[/bold green]" if is_campus else "🟡 [bold yellow]外部网络/代理[/bold yellow]"
            self.query_one("#net-status-label", Static).update(f"🌐 [bold]校园网:[/bold] {net_text}")

            user_text = f"[bold green]{u}[/bold green]" if u else "[dim]未配置[/dim]"
            self.query_one("#user-status-label", Static).update(f"  |  👤 [bold]教务网:[/bold] {user_text}")

            if w_tok:
                water_status_text = f"[bold green]已认证 ({cas_u or '扫码'})[/bold green]"
                water_deck_desc = f"办事大厅状态: [bold green]已认证 ({cas_u or '扫码完成'}) | 水控与账单已就绪[/bold green]"
            else:
                water_status_text = "[dim]未认证[/dim]"
                water_deck_desc = "办事大厅状态: [yellow]未认证 (在底栏输入 auth 进入独立认证中心)[/yellow]"

            self.query_one("#water-status-label", Static).update(f"  |  🏛️ [bold]办事大厅:[/bold] {water_status_text}")
            self.query_one("#status-deck-user", Label).update(f"当前绑定学号: {user_text}")
            self.query_one("#status-deck-water", Label).update(water_deck_desc)
        except Exception:
            pass

    def switch_to_view(self, target: str) -> None:
        """单页面多视图无缝流转"""
        views = ["hero", "water", "room", "schedule", "news", "status", "score", "article", "auth", "exam", "card", "plan"]
        for v in views:
            widget = self.query_one(f"#{v}-view", Vertical)
            widget.display = (v == target)
        self.active_view = target
        self.query_one("#command-input", Input).focus()

    def action_show_home(self) -> None:
        """返回居中大 Logo 首页"""
        self.switch_to_view("hero")

    # ==================== 右侧 1/4 动态侧边栏 ====================

    @work(thread=True)
    def action_load_sidebar_news(self) -> None:
        """后台异步拉取右侧公告列表"""
        try:
            brief = self.news_svc.get_daily_brief()
            self.call_from_thread(self._render_sidebar_news, brief)
        except Exception as e:
            def _update_err():
                try:
                    self.query_one("#news-loading-hint", Label).update(f"[red]动态拉取失败: {e}[/red]")
                except Exception:
                    pass
            self.call_from_thread(_update_err)

    def _render_sidebar_news(self, items: List[Dict[str, Any]]) -> None:
        container = self.query_one("#news-scroll-container", VerticalScroll)
        container.remove_children()

        if not items:
            container.mount(Label("[dim]今日暂无最新公告发布[/dim]"))
            return

        for item in items[:15]:
            is_read = item.get("is_read", False)
            unread_badge = "" if is_read else "[bold yellow]● [/bold yellow]"
            card = Vertical(
                Label(f"{unread_badge}[{item.get('type', '通告')}] · {item.get('date', '今日')}", classes="news-date"),
                Label(f"• {item.get('title', '')}", classes="news-title"),
                classes="news-card",
            )
            container.mount(card)

    # ==================== 底部命令输入条交互 ====================

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """用户在底部输入条按回车提交命令"""
        raw_cmd = event.value.strip()
        event.input.value = ""
        if not raw_cmd:
            return

        self._execute_command(raw_cmd)

    def _execute_command(self, raw_cmd: str) -> None:
        """解析并执行用户输入的指令"""
        parts = shlex.split(raw_cmd)
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            self.app.exit()
        elif cmd in ("home", "clear", "cls"):
            self.action_show_home()
        elif cmd in ("water", "bath"):
            self.switch_to_view("water")
            self.action_fetch_water_data()
        elif cmd in ("room", "rooms"):
            building = args[0] if args else "南一"
            media_only = "-m" in args or "--media" in args
            self.switch_to_view("room")
            self.action_fetch_room_data(building, media_only)
        elif cmd in ("today", "schedule", "course", "courses"):
            self.switch_to_view("schedule")
            self.action_fetch_schedule_data()
        elif cmd in ("news", "notice"):
            self.switch_to_view("news")
            self.action_fetch_news_data()
        elif cmd == "login":
            if len(args) < 2:
                self.notify("格式错误: login <学号> <密码>", title="参数不足", severity="warning")
                self.switch_to_view("status")
            else:
                u, p = args[0], args[1]
                set_credentials(u, p)
                self.jwzx_engine = None
                self._update_status_bar()
                self.notify(f"学号 {u} 凭据已保存，正在后台尝试登录...", title="账号配置", severity="information")
                self.switch_to_view("status")
                self.action_test_jwzx_login(u, p)
        elif cmd == "logout":
            clear_all_credentials()
            self.jwzx_engine = None
            self._update_status_bar()
            self.notify("已成功登出并清空所有本地密文凭据", title="安全登出", severity="information")
            self.switch_to_view("status")
        elif cmd in ("status",):
            self._update_status_bar()
            self.switch_to_view("status")
        elif cmd in ("auth", "ehall", "qr", "water-qr"):
            self.switch_to_view("auth")
            self.action_start_qr_login_flow()
        elif cmd in ("cas", "cas-login", "auth-login"):
            if len(args) >= 2:
                self.action_submit_cas_password_login(args[0], args[1])
            else:
                self.switch_to_view("auth")
        elif cmd in ("plan", "plans", "program", "programs"):
            self.switch_to_view("plan")
            self.action_fetch_plan_data()
        elif cmd in ("card", "cards", "bill", "bills", "cost", "costs", "ecard"):
            self.switch_to_view("card")
            self.action_fetch_card_data()
        elif cmd in ("exam", "exams", "test", "tests"):
            self.switch_to_view("exam")
            self.action_fetch_exam_data()
        elif cmd in ("score", "scores", "gpa", "grade", "grades"):
            self.switch_to_view("score")
            self.action_fetch_score_data()
        elif cmd == "read":
            if not args:
                self.notify("格式错误: read <文章ID> (如: read 5534)", title="参数不足", severity="warning")
            else:
                self.action_open_article(args[0])

        elif cmd in ("help", "?"):
            self.action_show_home()
            self.notify("指令: water | room 南一 | today | exam | score | card | plan | news | auth | login <学号> <密码> | status | exit", title="命令帮助")
        else:
            self.notify(f"未识别指令 '{cmd}'，请输入 help 查看可用命令", title="命令提示", severity="warning")

    # ==================== 数据拉取与渲染 Workers ====================

    @work(thread=True)
    def action_test_jwzx_login(self, u: str, p: str) -> None:
        """后台验证教务在线登录态并尝试自动打通水控"""
        engine = JwzxEngine()
        success = engine.login(u, p)
        if success:
            self.jwzx_engine = engine
            self.notify("教务系统登录成功！现在可使用 room 或 today 命令", title="登录验证通过", severity="information")
        else:
            self.notify("教务在线登录失败：请检查学号密码或内网连接", title="登录失败", severity="error")



    @work(thread=True)
    def action_sync_water_in_background(self, u: str, p: str) -> None:
        """后台静默通过统一身份认证换取水控 Token 并刷新状态"""
        try:
            auto_water = self.water_svc.auto_auth_and_sync(u, p)
            if auto_water.get("success"):
                self.call_from_thread(self._update_status_bar)
                self.notify("✔ 统一身份认证已全自动激活水控凭据！(免抓包)", title="水控系统", severity="information")
        except Exception:
            pass

    @work(thread=True)
    def action_fetch_water_data(self) -> None:
        """后台拉取水控数据并渲染（含无感自动打通）"""
        u, p = get_credentials()
        w_info, w_tok = get_water_token()

        if not w_tok and u and p:
            # 方案 1: 水控未配置时，自动尝试通过 CAS 静默换票
            try:
                auto_water = self.water_svc.auto_auth_and_sync(u, p)
                if auto_water.get("success"):
                    self.call_from_thread(self._update_status_bar)
                    self.notify("✔ 统一身份认证已全自动激活水控凭据！", title="水控系统", severity="information")
                    w_info, w_tok = get_water_token()
            except Exception:
                pass

        if not w_tok:
            self.notify("未配置水控 Token！可在底部输入 token <你的Token>", title="水控系统", severity="warning")
            def _show_empty_token():
                table = self.query_one("#table-water-deck", DataTable)
                table.clear()
                table.add_row("-", "未配置水控 Token (在底部输入: token <你的Token>)", "0 台", "0%", "未配置")
            self.call_from_thread(_show_empty_token)
            return

        try:
            from ..core.auth import get_water_account, get_cas_credentials
            account = get_water_account()
            if not account:
                cas_u, _ = get_cas_credentials()
                account = cas_u or u or "16264"
            status_list = self.water_svc.get_dashboard(account, w_tok)
            self.current_water_status = status_list
            self.call_from_thread(self._populate_water_table, status_list)
        except Exception as e:
            self.notify(f"水控大盘异常: {e} (若Token失效请重新设置)", title="水控系统", severity="warning")
            def _show_err():
                table = self.query_one("#table-water-deck", DataTable)
                table.clear()
                table.add_row("!", f"拉取失败: {e} (Token可能已过期)", "0 台", "0%", "异常")
            self.call_from_thread(_show_err)

    def _populate_water_table(self, items: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-water-deck", DataTable)
        table.clear()
        for idx, item in enumerate(items, 1):
            free_rate = item.get("free_rate", 0.0)
            rate_pct = free_rate if free_rate > 1.0 else free_rate * 100.0
            act_kind = item.get("act_kind", 0)
            book_code = item.get("book_code", "")

            if act_kind == 1 and book_code:
                status_text = f"[bold yellow on black] 已约 {book_code} (Enter取消) [/bold yellow on black]"
                rate_text = f"[bold yellow]{rate_pct:.1f}%[/bold yellow]"
            elif rate_pct > 70:
                rate_text = f"[green]{rate_pct:.1f}%[/green]"
                status_text = "[bold green]极佳 · 无需排队[/bold green]"
            elif rate_pct > 30:
                rate_text = f"[yellow]{rate_pct:.1f}%[/yellow]"
                status_text = "[bold yellow]正常 · 少量空位[/bold yellow]"
            else:
                rate_text = f"[red]{rate_pct:.1f}%[/red]"
                status_text = "[bold red]拥挤 · 机位紧张[/bold red]"

            table.add_row(
                str(idx),
                item.get("name", "未知"),
                f"{item.get('total_positions', 0)} 台",
                rate_text,
                status_text,
                key=str(item.get("class_no", idx)),
            )

    @work(thread=True)
    def action_book_water_from_deck(self) -> None:
        """从主命令台一键预约出水码或取消已有预约"""
        table = self.query_one("#table-water-deck", DataTable)
        if table.row_count == 0:
            self.notify("大盘暂无数据，请先刷新", severity="warning")
            return

        cursor_row = table.cursor_row
        target = self.current_water_status[cursor_row] if 0 <= cursor_row < len(self.current_water_status) else self.current_water_status[0]
        u, _ = get_credentials()
        _, w_tok = get_water_token()
        from ..core.auth import get_water_account, get_cas_credentials
        account = get_water_account()
        if not account:
            cas_u, _ = get_cas_credentials()
            account = cas_u or u or "16264"
        token = w_tok or ""

        # 1. 如果当前选中的场所已经被自己预约占用 -> 执行一键取消释放机位
        if target.get("act_kind") == 1 or target.get("book_code"):
            self.notify(f"正在申请取消 {target['name']} 的预约占用...", title="释放机位")
            try:
                res = self.water_svc.cancel_bath(target["class_no"], account, token)
                if res.get("success") or res.get("RetNo") == 0:
                    self.notify(f"✔ 已成功取消 {target['name']} 预约，机位已释放！", title="取消成功", severity="information")
                    self.action_fetch_water_data()
                else:
                    msg = res.get("RetDsp") or res.get("msg") or "取消失败"
                    self.notify(f"取消预约失败: {msg}", title="取消回执", severity="error")
            except Exception as e:
                self.notify(f"取消预约异常: {e}", severity="error")
            return

        # 2. 如果在其他场所已经有生效中的预约码 -> 提示冲突
        active_other = next((it for it in self.current_water_status if (it.get("act_kind") == 1 or it.get("book_code")) and it.get("class_no") != target["class_no"]), None)
        if active_other:
            self.notify(f"你当前在【{active_other['name']}】已有生效中的预约码 {active_other.get('book_code')}，请先选中它按回车取消后再预约新场所！", title="机位占用冲突", severity="warning")
            return

        # 3. 正常发起出水码预约
        self.notify(f"正在申请 {target['name']} 出水预约码...", title="水控预约")
        try:
            res = self.water_svc.book_bath(target["class_no"], account, token)
            is_success = res.get("success") or res.get("RetNo") == 0 or res.get("ret_no") == 0
            if is_success:
                code = res.get("BookCode") or res.get("book_code") or "8888"
                self.call_from_thread(self._render_deck_voucher, target["name"], code)
                self.notify(f"预约成功！出水码: {code}", title="出码成功", severity="information")
                self.action_fetch_water_data()
            else:
                msg = res.get("RetDsp") or res.get("msg") or "预约失败"
                self.notify(f"预约失败: {msg}", title="预约回执", severity="error")
        except Exception as e:
            self.notify(f"预约请求异常: {e}", title="水控异常", severity="error")

    def _render_deck_voucher(self, place_name: str, code: str) -> None:
        self.query_one("#voucher-deck-label", Label).update(
            f"🎉 [bold green]{place_name} 预约成功[/bold green]  |  "
            f"出水预约码: [bold yellow on black]  {code}  [/bold yellow on black]  (60 分钟内有效)"
        )

    @work(thread=True)
    def action_fetch_room_data(self, building: str, media_only: bool) -> None:
        """后台拉取教室资源"""
        default_b = RoomService.BUILDINGS["南一"]
        b_info = RoomService.BUILDINGS.get(building) or default_b

        u, p = get_credentials()
        if not u or not p:
            self.notify("未绑定教务账号！请在底部输入: login <学号> <密码>", title="需要登录", severity="warning")
            def _show_no_auth():
                table = self.query_one("#table-room-deck", DataTable)
                self.query_one("#label-room-title", Label).update(f"🏫 [bold cyan]{b_info['name']} 教室资源池 (需要登录)[/bold cyan]")
                table.clear()
                table.add_row("-", "未绑定教务账号，请在底部键入: login <学号> <密码>", "未配置", b_info["name"])
            self.call_from_thread(_show_no_auth)
            return

        self.notify(f"正在检索 {b_info['name']} 教室资源池...", title="自习教室")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    def _show_login_fail():
                        table = self.query_one("#table-room-deck", DataTable)
                        table.clear()
                        table.add_row("!", "教务在线登录失败，请检查账号密码或验证码", "异常", b_info["name"])
                    self.call_from_thread(_show_login_fail)
                    return

            room_svc = RoomService(self.jwzx_engine)
            rooms = room_svc.get_building_rooms(b_info["aid"], b_info["id"])
            if media_only:
                rooms = [r for r in rooms if r.get("is_media")]

            self.call_from_thread(self._populate_room_table, rooms, b_info["name"])
            self.notify(f"检索到 {len(rooms)} 间教室资源", title="自习教室", severity="information")
        except Exception as e:
            self.notify(f"检索教室失败: {e}", severity="error")
            def _show_fetch_err():
                table = self.query_one("#table-room-deck", DataTable)
                table.clear()
                table.add_row("!", f"检索教室失败: {e}", "异常", b_info["name"])
            self.call_from_thread(_show_fetch_err)

    def _populate_room_table(self, rooms: List[Dict[str, Any]], b_name: str) -> None:
        table = self.query_one("#table-room-deck", DataTable)
        self.query_one("#label-room-title", Label).update(f"🏫 [bold cyan]{b_name} 教室资源池 (共 {len(rooms)} 间)[/bold cyan]")
        table.clear()
        for idx, r in enumerate(rooms, 1):
            tag = "[bold cyan][多媒体/实验][/bold cyan]" if r.get("is_media") else "[dim][普通教室][/dim]"
            table.add_row(str(idx), r.get("name", ""), tag, b_name)

    @work(thread=True)
    def action_fetch_schedule_data(self) -> None:
        """后台拉取课表数据 (支持本地 SQLite 离线快照秒开)"""
        u, p = get_credentials()
        from ..services.schedule_svc import ScheduleService

        if not u or not p:
            # 检查是否有本地离线快照
            svc_offline = ScheduleService(None)
            cached_courses = svc_offline.get_timetable()
            if cached_courses:
                self.call_from_thread(self._populate_schedule_table, cached_courses)
                self.notify(f"已从本地数据库载入离线课表快照 (共 {len(cached_courses)} 门课程)", title="离线课表", severity="information")
                return

            self.notify("未绑定教务账号！请在底部输入: login <学号> <密码>", title="需要登录", severity="warning")
            def _show_no_sched():
                table = self.query_one("#table-schedule-deck", DataTable)
                table.clear()
                table.add_row("-", "未绑定教务账号，请在底部键入: login <学号> <密码>", "未配置", "-", "-")
            self.call_from_thread(_show_no_sched)
            return

        self.notify("正在同步大课表...", title="学业课表")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    # 登录失败，降级读取离线快照
                    svc_offline = ScheduleService(None)
                    cached_courses = svc_offline.get_timetable()
                    if cached_courses:
                        self.call_from_thread(self._populate_schedule_table, cached_courses)
                        self.notify("教务在线连接受限，已自动为您载入本地离线课表快照！", title="离线课表", severity="warning")
                        return

                    self.notify("教务在线自动登录失败且无本地缓存", severity="error")
                    def _show_login_fail():
                        table = self.query_one("#table-schedule-deck", DataTable)
                        table.clear()
                        table.add_row("!", "教务在线登录失败，请检查账号密码或内网连接", "异常", "-", "-")
                    self.call_from_thread(_show_login_fail)
                    return

            svc = ScheduleService(self.jwzx_engine)
            courses = svc.get_timetable()
            self.call_from_thread(self._populate_schedule_table, courses)
            self.notify(f"课表同步完成，共计 {len(courses)} 门课程", title="学业课表", severity="information")
        except Exception as e:
            # 异常时同样尝试降级读取离线快照
            svc_offline = ScheduleService(None)
            cached_courses = svc_offline.get_timetable()
            if cached_courses:
                self.call_from_thread(self._populate_schedule_table, cached_courses)
                self.notify(f"网络受限 ({e})，已平滑展示本地离线课表快照", title="离线课表", severity="warning")
                return

            self.notify(f"课表拉取失败: {e}", severity="error")
            def _show_fetch_err():
                table = self.query_one("#table-schedule-deck", DataTable)
                table.clear()
                table.add_row("!", f"课表拉取失败: {e}", "异常", "-", "-")
            self.call_from_thread(_show_fetch_err)

    def _populate_schedule_table(self, courses: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-schedule-deck", DataTable)
        table.clear()
        for idx, c in enumerate(courses, 1):
            table.add_row(
                str(idx),
                c.get("title", ""),
                c.get("teacher", ""),
                f"[bold yellow]{c.get('classroom', '')}[/bold yellow]",
                c.get("raw", "").replace("\n", " "),
            )

    @work(thread=True)
    def action_fetch_news_data(self) -> None:
        """后台拉取新闻列表"""
        try:
            notices = self.news_svc.get_articles(NewsService.COL_NOTICE, page=1)
            self.call_from_thread(self._populate_news_table, notices)
        except Exception as e:
            self.notify(f"公告获取失败: {e}", severity="error")

    def _populate_news_table(self, items: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-news-deck", DataTable)
        table.clear()
        for a in items:
            table.add_row(
                a.get("date", ""),
                "教务公告",
                a.get("title", ""),
                str(a.get("id", "")),
                key=str(a.get("id", "")),
            )

    # ==================== 任务 A: 学业成绩大盘 Workers ====================

    @work(thread=True)
    def action_fetch_score_data(self) -> None:
        """后台拉取全科成绩与 GPA 汇总"""
        u, p = get_credentials()
        if not u or not p:
            self.notify("未绑定教务账号！请在底部输入: login <学号> <密码>", title="需要登录", severity="warning")
            def _show_no_score():
                table = self.query_one("#table-score-deck", DataTable)
                table.clear()
                table.add_row("-", "-", "未绑定教务账号，请在底部键入: login <学号> <密码>", "-", "-", "-", "-", "-", "-")
                self.query_one("#score-summary-deck-label", Label).update("⚠️ 请先绑定教务账号后查看成绩大盘")
            self.call_from_thread(_show_no_score)
            return

        self.notify("正在登录教务在线检索全科成绩...", title="学业大盘")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    def _show_login_fail():
                        table = self.query_one("#table-score-deck", DataTable)
                        table.clear()
                        table.add_row("!", "-", "教务在线登录失败，请检查账号密码或验证码", "-", "-", "-", "-", "-", "-")
                    self.call_from_thread(_show_login_fail)
                    return

            svc = ScoreService(self.jwzx_engine)
            res = svc.get_scores()
            self.call_from_thread(self._populate_score_table, res)
            if res.get("blocked"):
                self.notify(f"成绩受限: {res.get('reason')}", severity="warning")
            else:
                summary = res.get("summary", {})
                self.notify(f"成绩同步完成！总学分: {summary.get('total_credits')} | GPA: {summary.get('gpa')}", title="学业成绩", severity="information")
        except Exception as e:
            self.notify(f"拉取成绩失败: {e}", severity="error")
            def _show_fetch_err():
                table = self.query_one("#table-score-deck", DataTable)
                table.clear()
                table.add_row("!", "-", f"拉取成绩失败: {e}", "-", "-", "-", "-", "-", "-")
            self.call_from_thread(_show_fetch_err)

    def _populate_score_table(self, res: Dict[str, Any]) -> None:
        table = self.query_one("#table-score-deck", DataTable)
        summary_lbl = self.query_one("#score-summary-deck-label", Label)
        table.clear()

        if res.get("blocked"):
            summary_lbl.update(f"⚠️ [bold yellow]{res.get('reason')}[/bold yellow]")
            table.add_row("!", "-", "成绩查看受限（教务处未评教拦截）", "-", "-", "-", "-", "-", "-")
            return

        scores = res.get("scores", [])
        summary = res.get("summary", {})

        summary_lbl.update(
            f"📊 [bold cyan]学业总评[/bold cyan]  |  "
            f"总修读: [bold green]{summary.get('total_courses', len(scores))} 门[/bold green]  |  "
            f"已获学分: [bold green]{summary.get('total_credits', 0.0)}[/bold green]  |  "
            f"加权平均分: [bold green]{summary.get('weighted_avg_score', 0.0)}[/bold green]  |  "
            f"官方加权 GPA: [bold yellow on black]  {summary.get('gpa', 0.0)}  [/bold yellow on black]"
        )

        for idx, s in enumerate(scores, 1):
            table.add_row(
                str(idx),
                s.get("term", ""),
                s.get("course_name", ""),
                s.get("category", "必修"),
                str(s.get("credit", 0.0)),
                str(s.get("regular_score", "-")),
                str(s.get("exam_score", "-")),
                f"[bold yellow]{s.get('final_score', '')}[/bold yellow]",
                f"[bold cyan]{s.get('gpa', 0.0)}[/bold cyan]"
            )

    # ==================== 任务 B: 通告正文阅读器 Workers ====================

    @work(thread=True)
    def action_open_article(self, article_id: str, col: int = 354) -> None:
        """后台拉取文章正文并切入详情阅读器"""
        self.call_from_thread(self.switch_to_view, "article")
        self.notify(f"正在拉取文章 #{article_id} 正文...", title="阅读器")
        try:
            art = self.news_svc.get_article_detail(article_id, column_id=col)
            self.call_from_thread(self._render_article_detail, art)
        except Exception as e:
            self.notify(f"加载正文失败: {e}", severity="error")

    def _render_article_detail(self, art: Dict[str, Any]) -> None:
        title_lbl = self.query_one("#article-deck-title", Label)
        meta_lbl = self.query_one("#article-deck-meta", Label)
        body_lbl = self.query_one("#article-deck-content", Label)
        att_lbl = self.query_one("#article-deck-attachments", Label)

        title_lbl.update(f"[bold cyan]{art.get('title', '')}[/bold cyan]")
        meta_lbl.update(
            f"📅 发布时间: [dim]{art.get('date', '未知')}[/dim]  |  "
            f"🏛️ 来源部门: [dim]{art.get('department', '教务处')}[/dim]  |  "
            f"🆔 文章 ID: [dim]{art.get('id', '')}[/dim]"
        )
        body_lbl.update(art.get("content", "[dim]该通告暂无正文文本[/dim]"))

        atts = art.get("attachments", [])
        if atts:
            att_lines = ["[bold yellow]📎 附件下载列表：[/bold yellow]"]
            for idx, a in enumerate(atts, 1):
                att_lines.append(f"  [{idx}] {a.get('name', '附件')}\n      👉 {a.get('url', '')}")
            att_lbl.update("\n".join(att_lines))
        else:
            att_lbl.update("[dim]（本文无附加下载文件）[/dim]")

    # ==================== 任务 F: 培养方案学分审查 Workers ====================

    @work(thread=True)
    def action_fetch_plan_data(self) -> None:
        """后台拉取本科专业培养方案与已修/尚欠学分总览"""
        u, p = get_credentials()
        if not u or not p:
            self.notify("未绑定教务账号！请在底部输入: login <学号> <密码>", title="需要登录", severity="warning")
            def _show_no_plan():
                table = self.query_one("#table-plan-deck", DataTable)
                table.clear()
                table.add_row("-", "-", "未绑定教务账号，请在底部键入: login <学号> <密码>", "-", "-", "-", "-", "-")
                self.query_one("#plan-summary-deck-label", Label).update("⚠️ 请先绑定教务账号后查看培养方案大盘")
            self.call_from_thread(_show_no_plan)
            return

        self.notify("正在登录教务在线核查培养方案进度...", title="培养方案")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    def _show_login_fail():
                        table = self.query_one("#table-plan-deck", DataTable)
                        table.clear()
                        table.add_row("!", "-", "教务在线登录失败，请检查账号密码或验证码", "-", "-", "-", "-", "-")
                    self.call_from_thread(_show_login_fail)
                    return

            svc = PlanService(self.jwzx_engine)
            res = svc.get_plan()
            self.call_from_thread(self._populate_plan_table, res)
            courses = res.get("courses", [])
            summary = res.get("summary", {})
            if not courses:
                self.notify("暂未检索到当前年级专业的教学计划大纲", severity="information")
            else:
                self.notify(f"培养方案同步完成！完成率: {summary.get('completion_rate')}% (尚欠 {summary.get('remaining_credits')} 学分)", title="培养方案", severity="information")
        except Exception as e:
            self.notify(f"拉取教学计划失败: {e}", severity="error")
            def _show_plan_err():
                table = self.query_one("#table-plan-deck", DataTable)
                table.clear()
                table.add_row("!", "-", f"拉取教学计划失败: {e}", "-", "-", "-", "-", "-")
            self.call_from_thread(_show_plan_err)

    def _populate_plan_table(self, res: Dict[str, Any]) -> None:
        table = self.query_one("#table-plan-deck", DataTable)
        summary_lbl = self.query_one("#plan-summary-deck-label", Label)
        table.clear()

        courses = res.get("courses", [])
        summary = res.get("summary", {})
        if not courses:
            summary_lbl.update(f"⚠️ [bold yellow]{res.get('msg', '当前暂无教学计划数据')}[/bold yellow]")
            table.add_row("-", "-", "教务在线未检索到当前专业的教学计划", "-", "-", "-", "-", "-")
            return

        summary_lbl.update(
            f"🎓 [bold cyan]毕业修读完成度[/bold cyan]  |  "
            f"总学分: [bold green]{summary.get('total_plan_credits')}[/bold green]  |  "
            f"已修得: [bold green]{summary.get('completed_credits')}[/bold green]  |  "
            f"尚欠: [bold red]{summary.get('remaining_credits')}[/bold red]  |  "
            f"进度: [bold yellow on black]  {summary.get('completion_rate')}%  [/bold yellow on black]"
        )

        for idx, c in enumerate(courses, 1):
            status_styled = "[bold green]✔ 已修得[/bold green]" if c.get("completed") else "[yellow]⏳ 未修读[/yellow]"
            table.add_row(
                str(idx),
                c.get("course_code", ""),
                c.get("course_name", ""),
                c.get("category", "必修"),
                str(c.get("credit", 0.0)),
                c.get("suggest_term", ""),
                c.get("exam_method", "考试"),
                status_styled
            )

    # ==================== 任务 E: 一卡通消费流水账单 Workers ====================

    @work(thread=True)
    def action_fetch_card_data(self) -> None:
        """后台拉取一卡通近期洗浴与热水消费流水"""
        w_info, w_tok = get_water_token()
        u, _ = get_credentials()
        if not w_tok:
            def _jump_auth_card():
                self.switch_to_view("auth")
                self.action_start_qr_login_flow()
            self.call_from_thread(_jump_auth_card)
            self.notify("未检测到网上办事大厅凭据，已为你跳转至办事大厅官方认证中心！", title="需要认证", severity="warning")
            return

        from ..core.auth import get_water_account, get_cas_credentials
        account = get_water_account()
        if not account:
            cas_u, _ = get_cas_credentials()
            account = cas_u or u or "16264"

        self.notify("正在拉取一卡通消费流水账单...", title="消费账单")
        try:
            res = self.water_svc.get_cost_records(account, w_tok)
            self.call_from_thread(self._populate_card_table, res)
            records = res.get("records", [])
            summary = res.get("summary", {})
            self.notify(f"已同步 {len(records)} 笔消费流水！总支出: ¥ {summary.get('total_cost')}", title="消费账单", severity="information")
        except Exception as e:
            self.notify(f"拉取消费账单失败: {e}", severity="error")
            def _show_card_err():
                table = self.query_one("#table-card-deck", DataTable)
                table.clear()
                table.add_row("!", "-", f"拉取消费流水失败: {e}", "-")
            self.call_from_thread(_show_card_err)

    def _populate_card_table(self, res: Dict[str, Any]) -> None:
        table = self.query_one("#table-card-deck", DataTable)
        summary_lbl = self.query_one("#card-summary-deck-label", Label)
        table.clear()

        records = res.get("records", [])
        summary = res.get("summary", {})
        if not records:
            summary_lbl.update("💡 [dim]近期暂无一卡通消费扣费流水明细[/dim]")
            table.add_row("-", "-", "暂无近期消费记录", "-")
            return

        summary_lbl.update(
            f"💰 [bold cyan]消费汇总[/bold cyan]  |  "
            f"近期消费: [bold green]{summary.get('total_count', len(records))} 笔[/bold green]  |  "
            f"累计支出: [bold yellow on black]  ¥ {summary.get('total_cost', 0.0)}  [/bold yellow on black]"
        )

        for idx, r in enumerate(records, 1):
            amt = r.get("amount", 0.0)
            table.add_row(
                str(idx),
                r.get("time", ""),
                r.get("place", "校园消费"),
                f"[bold yellow]-¥ {amt:.2f}[/bold yellow]"
            )

    # ==================== 任务 D: 考试日程与座位号大盘 Workers ====================

    @work(thread=True)
    def action_fetch_exam_data(self) -> None:
        """后台拉取期末/期中考试日程、地点与座位号"""
        u, p = get_credentials()
        if not u or not p:
            self.notify("未绑定教务账号！请在底部输入: login <学号> <密码>", title="需要登录", severity="warning")
            def _show_no_exam():
                table = self.query_one("#table-exam-deck", DataTable)
                table.clear()
                table.add_row("-", "-", "未绑定教务账号，请在底部键入: login <学号> <密码>", "-", "-", "-", "-", "-")
                self.query_one("#exam-summary-deck-label", Label).update("⚠️ 请先绑定教务账号后查看考试大盘")
            self.call_from_thread(_show_no_exam)
            return

        self.notify("正在登录教务在线检索考场与座位安排...", title="考试大盘")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    def _show_login_fail():
                        table = self.query_one("#table-exam-deck", DataTable)
                        table.clear()
                        table.add_row("!", "-", "教务在线登录失败，请检查账号密码或验证码", "-", "-", "-", "-", "-")
                    self.call_from_thread(_show_login_fail)
                    return

            svc = ExamService(self.jwzx_engine)
            res = svc.get_exams()
            self.call_from_thread(self._populate_exam_table, res)
            exams = res.get("exams", [])
            if not exams:
                self.notify("当前暂无排考日程", severity="information")
            else:
                self.notify(f"已同步 {len(exams)} 门课程的考场与座位号！", title="考试大盘", severity="information")
        except Exception as e:
            self.notify(f"拉取考试安排失败: {e}", severity="error")
            def _show_fetch_err():
                table = self.query_one("#table-exam-deck", DataTable)
                table.clear()
                table.add_row("!", "-", f"拉取考试安排失败: {e}", "-", "-", "-", "-", "-")
            self.call_from_thread(_show_fetch_err)

    def _populate_exam_table(self, res: Dict[str, Any]) -> None:
        table = self.query_one("#table-exam-deck", DataTable)
        summary_lbl = self.query_one("#exam-summary-deck-label", Label)
        table.clear()

        exams = res.get("exams", [])
        if not exams:
            summary_lbl.update(f"⚠️ [bold yellow]{res.get('msg', '当前暂无考试安排')}[/bold yellow]")
            table.add_row("-", "-", "教务处当前学期暂未发布正式考试安排", "-", "-", "-", "-", "-")
            return

        summary_lbl.update(f"📝 [bold cyan]期末考试总览[/bold cyan]  |  共排定 [bold green]{len(exams)} 门[/bold green] 考试科目  |  请提前确认考场教学楼与座位号")

        for idx, e in enumerate(exams, 1):
            status_desc = e.get("countdown_desc", "")
            if "今日" in status_desc or "明天" in status_desc:
                status_styled = f"[bold red on white] {status_desc} [/bold red on white]"
            elif "还有" in status_desc and (e.get("days_left") or 99) <= 7:
                status_styled = f"[bold yellow]{status_desc}[/bold yellow]"
            elif "已考完" in status_desc:
                status_styled = f"[dim]{status_desc}[/dim]"
            else:
                status_styled = f"[cyan]{status_desc}[/cyan]"

            table.add_row(
                str(idx),
                e.get("term", ""),
                e.get("course_name", ""),
                e.get("exam_type", "正常考试"),
                f"[bold yellow]{e.get('exam_time', '待排定')}[/bold yellow]",
                f"[cyan]{e.get('location', '考场未公布')}[/cyan]",
                f"[bold green]{e.get('seat_no', '-')}[/bold green]",
                status_styled
            )

    @work(thread=True)
    def action_submit_cas_password_login(self, u: str, p: str) -> None:
        """后台提交网上办事大厅 / 统一身份认证密码登录"""
        self.notify(f"正在向统一身份认证中心 (CAS) 提交学号 {u} 凭据...", title="办事大厅认证")
        def _set_loading():
            try:
                self.query_one("#label-cas-submit-status", Label).update("[cyan]⏳ 正在提交统一身份认证中心验明身份...[/cyan]")
            except Exception:
                pass
        self.call_from_thread(_set_loading)

        try:
            res = self.water_svc.login_by_password(u, p)
            if res.get("success"):
                acc = res.get('account') or u
                def _set_ok():
                    try:
                        self.query_one("#label-cas-submit-status", Label).update(f"[bold green]✔ 办事大厅认证成功！已绑定一卡通卡号: {acc}[/bold green]")
                        self._update_status_bar()
                        self.switch_to_view("water")
                        self.action_fetch_water_data()
                    except Exception:
                        pass
                self.call_from_thread(_set_ok)
                self.notify(f"✔ 网上办事大厅认证成功！一卡通卡号: {acc}，正在为你展开浴室大盘...", title="认证成功", severity="information")
            else:
                err = res.get('msg', '未知原因')
                def _set_fail():
                    try:
                        self.query_one("#label-cas-submit-status", Label).update(f"[bold red]❌ 统一认证失败: {err}[/bold red]")
                    except Exception:
                        pass
                self.call_from_thread(_set_fail)
                self.notify(f"办事大厅登录未通过: {err}", title="认证失败", severity="error")
        except Exception as e:
            def _set_exc():
                try:
                    self.query_one("#label-cas-submit-status", Label).update(f"[bold red]❌ 认证请求异常: {e}[/bold red]")
                except Exception:
                    pass
            self.call_from_thread(_set_exc)
            self.notify(f"认证请求异常: {e}", title="认证异常", severity="error")

    # ==================== 任务 C: 办事大厅扫码登录 Workers ====================

    @work(thread=True)
    def action_start_qr_login_flow(self) -> None:
        """后台拉取办事大厅二维码并在终端渲染，启动异步轮询"""
        self.notify("正在申请网上办事大厅登录二维码...", title="扫码登录")
        def _set_loading():
            self.query_one("#qr-code-display", Label).update("⏳ 正在获取二维码...")
            self.query_one("#qr-status-display", Label).update("[cyan]正在连接认证中心...[/cyan]")
        self.call_from_thread(_set_loading)

        try:
            session = self.water_svc.start_qr_login()
            uuid = session["uuid"]
            qr_ascii = session["qr_ascii"]

            def _show_qr():
                self.query_one("#qr-code-display", Label).update(qr_ascii)
                self.query_one("#qr-status-display", Label).update("[yellow]📱 等待手机扫码中 (微信/今日校园/哈理工移动端)...[/yellow]")
            self.call_from_thread(_show_qr)
        except Exception as e:
            def _show_err():
                self.query_one("#qr-code-display", Label).update("❌ 二维码加载失败")
                self.query_one("#qr-status-display", Label).update(f"[red]获取失败: {e}[/red]")
            self.call_from_thread(_show_err)
            self.notify(f"获取二维码失败: {e}", severity="error")
            return

        import time
        start_t = time.time()
        while time.time() - start_t < 120:
            if self.active_view != "qr":
                return
            try:
                st = self.water_svc.check_qr_status(uuid)
                if st == "2":
                    def _update_scanned():
                        self.query_one("#qr-status-display", Label).update("[bold yellow]📱 手机已扫描！请在手机上点击「确认登录」...[/bold yellow]")
                    self.call_from_thread(_update_scanned)
                elif st == "1":
                    def _update_finishing():
                        self.query_one("#qr-status-display", Label).update("[bold green]✔ 手机端已确认授权！正在换取一卡通与水控凭据...[/bold green]")
                    self.call_from_thread(_update_finishing)
                    res = self.water_svc.finish_qr_login(uuid)
                    if res.get("success"):
                        def _update_success():
                            acc = res.get("account", "")
                            self.query_one("#qr-status-display", Label).update(f"[bold green]🎉 扫码登录成功！已绑定一卡通卡号: {acc}[/bold green]")
                            self._update_status_bar()
                        self.call_from_thread(_update_success)
                        self.notify("🎉 扫码登录成功！水控凭据已自动同步，随时输入 water 秒约！", title="扫码登录成功", severity="information")
                    else:
                        def _update_fail():
                            err = res.get("msg", "未知错误")
                        self.query_one("#qr-status-display", Label).update(f"[red]换票失败: {err}[/red]")
                        self.call_from_thread(_update_fail)
                    return
                elif st == "3":
                    def _update_expired():
                        self.query_one("#qr-status-display", Label).update("[red]二维码已失效，请点击上方「重新生成二维码」重试[/red]")
                    self.call_from_thread(_update_expired)
                    return
            except Exception:
                pass
            time.sleep(1.5)

        def _update_timeout():
            self.query_one("#qr-status-display", Label).update("[yellow]扫码已超时，请点击上方「重新生成二维码」刷新[/yellow]")
        self.call_from_thread(_update_timeout)

    # ==================== 按钮与事件路由 ====================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-sidebar-refresh":
            self.action_load_sidebar_news()
            self.notify("正在刷新右侧校园动态...", severity="information")
        elif btn_id in (
            "btn-back-home-1",
            "btn-back-home-2",
            "btn-back-home-3",
            "btn-back-home-4",
            "btn-back-home-5",
            "btn-back-home-6",
            "btn-back-home-7",
            "btn-back-home-8",
            "btn-back-home-9",
            "btn-back-home-10",
            "btn-back-home-11",
        ):
            self.action_show_home()
        elif btn_id == "btn-water-refresh-deck":
            self.action_fetch_water_data()
        elif btn_id == "btn-water-book-deck":
            self.action_book_water_from_deck()
        elif btn_id == "btn-schedule-refresh-deck":
            self.action_fetch_schedule_data()
        elif btn_id == "btn-news-refresh-deck":
            self.action_fetch_news_data()
        elif btn_id == "btn-score-refresh-deck":
            self.action_fetch_score_data()
        elif btn_id == "btn-article-back-news":
            self.switch_to_view("news")
        elif btn_id == "btn-qr-refresh-deck":
            self.action_start_qr_login_flow()
        elif btn_id == "btn-cas-submit-deck":
            u_val = self.query_one("#input-cas-user", Input).value.strip()
            p_val = self.query_one("#input-cas-pass", Input).value.strip()
            if not u_val or not p_val:
                self.notify("请输入办事大厅学号和统一身份认证密码", title="信息不全", severity="warning")
            else:
                self.action_submit_cas_password_login(u_val, p_val)
        elif btn_id == "btn-exam-refresh-deck":
            self.action_fetch_exam_data()
        elif btn_id == "btn-card-refresh-deck":
            self.action_fetch_card_data()
        elif btn_id == "btn-plan-refresh-deck":
            self.action_fetch_plan_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "table-water-deck":
            self.action_book_water_from_deck()
        elif event.data_table.id == "table-news-deck":
            row_key = event.row_key.value
            if row_key and row_key.isdigit():
                self.action_open_article(row_key)

    def action_refresh_active(self) -> None:
        """刷新当前激活的视图"""
        if self.active_view == "water":
            self.action_fetch_water_data()
        elif self.active_view == "news":
            self.action_fetch_news_data()
        elif self.active_view == "schedule":
            self.action_fetch_schedule_data()
        elif self.active_view == "score":
            self.action_fetch_score_data()
        self.action_load_sidebar_news()
        self._update_status_bar()
        self.notify("当前数据已刷新", severity="information")


def run_tui():
    """TUI 独立启动入口"""
    app = HrbustTuiApp()
    app.run()


if __name__ == "__main__":
    run_tui()
