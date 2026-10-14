"""
HRBUST Toolkit 主命令行入口
基于 Typer 与 Rich 实现的专业终端交互界面（严谨、纯净、无任何表情符号与颜文字）
"""

import sys
import typer
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.prompt import Prompt

from ..core.network import check_campus_network
from ..core.auth import get_credentials, set_credentials, get_water_token, set_water_token
from ..core.jwzx import JwzxEngine
from ..core.water import WaterEngine
from ..services.water_svc import WaterService
from ..services.room_svc import RoomService
from ..services.schedule_svc import ScheduleService
from ..services.news_svc import NewsService

app = typer.Typer(
    name="hrbust",
    help="哈尔滨理工大学（HRBUST）数字化校园全栈 CLI 工具箱",
    add_completion=False,
)
console = Console()

def _ensure_network():
    """安全前哨拦截：确认内网环境与代理直连"""
    if not check_campus_network():
        console.print("[bold red][错误] 未检测到哈理工校园内网直连环境。[/bold red]")
        console.print("[dim]请确认当前设备已连接校园网 Wi-Fi (HRBUST-WLAN) 或宿舍网线。[/dim]")
        raise typer.Exit(code=1)

def _ensure_auth() -> JwzxEngine:
    """确认教务系统登录态"""
    _ensure_network()
    username, password = get_credentials()
    if not username or not password:
        console.print("[bold yellow][提示] 首次使用，请输入教务系统账号密码：[/bold yellow]")
        username = Prompt.ask("学号")
        password = Prompt.ask("密码", password=True)
        set_credentials(username, password)
    
    engine = JwzxEngine()
    with console.status("[cyan]正在进行打码验证并登录教务系统...[/cyan]"):
        success = engine.login(username, password)
    if not success:
        console.print("[bold red][错误] 登录失败：学号或密码错误，或验证码识别重试耗尽。[/bold red]")
        raise typer.Exit(code=1)
    return engine

# ==================== 1. 浴室水控 (water) ====================
@app.command(name="water")
def water():
    """浴室与水控：实时机位空闲大盘与交互式数字秒约"""
    _ensure_network()
    username, password = get_credentials()
    water_eng = WaterEngine()
    svc = WaterService(water_eng)

    raw_info, token = get_water_token()
    if not token:
        # 方案 1: 如果已配置学号与密码，优先尝试 CAS 全自动静默换票 (零抓包)
        if username and password:
            with console.status("[cyan]正在通过学校统一身份认证 (CAS) 全自动激活水控凭据...[/cyan]"):
                auto_res = svc.auto_auth_and_sync(username, password)
            if auto_res.get("success"):
                console.print("[bold green]✔ 已通过统一身份认证中心全自动激活水控！(免抓包)[/bold green]")
                raw_info, token = get_water_token()
            else:
                console.print(f"[dim]自动激活未完成 ({auto_res.get('msg')})，转入手动模式[/dim]")

    if not token:
        token = Prompt.ask("[bold yellow]请输入控水系统 Token[/bold yellow]")
        set_water_token(token)

    if not username:
        username = Prompt.ask("请输入学号")

    with console.status("[cyan]正在获取浴场实时空闲大盘...[/cyan]"):
        try:
            info_b64 = water_eng.aes_encrypt(username, username)
            status_list = svc.get_dashboard(info_b64, token)
        except Exception as e:
            console.print(f"[bold red][错误] 获取浴场状态异常: {e}[/bold red]")
            raise typer.Exit(code=1)

    table = Table(title="哈理工浴室与热水实时大盘", border_style="cyan")
    table.add_column("编号", justify="center", style="bold yellow")
    table.add_column("场所名称", style="bold white")
    table.add_column("总机位", justify="center")
    table.add_column("空闲率", justify="center")
    table.add_column("状态建议", justify="center")

    mapping = {}
    for idx, item in enumerate(status_list, 1):
        mapping[str(idx)] = item
        free_rate = item["free_rate"]
        # 兼容百分比数值 (85.48) 与小数 (0.8548)
        rate_pct = free_rate if free_rate > 1.0 else free_rate * 100.0
        advice = "[green]极佳无需排队[/green]" if rate_pct > 70 else ("[yellow]正常[/yellow]" if rate_pct > 30 else "[red]拥挤爆满[/red]")
        table.add_row(
            str(idx),
            item["name"],
            f"{item['total_positions']} 台",
            f"{rate_pct:.1f}%",
            advice
        )

    console.print(table)
    console.print("[dim][0] 仅查看大盘，直接退出[/dim]")
    choice = Prompt.ask("请选择你要预约的场所编号 [1-5]", default="0")
    if choice == "0" or choice not in mapping:
        console.print("[cyan]已退出。[/cyan]")
        return

    target = mapping[choice]
    with console.status(f"[cyan]正在为学号 {username} 申请 {target['name']} 预约码...[/cyan]"):
        res = svc.book_bath(target["class_no"], username, username, token)

    is_success = res.get("success") or res.get("RetNo") == 0 or res.get("ret_no") == 0
    book_code = res.get("book_code") or res.get("BookCode")
    if is_success:
        console.print(Panel(
            f"[bold green]预约成功[/bold green]\n\n"
            f"场所: [bold]{target['name']}[/bold]\n"
            f"出水预约码: [bold yellow on black] {book_code} [/bold yellow on black]\n"
            f"提示: 请于 60 分钟内在浴室终端输入使用",
            title="洗浴出码凭证",
            border_style="green"
        ))
    else:
        err_msg = res.get("msg") or res.get("RetDsp") or "未知原因"
        console.print(f"[bold red][错误] 预约失败: {err_msg}[/bold red]")

# ==================== 2. 自习与教室 (room) ====================
@app.command(name="room")
def room(
    building: str = typer.Argument(None, help="教学楼简称（如 南一、南二、西新主楼）"),
    media: bool = typer.Option(False, "--media", "-m", help="仅筛选多媒体/实验教室")
):
    """自习神器：交互选择教学楼、检索当前空闲教室与多媒体设备打标"""
    engine = _ensure_auth()
    svc = RoomService(engine)

    target_key = building
    if not target_key:
        console.print("[bold cyan]请选择你要查询的教学楼：[/bold cyan]")
        buildings_list = list(svc.BUILDINGS.items())
        for i, (k, v) in enumerate(buildings_list, 1):
            console.print(f"[{i}] {v['name']} ({k})")
        b_choice = Prompt.ask("请输入教学楼序号", default="1")
        try:
            target_key = buildings_list[int(b_choice) - 1][0]
        except (ValueError, IndexError):
            target_key = "南一"

    b_info = svc.BUILDINGS.get(target_key, svc.BUILDINGS["南一"])
    with console.status(f"[cyan]正在检索 {b_info['name']} 的全部教室资源...[/cyan]"):
        rooms = svc.get_building_rooms(b_info["aid"], b_info["id"])

    if media:
        rooms = [r for r in rooms if r["is_media"]]

    table = Table(title=f"{b_info['name']} 教室资源池 (共 {len(rooms)} 间)", border_style="blue")
    table.add_column("教室编号/名称", style="bold white")
    table.add_column("设备属性", justify="center")

    for r in rooms:
        tag = "[bold cyan][多媒体/实验][/bold cyan]" if r["is_media"] else "[dim][普通教室][/dim]"
        table.add_row(r["name"], tag)

    console.print(table)

# ==================== 3. 今日课表 (today) ====================
@app.command(name="today")
def today():
    """查看今日课程安排与教室节次"""
    engine = _ensure_auth()
    svc = ScheduleService(engine)
    with console.status("[cyan]正在拉取本学期大课表...[/cyan]"):
        courses = svc.get_current_timetable()

    table = Table(title="本学期课程清单", border_style="green")
    table.add_column("课程名称", style="bold white")
    table.add_column("任课教师", justify="center")
    table.add_column("星期", justify="center")
    table.add_column("节次", justify="center")
    table.add_column("周次区间", justify="center")
    table.add_column("教室", style="bold yellow")

    for c in courses:
        table.add_row(
            c.get("name", ""),
            c.get("teacher", ""),
            c.get("day_of_week", ""),
            c.get("session", ""),
            c.get("weeks", ""),
            c.get("room", "")
        )
    console.print(table)

# ==================== 4. 教务公告 (notice) ====================
@app.command(name="notice")
def notice(page: int = typer.Option(1, "--page", "-p", help="页码")):
    """免登录查看教务在线官方通知（选课、考试、四六级）"""
    _ensure_network()
    svc = NewsService()
    with console.status(f"[cyan]正在拉取第 {page} 页教务公告...[/cyan]"):
        articles = svc.get_articles(svc.COL_NOTICE, page=page)

    table = Table(title=f"哈理工教务处公告 (第 {page} 页)", border_style="yellow")
    table.add_column("发布日期", justify="center", style="dim")
    table.add_column("公告标题", style="bold white")
    table.add_column("ID", justify="center", style="dim")

    for a in articles:
        table.add_row(a.get("date", ""), a.get("title", ""), str(a.get("id", "")))
    console.print(table)

# ==================== 5. 教学新闻 (news) ====================
@app.command(name="news")
def news(page: int = typer.Option(1, "--page", "-p", help="页码")):
    """免登录查看哈理工最新教学新闻与教改竞赛动态"""
    _ensure_network()
    svc = NewsService()
    with console.status(f"[cyan]正在拉取第 {page} 页教学新闻...[/cyan]"):
        articles = svc.get_articles(svc.COL_NEWS, page=page)

    table = Table(title=f"哈理工教学新闻 (第 {page} 页)", border_style="magenta")
    table.add_column("发布日期", justify="center", style="dim")
    table.add_column("新闻标题", style="bold white")
    table.add_column("ID", justify="center", style="dim")

    for a in articles:
        table.add_row(a.get("date", ""), a.get("title", ""), str(a.get("id", "")))
    console.print(table)

# ==================== 6. 每日简报 (daily) ====================
@app.command(name="daily")
def daily(
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 格式输出供机器人或定时脚本解析")
):
    """获取过去 24 小时内的增量公告与新闻早报"""
    _ensure_network()
    svc = NewsService()
    with console.status("[cyan]正在汇总每日最新资讯简报...[/cyan]"):
        brief = svc.get_daily_briefing()

    if json_mode:
        import json
        console.print(json.dumps(brief, ensure_ascii=False, indent=2))
        return

    table = Table(title="哈理工教务处每日最新资讯早报", border_style="cyan")
    table.add_column("分类", justify="center", style="bold yellow")
    table.add_column("日期", justify="center", style="dim")
    table.add_column("标题", style="bold white")

    for a in brief.get("notices", []):
        table.add_row("公告", a.get("date", ""), a.get("title", ""))
    for a in brief.get("news", []):
        table.add_row("新闻", a.get("date", ""), a.get("title", ""))

    console.print(table)

# ==================== 7. 通告全文阅读 (read) ====================
@app.command(name="read")
def read_article(
    article_id: str = typer.Argument(..., help="公告或新闻的文章 ID（如 5534、5532）"),
    col: int = typer.Option(354, "--col", "-c", help="栏目 ID (354:教务公告, 355:教学新闻)"),
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 格式输出")
):
    """免登录在线阅读校内通告与新闻正文，列出附件下载链接"""
    _ensure_network()
    svc = NewsService()
    with console.status(f"[cyan]正在获取文章 #{article_id} 正文详情...[/cyan]"):
        art = svc.get_article_detail(article_id, column_id=col)

    if json_mode:
        import json
        console.print(json.dumps(art, ensure_ascii=False, indent=2))
        return

    console.print(Panel(
        f"[bold white]{art['title']}[/bold white]\n"
        f"[dim]发布日期: {art.get('date', '未知')}  |  部门: {art.get('department', '教务处')}  |  ID: {article_id}[/dim]",
        border_style="cyan"
    ))
    console.print(art.get("content", ""))
    attachments = art.get("attachments", [])
    if attachments:
        console.print("\n[bold yellow]📎 附件下载列表：[/bold yellow]")
        for idx, att in enumerate(attachments, 1):
            console.print(f"  [{idx}] {att['name']}\n      👉 {att['url']}")

# ==================== 8. 个人全科成绩与 GPA (score) ====================
@app.command(name="score")
def score(
    term: str = typer.Option(None, "--term", "-t", help="按学年学期筛选，如 '2024-2025-1'"),
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 格式输出成绩数据")
):
    """查询本科全科学分、各科成绩与加权平均绩点 GPA (moduleId=2020)"""
    engine = _ensure_auth()
    from ..services.score_svc import ScoreService
    svc = ScoreService(engine)
    with console.status("[cyan]正在拉取全科成绩与 GPA 绩点大盘...[/cyan]"):
        res = svc.get_scores(term=term)

    if json_mode:
        import json
        console.print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if res.get("blocked"):
        console.print(f"[bold yellow][提示] 成绩查询受限: {res.get('reason')}[/bold yellow]")
        return

    scores = res.get("scores", [])
    summary = res.get("summary", {})

    table = Table(title=f"哈理工本科成绩大盘 (共 {summary.get('total_courses', len(scores))} 门)", border_style="green")
    table.add_column("学期", justify="center", style="dim")
    table.add_column("课程名称", style="bold white")
    table.add_column("学分", justify="center")
    table.add_column("平时", justify="center", style="dim")
    table.add_column("期末", justify="center", style="dim")
    table.add_column("综合成绩", justify="center", style="bold yellow")
    table.add_column("绩点", justify="center", style="cyan")

    for s in scores:
        table.add_row(
            s.get("term", ""),
            s.get("course_name", ""),
            str(s.get("credit", 0.0)),
            str(s.get("regular_score", "-")),
            str(s.get("exam_score", "-")),
            str(s.get("final_score", "")),
            str(s.get("gpa", 0.0))
        )

    console.print(table)
    console.print(
        f"[bold cyan]📊 学业汇总[/bold cyan]: "
        f"总学分: [bold green]{summary.get('total_credits')}[/bold green]  |  "
        f"加权平均分: [bold green]{summary.get('weighted_avg_score')}[/bold green]  |  "
        f"加权 GPA: [bold yellow on black] {summary.get('gpa')} [/bold yellow on black]"
    )

# ==================== 8.5 期末考试日程大盘 (exam) ====================
@app.command(name="exam")
def exam(
    term: str = typer.Option(None, "--term", "-t", help="按学年学期筛选，如 '2024-2025-1'"),
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 格式输出考试数据")
):
    """考前神器：查询期末/期中考试科目、考试时间、考场教学楼与座位号 (moduleId=2030)"""
    engine = _ensure_auth()
    from ..services.exam_svc import ExamService
    svc = ExamService(engine)
    with console.status("[cyan]正在拉取学生期末考试与考场安排日程...[/cyan]"):
        res = svc.get_exams(term=term)

    if json_mode:
        import json
        console.print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    exams = res.get("exams", [])
    if not exams:
        console.print(f"[yellow]{res.get('msg', '当前暂无考试安排')}[/yellow]")
        return

    table = Table(title=f"哈理工期末考试日程大盘 (共 {len(exams)} 门)", border_style="cyan")
    table.add_column("学期", justify="center", style="dim")
    table.add_column("考试课程", style="bold white")
    table.add_column("性质", justify="center")
    table.add_column("考试时间", style="bold yellow")
    table.add_column("考场地点", style="cyan")
    table.add_column("座位号", justify="center", style="bold green")
    table.add_column("备考状态", justify="center")

    for e in exams:
        status_styled = e.get("countdown_desc", "")
        if "今日" in status_styled or "明天" in status_styled:
            status_styled = f"[bold red on white]{status_styled}[/bold red on white]"
        elif "还有" in status_styled and (e.get("days_left") or 99) <= 7:
            status_styled = f"[bold yellow]{status_styled}[/bold yellow]"
        elif "已考完" in status_styled:
            status_styled = f"[dim]{status_styled}[/dim]"

        table.add_row(
            e.get("term", ""),
            e.get("course_name", ""),
            e.get("exam_type", "正常考试"),
            e.get("exam_time", "待排定"),
            e.get("location", "考场未公布"),
            str(e.get("seat_no", "-")),
            status_styled
        )

    console.print(table)
    console.print(f"[bold cyan]💡 提示[/bold cyan]: 请提前 15 分钟携带学生证/身份证抵达考场，严禁携带智能手表与通信设备。")

# ==================== 8.8 一卡通消费流水账单 (card) ====================
@app.command(name="card")
def card(
    start: str = typer.Option("", "--start", "-s", help="起始日期 (格式: YYYY-MM-DD)"),
    end: str = typer.Option("", "--end", "-e", help="结束日期 (格式: YYYY-MM-DD)"),
    json_mode: bool = typer.Option(False, "--json", help="以 JSON 格式输出消费账单")
):
    """查询一卡通/水控近期洗浴与热水消费流水账单与扣费明细"""
    _ensure_network()
    from ..services.water_svc import WaterService
    from ..core.auth import get_credentials, get_water_token

    w_info, w_tok = get_water_token()
    u, _ = get_credentials()

    if not w_tok:
        console.print("[bold yellow]未检测到水控凭据！请先运行 hrbust qr 扫码登录或 hrbust login 绑定学号密码。[/bold yellow]")
        raise typer.Exit(code=1)

    account = u or "2306010309"
    svc = WaterService()
    with console.status("[cyan]正在拉取一卡通消费流水账单...[/cyan]"):
        try:
            res = svc.get_cost_records(account, account, w_tok, start_date=start, end_date=end)
        except Exception as e:
            console.print(f"[bold red][错误] 获取一卡通账单失败: {e}[/bold red]")
            raise typer.Exit(code=1)

    if json_mode:
        import json
        console.print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    records = res.get("records", [])
    summary = res.get("summary", {})

    if not records:
        console.print("[yellow]近期暂无一卡通消费扣费记录。[/yellow]")
        return

    table = Table(title=f"哈理工一卡通消费流水账单 (共 {summary.get('total_count', len(records))} 笔)", border_style="cyan")
    table.add_column("序号", justify="center", style="dim")
    table.add_column("交易时间", style="bold white")
    table.add_column("消费场所 / 扣费项目", style="cyan")
    table.add_column("扣款金额 (元)", justify="right", style="bold yellow")

    for idx, r in enumerate(records, 1):
        amt = r.get("amount", 0.0)
        table.add_row(
            str(idx),
            r.get("time", ""),
            r.get("place", ""),
            f"-{amt:.2f}"
        )

    console.print(table)
    console.print(
        f"[bold cyan]💰 消费汇总[/bold cyan]: "
        f"查询笔数: [bold green]{summary.get('total_count')} 笔[/bold green]  |  "
        f"累计消费支出: [bold yellow on black] ¥ {summary.get('total_cost')} [/bold yellow on black]"
    )

# ==================== 9. 办事大厅与水控扫码登录 (qr) ====================
@app.command(name="qr")
def qr_login():
    """免输密码：展示网上办事大厅 / 统一身份认证字符二维码，手机扫码秒登"""
    _ensure_network()
    from ..services.water_svc import WaterService
    import time
    svc = WaterService()

    with console.status("[cyan]正在申请网上办事大厅二维码会话...[/cyan]"):
        try:
            session = svc.start_qr_login()
        except Exception as e:
            console.print(f"[bold red][错误] 获取二维码失败: {e}[/bold red]")
            raise typer.Exit(code=1)

    uuid = session["uuid"]
    qr_ascii = session["qr_ascii"]

    console.print(Panel(
        f"[bold white]{qr_ascii}[/bold white]",
        title="[bold yellow]📱 网上办事大厅 / 水控移动端扫码登录[/bold yellow]",
        subtitle="微信 / 今日校园 / 哈理工移动端扫码",
        border_style="cyan"
    ))
    console.print("[dim]提示: 请在手机端扫描上方二维码并点击「确认登录」 (超时时间 120 秒)[/dim]\n")

    start_t = time.time()
    with console.status("[cyan]等待手机扫码中...[/cyan]") as st:
        while time.time() - start_t < 120:
            status = svc.check_qr_status(uuid)
            if status == "2":
                st.update("[yellow]已扫码！请在手机上点击「确认登录」...[/yellow]")
            elif status == "1":
                st.update("[green]手机端已确认授权！正在自动换取水控凭据并加密落盘...[/green]")
                res = svc.finish_qr_login(uuid)
                if res.get("success"):
                    console.print(f"\n[bold green]✅ 扫码单点登录成功！一卡通账号: {res.get('account')}[/bold green]")
                    console.print("[green]水控业务凭据已自动同步至本地安全保险箱。现在可直接执行 hrbust water 或打开 TUI 秒约洗澡！[/green]")
                    return
                else:
                    console.print(f"\n[bold red][错误] 换票失败: {res.get('msg')}[/bold red]")
                    raise typer.Exit(code=1)
            elif status == "3":
                console.print("\n[bold red]二维码已超时失效，请重新运行 hrbust qr 获取新码。[/bold red]")
                raise typer.Exit(code=1)
            time.sleep(1.5)

    console.print("\n[yellow]扫码超时，请重新运行 hrbust qr。[/yellow]")

@app.command(name="tui")
def tui():
    """启动 HRBUST 全屏交互式终端中枢大盘 (TUI)"""
    from ..tui.app import run_tui
    run_tui()

@app.command("logout")
def logout():
    """登出并彻底清空本地安全保险箱凭据"""
    from ..core.auth import clear_all_credentials
    clear_all_credentials()
    console.print("[green]已成功退出登录，本地安全凭据已彻底清空。[/green]")

@app.command("status")
def status():
    """检查当前系统登录态与安全凭据存储状态"""
    from ..core.auth import get_credentials, get_water_token
    u, p = get_credentials()
    w_info, w_tok = get_water_token()
    
    table = Table(title="HRBUST 凭据与安全状态", box=box.SIMPLE)
    table.add_column("检测项目", style="cyan")
    table.add_column("状态", style="bold")
    
    table.add_row("教务账号", u if u else "[dim]未配置[/dim]")
    table.add_row("教务密码", "******" if p else "[dim]未配置[/dim]")

    if w_info and w_tok:
        water_desc = "[green]已就绪 (通过统一身份认证全自动激活)[/green]"
    elif u and p:
        water_desc = "[yellow]已关联学号 (敲 hrbust water 将全自动激活，免抓包)[/yellow]"
    else:
        water_desc = "[dim]未配置 (配置学号密码后将全自动打通)[/dim]"

    table.add_row("水控凭据", water_desc)
    table.add_row("底层存储", "机器特征绑定 AES-256-GCM 密文保险箱 (0600)")
    console.print(table)
    console.print("[dim]💡 提示: 水控系统已接入学校统一身份认证 (CAS)。直接敲 hrbust water 即可全自动激活出码，无需手动抓包。[/dim]")

def run():
    if len(sys.argv) == 1:
        # 直接敲 hrbust 默认优雅切入交互式全屏 TUI 大盘
        from ..tui.app import run_tui
        run_tui()
    else:
        app()

if __name__ == "__main__":
    run()
