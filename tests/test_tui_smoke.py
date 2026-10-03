"""
HRBUST TUI 自动化冒烟测试脚本
验证全屏组件挂载、快捷键响应、5 大选项卡切换及优雅退出
"""

import sys
import asyncio
from pathlib import Path

# 将项目根目录注入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from hrbust.tui.app import HrbustTuiApp
from textual.widgets import TabbedContent, DataTable, Header, Footer


async def run_smoke_test():
    print("[1/4] 初始化 HrbustTuiApp 实例...")
    app = HrbustTuiApp()

    print("[2/4] 进入 Textual 模拟驱动 (run_test)...")
    async with app.run_test(size=(120, 36)) as pilot:
        # 1. 验证基础框架组件
        header = app.query_one(Header)
        footer = app.query_one(Footer)
        tabs = app.query_one("#main-tabs", TabbedContent)

        assert header is not None, "Header 应该成功挂载"
        assert footer is not None, "Footer 应该成功挂载"
        assert tabs is not None, "TabbedContent 应该成功挂载"
        assert tabs.active == "tab-water", f"初始 Tab 应该是 tab-water, 实际是 {tabs.active}"
        print("  ✓ 核心骨架与顶部/底部导航正常挂载")

        # 2. 验证各个表格存在
        t_water = app.query_one("#table-water", DataTable)
        t_room = app.query_one("#table-room", DataTable)
        t_sched = app.query_one("#table-schedule", DataTable)
        t_news = app.query_one("#table-news", DataTable)

        assert t_water is not None
        assert t_room is not None
        assert t_sched is not None
        assert t_news is not None
        print("  ✓ 水控大盘、自习室、课表、新闻四大 DataTable 均已挂载")

        # 3. 模拟快捷键 1~5 切换 Tab
        print("[3/4] 模拟全键盘交互与选项卡切换...")
        await pilot.press("2")
        assert tabs.active == "tab-room", f"按 '2' 应切换至自习室, 实际: {tabs.active}"

        await pilot.press("3")
        assert tabs.active == "tab-schedule", f"按 '3' 应切换至学业课表, 实际: {tabs.active}"

        await pilot.press("4")
        assert tabs.active == "tab-news", f"按 '4' 应切换至教务公告, 实际: {tabs.active}"

        await pilot.press("5")
        assert tabs.active == "tab-status", f"按 '5' 应切换至安全状态, 实际: {tabs.active}"

        await pilot.press("1")
        assert tabs.active == "tab-water", f"按 '1' 应切换回水控大盘, 实际: {tabs.active}"
        print("  ✓ 快捷键 1~5 选项卡无缝流转测试通过")

        # 4. 模拟按 q 退出
        print("[4/4] 模拟按 'q' 触发优雅退出...")
        await pilot.press("q")

    print("\n🎉 [PASS] HRBUST TUI 全链路自动化冒烟测试 100% 成功通过！\n")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
