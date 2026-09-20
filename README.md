# HRBUST Toolkit (哈理工数字化校园全栈开源 CLI 与 SDK)

哈尔滨理工大学（HRBUST）数字化校园全栈终端工具箱与开发 SDK。
集成教务在线学业系统、一卡通洗浴控水系统、空教室与多媒体自习室查询、以及教务处最新公告新闻。

## 核心特性

- **代理安全免疫**：内置校园内网专用会话通道，自动屏蔽宿主机 VPN/代理客户端（如 Clash/v2rayN）造成的 502 与网络超时，确保内网纯净直连。
- **浴室洗浴水控 (`hrbust water`)**：实时查询南区/西区浴室与公寓热水空闲率，数字键一秒申请 4 位有效出水预约码。
- **自习与多媒体教室 (`hrbust room`)**：按教学楼检索空闲教室，自动高亮打标微机/投影多媒体专用教室，支持查单教室全周课表。
- **个人学业课表 (`hrbust today`)**：自动打码登录教务在线，输出当日课程安排与全周矩阵，支持培养方案学分清点。
- **公告与每日资讯 (`hrbust notice` / `news` / `daily`)**：免登录拉取教务处最新通知与教学动态，自动修正官方 GBK 附件乱码；支持 `--json` 输出供微信机器人（AstrBot）或 Agent 定时调度。
- **全生态解耦适配**：底层采用 Clean Architecture 架构，既是开箱即用的 CLI，又是标准的 Python SDK，可无缝对接 Hermes Agent Tools 或 AstrBot 插件。

## 快速上手

### 1. 安装

```bash
git clone https://github.com/Wdclouds/hrbust-cli.git
cd hrbust-cli
pip install -e .
```

### 2. 常用命令概览

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

## 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
仅供个人学习与校园生活效率提升使用，严禁用于任何商业牟利行为。
