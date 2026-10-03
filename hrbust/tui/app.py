"""
HRBUST TUI Application
哈尔滨理工大学数字化校园全栈交互式终端大盘 (Textual)
"""

import sys
import os
from typing import List, Dict, Any, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    TabbedContent,
    TabPane,
    DataTable,
    Button,
    Label,
    Static,
    Input,
    Select,
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


class HrbustTuiApp(App):
    """哈理工数字化校园 TUI 主应用"""

    TITLE = "HRBUST Toolkit · 数字化校园终端中枢"
    SUB_TITLE = "v1.1.0 · TUI Edition"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "退出", show=True),
        Binding("r", "refresh_active", "刷新当前页", show=True),
        Binding("1", "switch_tab('tab-water')", "水控大盘", show=True),
        Binding("2", "switch_tab('tab-room')", "自习教室", show=True),
        Binding("3", "switch_tab('tab-schedule')", "课表大盘", show=True),
        Binding("4", "switch_tab('tab-news')", "教务公告", show=True),
        Binding("5", "switch_tab('tab-status')", "安全状态", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.water_engine = WaterEngine()
        self.water_svc = WaterService(self.water_engine)
        self.news_svc = NewsService()
        self.jwzx_engine: Optional[JwzxEngine] = None
        self.current_water_status: List[Dict[str, Any]] = []
        self.current_rooms: List[Dict[str, Any]] = []
        self.news_column = NewsService.COL_NOTICE
        self.news_page = 1
        self.media_filter = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # 顶部全局状态指示条
        with Horizontal(classes="status-bar"):
            yield Static("🌐 [bold]校园网直连:[/bold] 正在探测...", id="net-status-label")
            yield Static("  |  👤 [bold]当前学号:[/bold] 未绑定", id="user-status-label")
            yield Static("  |  💧 [bold]水控凭据:[/bold] 未就绪", id="water-status-label")

        with TabbedContent(id="main-tabs"):
            # ========== Tab 1: 浴室水控大盘 ==========
            with TabPane("🚿 浴室水控大盘", id="tab-water"):
                with Horizontal(classes="toolbar-row"):
                    yield Button("⚡ 预约选中机位", id="btn-water-book", variant="primary")
                    yield Button("🔄 刷新大盘", id="btn-water-refresh")
                    yield Label("  💡 提示: 上下键选中场所后按 Enter 或点击预约", classes="tip-text")

                yield DataTable(id="table-water")

                # 出码结果卡片
                with Vertical(id="water-voucher-box", classes="voucher-card"):
                    yield Label("🎉 [bold green]出水预约码就绪[/bold green]", id="voucher-title")
                    yield Static("[请选择场所进行预约]", id="voucher-detail")

            # ========== Tab 2: 空闲与多媒体教室 ==========
            with TabPane("🏫 空闲自习室", id="tab-room"):
                with Horizontal(classes="toolbar-row"):
                    b_options = [
                        (v["name"], k) for k, v in RoomService.BUILDINGS.items()
                    ]
                    yield Select(b_options, prompt="选择教学楼", value="南一", id="select-building")
                    yield Button("仅看多媒体/机房 [关]", id="btn-toggle-media")
                    yield Input(placeholder="🔍 快速筛选教室名称/房号...", id="input-room-filter")
                    yield Button("🔄 检索教室", id="btn-room-refresh")

                yield DataTable(id="table-room")

            # ========== Tab 3: 学业与今日课表 ==========
            with TabPane("📅 学业与大课表", id="tab-schedule"):
                with Horizontal(classes="toolbar-row"):
                    yield Button("🔄 同步本学期课表", id="btn-schedule-refresh", variant="primary")
                    yield Label("  📚 自动对接教务在线 (jwzx) 获取选课与教室排布", classes="tip-text")

                yield DataTable(id="table-schedule")

            # ========== Tab 4: 教务公告与新闻 ==========
            with TabPane("📢 教务公告与新闻", id="tab-news"):
                with Horizontal(classes="toolbar-row"):
                    yield Button("📜 教务公告", id="btn-news-col-notice", variant="primary")
                    yield Button("📰 教学新闻", id="btn-news-col-news")
                    yield Button("⬅️ 上一页", id="btn-news-prev")
                    yield Button("➡️ 下一页", id="btn-news-next")
                    yield Label("  第 1 页", id="label-news-page")

                yield DataTable(id="table-news")

                with Vertical(classes="detail-preview"):
                    yield Label("📌 [bold cyan]公告详情预览[/bold cyan]")
                    yield Static("上下键切换文章列表，按 Enter 查看详情或复制链接", id="news-preview-text")

            # ========== Tab 5: 安全保险箱与状态 ==========
            with TabPane("🛡️ 安全凭据与状态", id="tab-status"):
                with VerticalScroll():
                    with Vertical(classes="panel-box"):
                        yield Label("🔑 [bold cyan]教务在线 (JWZX) 登录凭据[/bold cyan]", classes="panel-title")
                        yield Input(placeholder="请输入教务在线学号 (如 21010101xx)", id="input-auth-user")
                        yield Input(placeholder="请输入教务在线密码", password=True, id="input-auth-pass")
                        with Horizontal(classes="toolbar-row"):
                            yield Button("💾 保存教务凭据", id="btn-save-auth", variant="primary")

                    with Vertical(classes="panel-box"):
                        yield Label("💧 [bold cyan]一卡通水控 Token 凭据[/bold cyan]", classes="panel-title")
                        yield Input(placeholder="请输入抓包获取的控水 Token (留空则使用默认配置)", password=True, id="input-auth-water")
                        with Horizontal(classes="toolbar-row"):
                            yield Button("💾 保存水控 Token", id="btn-save-water", variant="primary")

                    with Vertical(classes="panel-box"):
                        yield Label("⚠️ [bold red]危险操作[/bold red]", classes="panel-title")
                        yield Label("登出将彻底清空本地绑定的 AES-256 安全密文保险箱凭据。")
                        with Horizontal(classes="toolbar-row"):
                            yield Button("🚪 退出登录并清空凭据", id="btn-logout-all", variant="error")

        yield Footer()

    def on_mount(self) -> None:
        """应用初始化挂载"""
        self._init_tables()
        self._update_status_bar()
        # 默认加载水控大盘和公告数据
        self.action_refresh_water()
        self.action_refresh_news()

    def _init_tables(self) -> None:
        """初始化表格表头"""
        # 水控表
        t_water = self.query_one("#table-water", DataTable)
        t_water.cursor_type = "row"
        t_water.add_columns("编号", "场所名称", "总机位数", "当前空闲率", "拥挤度评级")

        # 教室表
        t_room = self.query_one("#table-room", DataTable)
        t_room.cursor_type = "row"
        t_room.add_columns("序号", "教室编号 / 房间名称", "设备类别", "所属教学楼")

        # 课表
        t_sched = self.query_one("#table-schedule", DataTable)
        t_sched.cursor_type = "row"
        t_sched.add_columns("序号", "课程名称", "任课教师", "上课教室", "课程详情与节次")

        # 新闻公告表
        t_news = self.query_one("#table-news", DataTable)
        t_news.cursor_type = "row"
        t_news.add_columns("发布日期", "分类", "公告 / 新闻标题", "文章 ID")

    def _update_status_bar(self) -> None:
        """更新顶部状态栏"""
        u, _ = get_credentials()
        w_info, w_tok = get_water_token()
        
        # 检查网络
        is_campus = check_campus_network()
        net_text = "🟢 [bold green]已直连校园网[/bold green]" if is_campus else "🟡 [bold yellow]外部网络/代理[/bold yellow]"
        self.query_one("#net-status-label", Static).update(f"🌐 [bold]校园网:[/bold] {net_text}")

        user_text = f"[bold green]{u}[/bold green]" if u else "[dim]未绑定[/dim]"
        self.query_one("#user-status-label", Static).update(f"  |  👤 [bold]学号:[/bold] {user_text}")

        water_text = "[bold green]已就绪[/bold green]" if w_tok else "[dim]未配置[/dim]"
        self.query_one("#water-status-label", Static).update(f"  |  💧 [bold]水控凭据:[/bold] {water_text}")

        if u:
            self.query_one("#input-auth-user", Input).value = u

    # ==================== 业务逻辑与工作线程 (Workers) ====================

    @work(thread=True)
    def action_refresh_water(self) -> None:
        """后台拉取水控实时大盘"""
        self.notify("正在拉取浴室与热水大盘...", title="水控系统", severity="information")
        try:
            u, _ = get_credentials()
            w_info, w_tok = get_water_token()
            token = w_tok or "default_guest_token"

            account = u or "2101010101"
            raw_info = w_info or self.water_engine.aes_encrypt(account, account)
            status_list = self.water_svc.get_dashboard(raw_info, token)
            self.current_water_status = status_list

            self.call_from_thread(self._render_water_table, status_list)
            self.notify("浴室与热水大盘已更新", title="水控系统", severity="information")
        except Exception as e:
            self.notify(f"获取水控数据异常: {e}", title="水控系统", severity="warning")

    def _render_water_table(self, items: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-water", DataTable)
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
    def action_book_selected_water(self) -> None:
        """一键预约选中的浴室机位"""
        table = self.query_one("#table-water", DataTable)
        if table.row_count == 0:
            self.notify("大盘无数据，请先刷新", severity="warning")
            return

        cursor_row = table.cursor_row
        if cursor_row < 0 or cursor_row >= len(self.current_water_status):
            target = self.current_water_status[0]
        else:
            target = self.current_water_status[cursor_row]

        u, _ = get_credentials()
        _, w_tok = get_water_token()
        account = u or "2101010101"
        token = w_tok or "default_token"

        self.notify(f"正在为学号 {account} 申请 {target['name']} 预约码...", title="水控预约")
        try:
            res = self.water_svc.book_bath(target["class_no"], account, account, token)
            ret_no = res.get("RetNo", res.get("ret_no", -1))
            if ret_no == 0:
                code = res.get("BookCode") or res.get("book_code") or "8888"
                self.call_from_thread(self._render_voucher, target["name"], code)
                self.notify(f"预约成功！出水码: {code}", title="预约成功", severity="information")
            else:
                msg = res.get("RetDsp") or res.get("msg") or "预约失败"
                self.notify(f"预约失败: {msg}", title="预约回执", severity="error")
        except Exception as e:
            self.notify(f"预约请求异常: {e}", title="预约异常", severity="error")

    def _render_voucher(self, place_name: str, code: str) -> None:
        self.query_one("#voucher-title", Label).update(f"🎉 [bold green]{place_name} 预约成功[/bold green]")
        self.query_one("#voucher-detail", Static).update(
            f"出水预约码: [bold yellow on black]  {code}  [/bold yellow on black]  (请在 60 分钟内到浴室机位输入)"
        )

    @work(thread=True)
    def action_refresh_rooms(self) -> None:
        """拉取教学楼教室资源"""
        select = self.query_one("#select-building", Select)
        b_key = select.value if select.value != Select.BLANK else "南一"
        b_info = RoomService.BUILDINGS.get(str(b_key), RoomService.BUILDINGS["南一"])

        self.notify(f"正在检索 {b_info['name']} 教室资源池...", title="自习教室")
        try:
            # 确保已登录教务系统
            if not self.jwzx_engine:
                u, p = get_credentials()
                if not u or not p:
                    self.notify("请先在「安全状态」页配置教务系统学号与密码", title="需要登录", severity="warning")
                    return
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败，请检查密码", severity="error")
                    return

            room_svc = RoomService(self.jwzx_engine)
            rooms = room_svc.get_building_rooms(b_info["aid"], b_info["id"])
            self.current_rooms = rooms

            filter_text = self.query_one("#input-room-filter", Input).value.strip()
            self.call_from_thread(self._render_room_table, rooms, filter_text, self.media_filter, b_info["name"])
            self.notify(f"检索到 {len(rooms)} 间教室资源", title="自习教室", severity="information")
        except Exception as e:
            self.notify(f"拉取教室数据失败: {e}", title="自习教室", severity="error")

    def _render_room_table(self, rooms: List[Dict[str, Any]], filter_text: str, media_only: bool, b_name: str) -> None:
        table = self.query_one("#table-room", DataTable)
        table.clear()
        count = 0
        for r in rooms:
            if media_only and not r["is_media"]:
                continue
            if filter_text and filter_text.lower() not in r["name"].lower():
                continue
            count += 1
            tag = "[bold cyan][多媒体/实验][/bold cyan]" if r["is_media"] else "[dim][普通教室][/dim]"
            table.add_row(str(count), r["name"], tag, b_name)

    @work(thread=True)
    def action_refresh_schedule(self) -> None:
        """拉取个人大课表"""
        u, p = get_credentials()
        if not u or not p:
            self.notify("请先在「安全状态」页配置教务系统学号与密码", title="需要登录", severity="warning")
            return

        self.notify("正在登录教务在线拉取大课表...", title="学业课表")
        try:
            if not self.jwzx_engine:
                self.jwzx_engine = JwzxEngine()
                if not self.jwzx_engine.login(u, p):
                    self.notify("教务在线自动打码登录失败", severity="error")
                    return

            svc = ScheduleService(self.jwzx_engine)
            courses = svc.get_timetable()
            self.call_from_thread(self._render_schedule_table, courses)
            self.notify(f"课表同步成功，共计 {len(courses)} 门课程", title="学业课表", severity="information")
        except Exception as e:
            self.notify(f"拉取课表失败: {e}", title="学业课表", severity="error")

    def _render_schedule_table(self, courses: List[Dict[str, Any]]) -> None:
        table = self.query_one("#table-schedule", DataTable)
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
    def action_refresh_news(self) -> None:
        """免登录拉取教务公告/教学新闻"""
        col_name = "教务公告" if self.news_column == NewsService.COL_NOTICE else "教学新闻"
        self.notify(f"正在拉取 {col_name} (第 {self.news_page} 页)...", title="教务资讯")
        try:
            articles = self.news_svc.get_articles(self.news_column, page=self.news_page)
            self.call_from_thread(self._render_news_table, articles, col_name)
        except Exception as e:
            self.notify(f"拉取教务资讯失败: {e}", title="教务资讯", severity="error")

    def _render_news_table(self, articles: List[Dict[str, Any]], col_name: str) -> None:
        table = self.query_one("#table-news", DataTable)
        table.clear()
        for a in articles:
            table.add_row(
                a.get("date", ""),
                f"[bold cyan]{col_name}[/bold cyan]",
                a.get("title", ""),
                str(a.get("id", "")),
                key=a.get("url", ""),
            )
        self.query_one("#label-news-page", Label).update(f"  第 {self.news_page} 页")

    # ==================== 界面事件处理 (Events) ====================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-water-refresh":
            self.action_refresh_water()
        elif btn_id == "btn-water-book":
            self.action_book_selected_water()
        elif btn_id == "btn-room-refresh":
            self.action_refresh_rooms()
        elif btn_id == "btn-toggle-media":
            self.media_filter = not self.media_filter
            event.button.label = f"仅看多媒体/机房 [{'开' if self.media_filter else '关'}]"
            # 重新过滤当前列表
            select = self.query_one("#select-building", Select)
            b_key = select.value if select.value != Select.BLANK else "南一"
            b_name = RoomService.BUILDINGS.get(str(b_key), {}).get("name", "南区一号楼")
            filter_text = self.query_one("#input-room-filter", Input).value.strip()
            self._render_room_table(self.current_rooms, filter_text, self.media_filter, b_name)
        elif btn_id == "btn-schedule-refresh":
            self.action_refresh_schedule()
        elif btn_id == "btn-news-col-notice":
            self.news_column = NewsService.COL_NOTICE
            self.news_page = 1
            self.action_refresh_news()
        elif btn_id == "btn-news-col-news":
            self.news_column = NewsService.COL_NEWS
            self.news_page = 1
            self.action_refresh_news()
        elif btn_id == "btn-news-prev":
            if self.news_page > 1:
                self.news_page -= 1
                self.action_refresh_news()
        elif btn_id == "btn-news-next":
            self.news_page += 1
            self.action_refresh_news()
        elif btn_id == "btn-save-auth":
            u = self.query_one("#input-auth-user", Input).value.strip()
            p = self.query_one("#input-auth-pass", Input).value.strip()
            if u and p:
                set_credentials(u, p)
                self.jwzx_engine = None  # 重置登录会话
                self._update_status_bar()
                self.notify("教务在线学号与密码已存入安全保险箱", title="保存成功", severity="information")
            else:
                self.notify("学号与密码均不能为空", severity="warning")
        elif btn_id == "btn-save-water":
            tok = self.query_one("#input-auth-water", Input).value.strip()
            if tok:
                u, _ = get_credentials()
                account = u or "2101010101"
                raw_info = self.water_engine.aes_encrypt(account, account)
                set_water_token(raw_info, tok)
                self._update_status_bar()
                self.notify("控水 Token 凭据已成功保存", title="保存成功", severity="information")
        elif btn_id == "btn-logout-all":
            clear_all_credentials()
            self.jwzx_engine = None
            self._update_status_bar()
            self.notify("已彻底清空本地安全凭据保险箱", title="已登出", severity="warning")

    def on_input_changed(self, event: Input.Changed) -> None:
        """自习室搜索框动态过滤"""
        if event.input.id == "input-room-filter":
            select = self.query_one("#select-building", Select)
            b_key = select.value if select.value != Select.BLANK else "南一"
            b_name = RoomService.BUILDINGS.get(str(b_key), {}).get("name", "南区一号楼")
            self._render_room_table(self.current_rooms, event.value.strip(), self.media_filter, b_name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """表格行选中"""
        if event.data_table.id == "table-water":
            # 按回车直接触发预约
            self.action_book_selected_water()
        elif event.data_table.id == "table-news":
            # 预览文章
            row_data = event.data_table.get_row(event.row_key)
            if row_data:
                self.query_one("#news-preview-text", Static).update(
                    f"【{row_data[1]}】 [bold]{row_data[2]}[/bold]\\n"
                    f"发布日期: {row_data[0]}  |  在线链接: {event.row_key.value}"
                )

    def action_refresh_active(self) -> None:
        """全局快捷键 R 刷新当前选项卡"""
        tabs = self.query_one("#main-tabs", TabbedContent)
        active_tab = tabs.active
        if active_tab == "tab-water":
            self.action_refresh_water()
        elif active_tab == "tab-room":
            self.action_refresh_rooms()
        elif active_tab == "tab-schedule":
            self.action_refresh_schedule()
        elif active_tab == "tab-news":
            self.action_refresh_news()
        elif active_tab == "tab-status":
            self._update_status_bar()
            self.notify("系统状态已重新探测", severity="information")

    def action_switch_tab(self, tab_id: str) -> None:
        """快捷键 1-5 快速切换 Tab"""
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = tab_id


def run_tui():
    """TUI 独立启动入口"""
    app = HrbustTuiApp()
    app.run()


if __name__ == "__main__":
    run_tui()
