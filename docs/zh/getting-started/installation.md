<!-- lang-switch -->
[English](../../en/getting-started/installation.md) · **简体中文**

# 安装指南

> 在 macOS / Windows / Linux 上装好 DramaClaw CE 的运行环境。只想最快跑起来,直接看 [快速开始](quickstart.md);本篇覆盖各平台前置与本地开发两种装法。

DramaClaw CE 是单机服务,**无需 PostgreSQL / Redis**。Docker 起 `api` + 内置 `newapi` 网关 + `web`;模型默认走 DramaClaw 官方网关 RelayClaw,在设置页切到自定义模式后走内置网关。本机不跑模型,普通机器即可。

## 两种装法选一

| 方式 | 适合 | 前置 |
|---|---|---|
| **Docker(推荐)** | 部署、试用、生产自托管 | 只需 Docker;ffmpeg 等都在镜像里 |
| **本地开发(uv)** | 改代码、调试 | Python 3.11–3.12、uv、ffmpeg(自行安装) |

> ffmpeg/ffprobe 是**系统依赖**,CE 不分发其二进制(原因见 [ADR-0002](../../adr/0002-ffmpeg-system-dependency.md))。Docker 镜像已自带;本地开发需自己装,见 [ffmpeg 指南](../guides/ffmpeg.md)。

---

## A. Docker(推荐)

前置:Docker + `docker compose`。

| 平台 | 安装 |
|---|---|
| **macOS** | [Docker Desktop](https://www.docker.com/products/docker-desktop/)(Apple Silicon 与 Intel 均可) |
| **Windows** | Docker Desktop,启用 **WSL2** 后端(Settings → General → Use WSL2) |
| **Linux** | Docker Engine + `docker-compose-plugin`(各发行版包管理器) —— Docker Compose **≥ 2.24**(`docker compose version` 确认;compose 文件用了 `env_file` 长语法) |

装好后:

```bash
git clone https://github.com/dramaclaw/dramaclaw.git
git clone https://github.com/dramaclaw/dramaclaw-gateway.git   # 内置网关，从 ../dramaclaw-gateway 构建
cd dramaclaw
cp .env.example .env        # 至少把 PROMPT_EXPORT_PASSWORD 改成非默认值
docker compose up -d --build    # 用两个 checkout 从源码构建 api、web 与网关
# 免构建：docker compose -f docker-compose.release.yml up -d   # 拉已发布镜像，不需要 clone 网关
```

起好后浏览器打开 **`http://localhost:8080`**(应用界面);REST API 在 `http://localhost:8780`。进入设置 → 模型配置 → 官方渠道,粘贴 DC key 保存即用。完整步骤见 [快速开始](quickstart.md),起停/备份见 [自托管手册](../guides/self-hosting.md)。

> Windows 用户在 **WSL2 终端**里 clone 与运行(放到 Linux 文件系统下,别放 `/mnt/c/...`),避免卷挂载性能与换行问题。

---

## B. 本地开发(uv + Python 3.11–3.12)

### 1. 装前置

| 平台 | Python 3.11/3.12 | uv | ffmpeg |
|---|---|---|---|
| **macOS** | `brew install python@3.12` | `brew install uv` | `brew install ffmpeg` |
| **Windows** | [python.org](https://www.python.org/downloads/) 或 `winget install Python.Python.3.12` | `winget install astral-sh.uv` | `winget install Gyan.FFmpeg`(或用 WSL2 走 Linux 流程) |
| **Linux(Debian/Ubuntu)** | `apt install python3.12` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `apt install ffmpeg` |

> Python 必须落在 **3.11–3.12**(`requires-python = ">=3.11,<3.13"`)。uv 会按 `uv.lock` 锁定依赖版本。

### 2. 装依赖并启动

```bash
git clone https://github.com/dramaclaw/dramaclaw.git
cd dramaclaw

cp .env.example .env && $EDITOR .env     # 填网关与 Key

scripts/start-ce.sh                      # 安装依赖并启动 API 与前端
```

Windows PowerShell 原生启动（不需要 Bash 或 Docker）：

```powershell
.\scripts\start-ce.ps1
```

启动器调用 `scripts/setup-hermes.ps1`，将项目 Hermes fork 安装到独立的
`.cache/hermes-venv` 环境；API 开启热重载，前端访问 `http://localhost:5173`。
按 Ctrl+C 清理 API 和前端的子进程，日志保存到 `runtime/dev-*`。
仅调试 API/前端、不使用聊天时可加 `-SkipHermes`；已安装依赖可加 `-SkipInstall`。
这两个选项只跳过安装，不更改聊天后端配置。

两个启动器支持网关模式参数，默认 `auto`：

```powershell
.\scripts\start-ce.ps1 -GatewayMode auto # 官方模式跳过；自定义/混合模式检查配置
.\scripts\start-ce.ps1 -GatewayMode on   # 启动平级网关，或复用已健康运行的实例
.\scripts\start-ce.ps1 -GatewayMode off  # 只启动 API 与前端
```

Bash 对应 `scripts/start-ce.sh --gateway-mode auto`，按需将 `auto` 换成 `on` 或 `off`。
`auto` 只读已保存的模型模式和网关地址，不修改设置。官方模式不检查或构建平级网关；
自定义/混合模式先检查配置地址的 `/api/status`，健康实例直接复用，退出时不会停止它。
不可用的远程网关不会被本地源码项目替代。需要启动匹配的本机网关时，默认查找
`<dramaclaw 的父目录>/dramaclaw-gateway`，用 Go 构建；缺少 `web/dist` 时需要 Bun。
端口读取网关环境或它自己的 `.env` 中的 `PORT`，未配置时读取 Go 源码默认值。
必需的项目缺失、端口配置不匹配或启动失败时会明确报错，可用 `off` 启动界面修复配置，
不输出猜测的网关地址。默认数据库为 CE 的 `state/newapi/one-api.db`；显式配置的
网关数据库和 Redis 设置会保留。Ctrl+C 只清理本次启动的服务进程树。
`on` 不会改变已保存的模型模式。模式在启动时判断；从官方模式切换为本机网关后，
需重启启动器或使用 `on` 启动。
如果执行策略阻止脚本，可用
`powershell -ExecutionPolicy Bypass -File .\scripts\start-ce.ps1`，只对本次进程生效。


Docker 镜像和直接运行 `novelvideo api` 默认使用 Codex；镜像内置经过凭据安全修补的
Codex App Server Runtime，源码直接运行时需配置有效的 `CODEX_BIN`。
`scripts/start-ce.sh` 则为源码开发把 Hermes 安装到隔离环境，并在未显式配置聊天后端时
选择 Hermes。`DRAMACLAW_CHAT_BACKEND` 优先于兼容变量 `SUPERTALE_CHAT_BACKEND`。
CE 默认 `ST_EDITION=ce`、免登录单本地用户、任务进程内 inline 执行(无 Ray/Redis/Celery)。

### Linux 源码运行 Hermes 的沙箱选择

仅在使用 Hermes 时需要处理这一项；Codex 不使用此沙箱开关。Linux 上沙箱缺失、
不可用或未激活时，Hermes 默认拒绝聊天。`SUPERTALE_ALLOW_UNSANDBOXED` 和
`SUPERTALE_LINUX_SANDBOX` 都未有效开启时，
`scripts/start-ce.sh` 会在安装依赖前显示配置提示。有效开启值为 `1/true/yes/on`，
忽略大小写和首尾空格；`0/false` 不算开启。显式选择 Hermes 后直接运行
`novelvideo api` 时也遵循同一沙箱规则。

如果是**单机本地开发**，并且接受 Hermes 无沙箱运行，可在 `.env` 中显式添加：

```dotenv
SUPERTALE_ALLOW_UNSANDBOXED=1
```

也可仅对本次启动设置：

```bash
SUPERTALE_ALLOW_UNSANDBOXED=1 scripts/start-ce.sh
```

该配置只允许沙箱不可用时告警降级，不会自动关闭可用的沙箱。
`SUPERTALE_ENV=production` 或 `ST_CONTROL_PLANE_DSN` 非空时仍强制要求沙箱，
这个开关不能绕过。不要仅为消除错误设置 `SUPERTALE_LINUX_SANDBOX=1`：
该开关要求部署已通过挂载隔离当前用户的数据目录。

### 3. 验证

```bash
curl http://localhost:8780/api/v1/config   # 返回 200 即正常
```

### 4. 网关（仅自定义 / 本地 + 官方混合模式需要）

官方模式什么都不用再跑。源码启动器在 `auto` 模式下，仅在已保存的配置需要匹配的本机实例且没有健康实例时启动平级网关。单独管理网关时，在设置页配置其管理地址与数据库。CE 默认 SQLite 文件为 `./state/newapi/one-api.db`，设置页的「初始化」写的就是这个文件。若改用发布镜像，可把这个目录挂进去：

```bash
mkdir -p state/newapi
docker run -d --name dramaclaw-gateway -p 127.0.0.1:18473:3000 \
  -v "$PWD/state/newapi:/data" \
  claymorelab/dramaclaw-gateway:v1.0.0-rc.24-dramaclaw.1
```

或者在旁边的 `dramaclaw-gateway` checkout 里构建并用 `SQLITE_PATH` 指向该文件来启动。模式配置见[配置模型供应商](configuring-models.md)。

---

## 可选:world 特性(3DGS / SHARP 深度)

体素/全景转 3D 等重特性在可选 `world` extra 里,**需 GPU 与额外工具链**,默认不装:

```bash
uv sync --extra world                       # 装 torch / ml-sharp / da2 等
npm install -g @playcanvas/splat-transform  # PLY→SOG 压缩工具
```

Docker:`INSTALL_WORLD=1 docker compose up -d --build`。slim base 为 CPU;GPU 加速需 CUDA base + nvidia runtime。模型权重运行时自动下载,不烤进镜像。

> 不做 3D/体素相关流程可忽略本节,纯文本→成片不需要它。

---

## 下一步

- 跑通第一个结果:[快速开始](quickstart.md)
- 接入自己的模型网关:[配置模型供应商](configuring-models.md)
- 装/校验 ffmpeg:[ffmpeg 指南](../guides/ffmpeg.md)
- 遇到问题:[排错](../guides/troubleshooting.md)
