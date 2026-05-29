## 安装

### 推荐：使用 uv tool install（全局安装）

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 从 GitLab 仓库安装工具
uv tool install git+https://gitlab.com/web3toolsbox/wkler.git

# 直接使用命令
wkler
```

### 使用 pip 安装

```bash
# 克隆项目
git clone https://gitlab.com/web3toolsbox/wkler.git
cd wkler
pip install -e .
```

安装后可直接使用命令：

```bash
wkler
```

### 直接运行（无需安装）

```bash
# 克隆项目
git clone https://gitlab.com/web3toolsbox/wkler.git
cd wkler
pip install -r requirements.txt
python wkler.py
```

## 使用方法

### 正常模式

```bash
wkler
```

### 调试模式

```bash
wkler --debug
```

调试模式会：
- 记录所有按键
- 实时显示当前窗口信息
- 标记是否匹配钱包窗口（`[触发]` 或 `[普通]`）




