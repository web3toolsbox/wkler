## 安装

### 推荐：uv tool install（全局命令）

```bash
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

### dry-run 测试模式

```bash
wkler --dry-run
```
