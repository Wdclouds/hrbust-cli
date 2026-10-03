# HRBUST Toolkit (哈理工数字化校园全栈开源 CLI 与 SDK)

<p align="center">
  <b>全屏命令中枢 TUI · 居中 ASCII 艺术字 · 底部常驻交互命令条 · 右侧 1/4 实时学校动态 · 代理安全免疫</b>
</p>

哈尔滨理工大学（HRBUST）数字化校园全栈终端工具箱与开发 SDK。  
集成全新进化的交互式终端命令中枢（TUI）、教务在线学业系统、一卡通洗浴控水系统、空教室与多媒体自习室查询、以及教务处最新公告新闻。

---

## 🌟 核心特性

- 🖥️ **全新进化：现代化命令中枢 TUI (`hrbust` / `hrbust tui`)**：
  - 基于 **Textual 8.x** 高性能终端引擎打造的暗黑极客命令中枢；
  - **中间视觉焦点**：居中巨幅 **`HRBUST` ASCII 艺术字 Logo** + 快捷交互指引面板；
  - **最下方常驻命令输入条**：`❯ 键入指令 (如: water, room 南一, today, news, status, help, exit)...`，全键盘丝滑命令驱动；
  - **右侧 1/4 独立校园动态栏**：自动异步拉取教务在线最新的增量通知与教学动态，卡片式流式呈现；
  - **无缝视图切入与一键归位**：输入 `water` 展现实时水控机位与秒约、输入 `room 南一` 筛选自习室、按 `Esc` 或输入 `home` 随时一键切回大 Logo 首页。
- 🛡️ **代理安全免疫**：内置校园内网专用会话通道，自动屏蔽宿主机 VPN/代理客户端（如 Clash/v2rayN）造成的 502 与网络超时，确保内网纯净直连。
- 🚿 **浴室洗浴水控 (`hrbust water`)**：实时查询南区/西区浴室与公寓热水空闲率，数字键一秒申请 4 位有效出水预约码。
- 🏫 **自习与多媒体教室 (`hrbust room`)**：按教学楼检索空闲教室，自动高亮打标微机/投影多媒体专用教室，支持输入关键词动态过滤。
- 📅 **个人学业课表 (`hrbust today`)**：自动打码登录教务在线，输出当日课程安排与全周矩阵，支持培养方案学分清点。
- 📢 **公告与每日资讯 (`hrbust notice` / `news` / `daily`)**：免登录拉取教务处最新通知与教学动态，自动修正官方 GBK 附件乱码；支持 `--json` 输出供微信机器人（AstrBot）或 Agent 定时调度。
- 🔌 **全生态解耦适配**：底层采用 Clean Architecture 架构，既是开箱即用的 CLI，又是标准的 Python SDK，可无缝对接 Hermes Agent Tools 或 AstrBot 插件。

---

## 🚀 快速上手

### 1. 安装与环境准备

确保系统安装了 Python 3.9+：

```bash
git clone https://github.com/Wdclouds/hrbust-cli.git
cd hrbust-cli
pip install -e .
```

### 2. 启动命令中枢 TUI (推荐)

直接在终端输入即可秒开全屏交互式命令中枢：

```bash
hrbust
# 或明确指定
hrbust tui
```

#### TUI 交互命令速查表
| 命令 / 快捷键 | 功能描述 |
| :--- | :--- |
| **`water`** | 展开全校 5 大浴场/热水实时大盘，上下键选中按 `Enter` 闪电出码 |
| **`room [教学楼] [-m]`** | 检索空闲教室（例如 `room 南一`，加 `-m` 仅筛选多媒体机房） |
| **`today` / `schedule`** | 登录教务在线同步本学期大课表与教室节次排布 |
| **`news` / `notice`** | 展开教务处官方最新通知公告全量列表 |
| **`status` / `login`** | 查看当前绑定学号、水控凭据与校园网连通性 |
| **`home` / `Esc`** | 随时一秒平滑切回居中 ASCII Logo 首页 |
| **`q` / `exit`** | 优雅退出 TUI 界面 |

---

### 3. 命令行快捷指令 (CLI 批处理模式)

除了全屏 TUI 外，所有功能均支持以脚本化 CLI 命令单次调用：

```bash
# 1. 浴室水控 (查看空闲率大盘并一键预约)
hrbust water

# 2. 查找空闲自习室 (可筛选多媒体教室)
hrbust room
hrbust room 南一 --media

# 3. 查课表
hrbust today      # 今日课程预报

# 4. 教务公告与新闻
hrbust notice     # 教务公告
hrbust news       # 教学新闻
hrbust daily      # 过去 24 小时增量资讯汇总
```

---

## 🧪 自动化测试验证

本项目拥有完善的 Textual TUI 无头模拟驱动测试套件：

```bash
pytest tests/test_tui_smoke.py
```

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。  
仅供个人学习与校园生活效率提升使用，严禁用于任何商业牟利行为。
