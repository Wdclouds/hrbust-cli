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
    token = get_water_token()
    if not token:
        token = Prompt.ask("[bold yellow]请输入控水系统 Token[/bold yellow]")
        set_water_token(token)

    username, _ = get_credentials()
    if not username:
        username = Prompt.ask("请输入学号")

    water_eng = WaterEngine()
    svc = WaterService(water_eng)

    with console.status("[cyan]正在获取浴场实时空闲大盘...[/cyan]"):
        try:
            info_b64 = water_eng.generate_token_info(username)
            status_list = svc.get_status(info_b64, token)
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
        advice = "[green]极佳无需排队[/green]" if free_rate > 70 else ("[yellow]正常[/yellow]" if free_rate > 30 else "[red]拥挤爆满[/red]")
        table.add_row(
            str(idx),
            item["name"],
            f"{item['total_positions']} 台",
            f"{free_rate:.2f}%",
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
        res = svc.book_water(username, target["class_no"], token)

    if res.get("ret_no") == 0:
        console.print(Panel(
            f"[bold green]预约成功[/bold green]\n\n"
            f"场所: [bold]{target['name']}[/bold]\n"
            f"出水预约码: [bold yellow on black] {res.get('book_code')} [/bold yellow on black]\n"
            f"提示: 请于 60 分钟内在浴室终端输入使用",
            title="洗浴出码凭证",
            border_style="green"
        ))
    else:
        console.print(f"[bold red][错误] 预约失败: {res.get('msg')}[/bold red]")

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

def run():
    app()

if __name__ == "__main__":
    run()


@app.command("logout")
def logout():
    """登出并彻底清空本地安全保险箱凭据"""
    from ..core.auth import clear_all_credentials
    clear_all_credentials()
    console.print("[green]已成功退出登录，本地安全凭据已彻底清空。[/green]")

@app.command("status")
def status():
    """检查当前系统登录态与安全凭据存储状态"""
    from ..core.auth import get_credentials, get_water_token, VAULT_FILE
    u, p = get_credentials()
    w_info, w_tok = get_water_token()
    
    table = Table(title="HRBUST 凭据与安全状态", box=box.SIMPLE)
    table.add_column("检测项目", style="cyan")
    table.add_column("状态", style="bold")
    
    table.add_row("教务账号", u if u else "[dim]未配置[/dim]")
    table.add_row("教务密码", "******" if p else "[dim]未配置[/dim]")
    table.add_row("水控凭据", "已就绪" if (w_info and w_tok) else "[dim]未配置[/dim]")
    table.add_row("底层存储", "机器特征绑定 AES-256-GCM 密文保险箱 (0600)")
    console.print(table)
