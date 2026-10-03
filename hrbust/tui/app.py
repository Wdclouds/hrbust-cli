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
        Binding("escape", "show_home", "返回主页", show=True),
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
                            yield Label("• 📢 教务公告新闻: 输入 [bold yellow]news[/bold yellow] 或 [bold yellow]notice[/bold yellow] 查看官方通告", classes="guide-item")
                            yield Label("• 🛡️ 账号凭据保险箱: 输入 [bold yellow]status[/bold yellow] 配置密码 / 输入 [bold yellow]logout[/bold yellow] 登出", classes="guide-item")
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
                            yield Label("🛡️ [bold cyan]HRBUST 凭据与安全保险箱[/bold cyan]", classes="view-header-title")
                            yield Button("🏠 返回主页 (Esc)", id="btn-back-home-5")
                        with VerticalScroll():
                            with Vertical(classes="panel-box"):
                                yield Label("🔑 [bold cyan]教务在线 (JWZX) 凭据[/bold cyan]")
                                yield Label("当前绑定学号: [dim]探测中...[/dim]", id="status-deck-user")
                            with Vertical(classes="panel-box"):
                                yield Label("💧 [bold cyan]一卡通水控 Token 凭据[/bold cyan]")
                                yield Label("水控凭据状态: [dim]探测中...[/dim]", id="status-deck-water")

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

    def _update_status_bar(self) -> None:
        """刷新顶部状态指示条"""
        u, _ = get_credentials()
        _, w_tok = get_water_token()
        is_campus = check_campus_network()
        net_text = "🟢 [bold green]已直连校园网[/bold green]" if is_campus else "🟡 [bold yellow]外部网络/代理[/bold yellow]"
        self.query_one("#net-status-label", Static).update(f"🌐 [bold]校园网:[/bold] {net_text}")

        user_text = f"[bold green]{u}[/bold green]" if u else "[dim]未绑定[/dim]"
        self.query_one("#user-status-label", Static).update(f"  |  👤 [bold]学号:[/bold] {user_text}")

        water_text = "[bold green]已就绪[/bold green]" if w_tok else "[dim]未配置[/dim]"
        self.query_one("#water-status-label", Static).update(f"  |  💧 [bold]水控凭据:[/bold] {water_text}")

        self.query_one("#status-deck-user", Label).update(f"当前绑定学号: {user_text}")
        self.query_one("#status-deck-water", Label).update(f"水控凭据状态: {water_text}")

    def switch_to_view(self, target: str) -> None:
        """单页面多视图无缝流转"""
        views = ["hero", "water", "room", "schedule", "news", "status"]
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
            self.call_from_thread(
                lambda: self.query_one("#news-loading-hint", Label).update(f"[red]动态拉取失败: {e}[/red]")
            )

    def _render_sidebar_news(self, items: List[Dict[str, Any]]) -> None:
        container = self.query_one("#news-scroll-container", VerticalScroll)
        container.remove_children()

        if not items:
            container.mount(Label("[dim]今日暂无最新公告发布[/dim]"))
            return

        for item in items[:12]:
            card = Vertical(classes="news-card")
            card.mount(Label(f"[{item.get('type', '通告')}] · {item.get('date', '今日')}", classes="news-date"))
            card.mount(Label(item.get("title", ""), classes="news-title"))
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
        elif cmd in ("status", "auth", "login"):
            self._update_status_bar()
            self.switch_to_view("status")
        elif cmd in ("help", "?"):
            self.action_show_home()
            self.notify("快捷命令: water | room 南一 | today | news | status | home | exit", title="命令帮助")
        else:
            self.notify(f"未识别指令 '{cmd}'，请输入 help 查看可用命令", title="命令提示", severity="warning")

    # ==================== 数据拉取与渲染 Workers ====================

    @work(thread=True)
    def action_fetch_water_data(self) -> None:
        """后台拉取水控数据并渲染"""
        try:
            u, _ = get_credentials()
            w_info, w_tok = get_water_token()
            token = w_tok or "default_guest_token"
            account = u or "2101010101"
            raw_info = w_info or self.water_engine.aes_encrypt(account, account)
            status_list = self.water_svc.get_dashboard(raw_info, token)
            self.current_water_status = status_list
            self.call_from_thread(self._populate_water_table, status_list)
        except Exception as e:
            self.notify(f"水控大盘获取异常: {e}", title="水控系统", severity="warning")

    def _populate_water_table(self, items: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-water-deck", DataTable)
        table.clear()
        for idx, item in enumerate(items, 1):
            free_rate = item.get("free_rate", 0.0)
            if free_rate > 70:
                rate_text = f"[green]{free_rate:.1f}%[/green]"
                status_text = "[bold green]极佳 · 无需排队[/bold green]"
            elif free_rate > 30:
                rate_text = f"[yellow]{free_rate:.1f}%[/yellow]"
                status_text = "[bold yellow]正常 · 少量空位[/bold yellow]"
            else:
                rate_text = f"[red]{free_rate:.1f}%[/red]"
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
        """从主命令台一键预约出水码"""
        table = self.query_one("#table-water-deck", DataTable)
        if table.row_count == 0:
            self.notify("大盘暂无数据，请先刷新", severity="warning")
            return

        cursor_row = table.cursor_row
        target = self.current_water_status[cursor_row] if 0 <= cursor_row < len(self.current_water_status) else self.current_water_status[0]
        u, _ = get_credentials()
        _, w_tok = get_water_token()
        account = u or "2101010101"
        token = w_tok or "default_token"

        self.notify(f"正在申请 {target['name']} 出水预约码...", title="水控预约")
        try:
            res = self.water_svc.book_bath(target["class_no"], account, account, token)
            ret_no = res.get("RetNo", res.get("ret_no", -1))
            if ret_no == 0:
                code = res.get("BookCode") or res.get("book_code") or "8888"
                self.call_from_thread(self._render_deck_voucher, target["name"], code)
                self.notify(f"预约成功！出水码: {code}", title="出码成功", severity="information")
            else:
                msg = res.get("RetDsp") or res.get("msg") or "预约失败"
                self.notify(f"预约失败: {msg}", title="预约回执", severity="error")
        except Exception as e:
            self.notify(f"预约异常: {e}", severity="error")

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
        self.notify(f"正在检索 {b_info['name']} 教室资源池...", title="自习教室")
        try:
            if not self.jwzx_engine:
                u, p = get_credentials()
                if not u or not p:
                    self.notify("请在 status 命令中配置教务账号密码", severity="warning")
                    return
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    return

            room_svc = RoomService(self.jwzx_engine)
            rooms = room_svc.get_building_rooms(b_info["aid"], b_info["id"])
            if media_only:
                rooms = [r for r in rooms if r.get("is_media")]

            self.call_from_thread(self._populate_room_table, rooms, b_info["name"])
            self.notify(f"检索到 {len(rooms)} 间教室资源", title="自习教室", severity="information")
        except Exception as e:
            self.notify(f"检索教室失败: {e}", severity="error")

    def _populate_room_table(self, rooms: List[Dict[str, Any]], b_name: str) -> None:
        table = self.query_one("#table-room-deck", DataTable)
        self.query_one("#label-room-title", Label).update(f"🏫 [bold cyan]{b_name} 教室资源池 (共 {len(rooms)} 间)[/bold cyan]")
        table.clear()
        for idx, r in enumerate(rooms, 1):
            tag = "[bold cyan][多媒体/实验][/bold cyan]" if r.get("is_media") else "[dim][普通教室][/dim]"
            table.add_row(str(idx), r.get("name", ""), tag, b_name)

    @work(thread=True)
    def action_fetch_schedule_data(self) -> None:
        """后台拉取课表数据"""
        u, p = get_credentials()
        if not u or not p:
            self.notify("未绑定教务账号，请输入 status 进行配置", severity="warning")
            return

        self.notify("正在登录教务在线同步大课表...", title="学业课表")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动登录失败", severity="error")
                    return

            svc = ScheduleService(self.jwzx_engine)
            courses = svc.get_timetable()
            self.call_from_thread(self._populate_schedule_table, courses)
            self.notify(f"课表同步完成，共计 {len(courses)} 门课程", title="学业课表", severity="information")
        except Exception as e:
            self.notify(f"课表拉取失败: {e}", severity="error")

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
            )

    # ==================== 按钮与事件路由 ====================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-sidebar-refresh":
            self.action_load_sidebar_news()
            self.notify("正在刷新右侧校园动态...", severity="information")
        elif btn_id in ("btn-back-home-1", "btn-back-home-2", "btn-back-home-3", "btn-back-home-4", "btn-back-home-5"):
            self.action_show_home()
        elif btn_id == "btn-water-refresh-deck":
            self.action_fetch_water_data()
        elif btn_id == "btn-water-book-deck":
            self.action_book_water_from_deck()
        elif btn_id == "btn-schedule-refresh-deck":
            self.action_fetch_schedule_data()
        elif btn_id == "btn-news-refresh-deck":
            self.action_fetch_news_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "table-water-deck":
            self.action_book_water_from_deck()

    def action_refresh_active(self) -> None:
        """刷新当前激活的视图"""
        if self.active_view == "water":
            self.action_fetch_water_data()
        elif self.active_view == "news":
            self.action_fetch_news_data()
        elif self.active_view == "schedule":
            self.action_fetch_schedule_data()
        self.action_load_sidebar_news()
        self._update_status_bar()
        self.notify("当前数据已刷新", severity="information")


def run_tui():
    """TUI 独立启动入口"""
    app = HrbustTuiApp()
    app.run()


if __name__ == "__main__":
    run_tui()
