# 门诊失物招领系统

一个支持「公众失主 + 管理员后台」双角色的失物招领管理网站。
患者/失主不用登录就能浏览失物、提交报失；导医凭口令进入后台登记、认领、统计、导出。

## ✨ 功能总览

### 📱 公众界面（无需登录）
| 功能 | 说明 |
|------|------|
| 失物招领首页 `/` | 浏览被捡到的、待认领的物品，卡片网格展示，可按类别筛选+搜索 |
| 我要报失 `/report` | 失主提交丢失信息（姓名、电话、物品、特征、地点、照片） |

> 隐私保护：敏感物品（证件/医保卡等）登记时可勾选「隐藏照片」，公众界面看不到照片，仅管理员可见。

### 🔒 管理员后台（口令登录，入口 `/login`）
| 功能 | 说明 |
|------|------|
| 工作台 `/admin` | 今日登记/待认领/本月归还 + 待处理报失提醒 |
| 拾物登记 `/register` | 录入物品+拍照/上传，自动生成失物编号（如 `20260729-001`）|
| 认领登记 `/claim` | 定位物品 → 核对特征 → 登记失主信息 → 状态变"已认领" |
| 失物总表 `/list` | 筛选+搜索+日期范围，点行看详情 |
| 报失处理 `/reports` | 查看公众报失，标记已找到/已忽略，填备注 |
| 统计导出 `/stats` `/export` | 按时间段统计，一键导出 Excel |

## 🚀 启动方法

### macOS
找到 `start.command`，**双击**即可（首次会自动准备环境）。

### Windows
找到 `start.bat`，**双击**即可。Windows 详细步骤见 `Windows部署手册.md`。

### 手动启动
```bash
cd 本文件夹路径
pip install -r requirements.txt
python3 app.py
```
然后浏览器打开 **http://127.0.0.1:8000**

> - 进入口令：`8888`（默认值，务必修改，见下方"安全配置"）
> - 公众首页直接打开网址即可，**管理员后台**需点右上角"管理员入口"再输入口令

## 🔐 安全配置（重要，尤其要部署/传 GitHub 时）

口令、密钥通过**环境变量**配置，不写死在代码里：

1. 复制 `.env.example` 为 `.env`
2. 修改其中的值：
   ```
   LF_PASSWORD=你的强口令
   LF_SECRET_KEY=一长串随机字符
   ```
3. 本地开发可不配 `.env`（会用默认值）；**部署到服务器/提交到 GitHub 前，务必设置环境变量，绝不要用默认口令**

生成随机密钥：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 🌐 多端访问

服务器电脑运行程序后，其他设备（手机/电脑）连同一局域网，浏览器输入：
```
http://服务器IP:8000
```
查 IP：服务器电脑终端执行 `ipconfig getifaddr en0`（Mac）或 `ipconfig`（Windows）。

> 注意：手机浏览器在 http 下摄像头功能可能受限，可改用「上传图片」调起手机相机。

## 💾 数据备份

所有数据在本文件夹内：
- `lostfound.db` —— 所有记录（最重要）
- `uploads/` —— 所有照片

**定期把这两个拷走即可备份。**

## 📁 项目结构

```
待领处1/
├── app.py                  # Flask 主程序（路由、数据库、业务逻辑）
├── config.py               # 配置（口令、端口、类别、地点等）
├── openpyxl_export.py      # Excel 导出模块
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量示例（复制为.env使用）
├── .gitignore              # Git 忽略规则
├── start.command           # macOS 双击启动
├── start.bat               # Windows 双击启动
├── start.sh                # Linux/通用启动
├── Windows部署手册.md       # Windows 局域网部署详细步骤
├── templates/              # 页面模板
│   ├── base.html           # 管理后台父模板
│   ├── base_public.html    # 公众页父模板
│   ├── public_index.html   # 公众首页
│   ├── public_report.html  # 公众报失页
│   ├── login.html / index.html / register.html / claim.html / list.html / reports.html / stats.html
├── static/                 # 样式、脚本
│   ├── style.css
│   └── app.js
├── uploads/                # 照片（运行时生成，不提交）
└── lostfound.db            # 数据库（运行时生成，不提交）
```

## 🛠️ 技术栈
- 后端：Python + Flask
- 数据库：SQLite（单文件，零配置）
- 前端：原生 HTML/CSS/JS（无框架）
- 导出：openpyxl
- 生产部署：gunicorn（可选）

## 📤 部署到云服务器（规划中）

将来部署到阿里云等服务器时：
1. 把代码传到服务器（可通过 Git）
2. 安装依赖：`pip install -r requirements.txt`
3. 配置环境变量（`LF_PASSWORD`、`LF_SECRET_KEY`）
4. 用 gunicorn 运行：`gunicorn -b 0.0.0.0:8000 app:app`
5. 配合 nginx 做反向代理 + HTTPS（手机拍照需要 HTTPS）
6. 国内服务器+域名访问需 ICP 备案

## ❓ 常见问题
**Q：管理员怎么进后台？** A：点公众页面右上角"管理员入口 →"，输口令登录。

**Q：公众能看认领人的电话吗？** A：不能。公众只能看物品本身信息，认领人姓名/电话仅管理员可见。

**Q：报失信息会公开吗？** A：不会。报失的姓名电话仅管理员可见。

**Q：怎么改口令、类别、导医名单？** A：环境变量改口令；`config.py` 改类别/地点/导医名单。改完重启。
