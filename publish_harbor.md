# Harbor 镜像发布与服务器部署

本文分为两部分：先在构建机器上把三个镜像推送到公司 Harbor，再在目标服务器上拉取镜像并启动服务。
部署沿用 `docker-compose.release.yml` 的默认运行参数，只配置 Harbor 镜像来源与版本。

标签由脚本自动生成，固定格式为 `YYYYMMDD-8位提交SHA`（构建机器本地日期 + 主项目 Git HEAD），
例如 `20261019-01f4db4f`。三个镜像共用同一标签，不接受手动 `--tag`。
文中的标签仅为示例，部署时复制脚本实际输出的版本值。

## 1. 发布到公司 Harbor Docker 镜像仓库

本章在**构建机器**上执行，命令以 Windows PowerShell 为例。

### 1.1 检查工具和项目目录

需要 Python 3.11+、Git、Docker CLI、Docker Compose，以及运行中的 Docker Engine。
`scripts/publish_harbor.py` 只使用 Python 标准库，不需要额外安装 Python 依赖。

进入本地项目根目录，然后检查工具：

```powershell
cd D:\code\local\dramaclaw
python --version
git --version
docker version
docker compose version
```

本地目录不同，替换 `cd` 后面的路径。`docker version` 应能显示 Client 和 Server；
若提示无法连接 Docker Engine，先启动 Docker Desktop 或 Docker 服务。

### 1.2 在 Harbor 创建项目并确认权限

1. 打开 <https://harbor.n.nebulaedata.com/>，登录公司 Harbor。
2. 进入「项目」，确认存在名为 `dramaclaw` 的项目；没有则通过「新建项目」创建普通项目，可保持私有。
3. 确认发布账号拥有该项目的推送权限。

脚本不会自动创建 Harbor 项目。三个镜像仓库会在成功推送时创建，无需分别手动创建。
如果使用其他项目名，后面的脚本命令加上 `--project 你的项目名`，服务器也使用同一项目名。

### 1.3 推送镜像

直接运行脚本即可生成标签，无需手填日期、分支名或功能名。
同一天、同一提交重复运行会使用相同标签；Git HEAD 读取失败时停止发布。

**已经执行过 `docker compose up -d --build` 并构建成功**，直接上传已有镜像：

```powershell
# 先预览命令，不登录、不构建、不上传
python scripts/publish_harbor.py --skip-build --dry-run

# 正式登录、打标签并上传三个镜像
python scripts/publish_harbor.py --skip-build
```

按提示输入 Harbor 用户名和密码。也可以显式指定用户名：

```powershell
python scripts/publish_harbor.py --skip-build --username your-account
```

**需要重新构建后再上传**，先确保网关源码存在于项目旁边的 `../dramaclaw-gateway`：

```powershell
# 仅在网关目录尚不存在时执行
git clone https://github.com/dramaclaw/dramaclaw-gateway.git ../dramaclaw-gateway

# 构建 API、网关和前端，再上传
python scripts/publish_harbor.py
```

网关源码放在其他位置时，可通过本地 `.env` 的 `DRAMACLAW_GATEWAY_SRC` 指定路径。
重新构建使用 `docker-compose.yml`；目标服务器使用 `docker-compose.release.yml` 拉取镜像。

`--skip-build` 使用当前的 `dramaclaw-local/*:latest`，不会检查镜像是否对应最新源码。
如果刚更新过源码、希望发布这些更新，应使用重新构建命令。

### 1.4 确认上传成功并记录版本

脚本输出 `Publication complete.` 后，在 Harbor 的 `dramaclaw` 项目中确认以下三个仓库均存在，
并且都有本次标签：

| 服务 | Harbor 镜像地址（示例） |
| --- | --- |
| API | `harbor.n.nebulaedata.com/dramaclaw/dramaclaw:20261019-01f4db4f` |
| 网关 | `harbor.n.nebulaedata.com/dramaclaw/dramaclaw-gateway:20261019-01f4db4f` |
| 前端 | `harbor.n.nebulaedata.com/dramaclaw/dramaclaw-frontend:20261019-01f4db4f` |

记录脚本最后输出的三个配置值，下一章直接使用：

```dotenv
DRAMACLAW_IMAGE_PREFIX=harbor.n.nebulaedata.com/dramaclaw
DRAMACLAW_VERSION=20261019-01f4db4f
DRAMACLAW_GATEWAY_VERSION=20261019-01f4db4f
```

任何 Docker 命令失败都会停止发布并返回非零退出码。三个镜像的推送不是原子操作，
失败前已经成功推送的镜像会保留；只有三个镜像全部成功后，才进入服务器部署步骤。
脚本不接受密码参数、不修改 `.env`，登录信息由 Docker 管理。

## 2. 使用 Harbor 仓库部署到目标服务器

本章在**目标 Linux 服务器**上执行，命令使用 Bash。
这是当前仓库社区版单机 Compose 的部署流程。

### 2.1 登录服务器并检查环境

从本机终端登录服务器，替换账号和地址：

```bash
ssh your-user@your-server
```

在服务器上检查 Git、Docker 和 Compose：

```bash
git --version
docker version
docker compose version
uname -m
```

服务器需要安装 Git、Docker Engine 和 Compose 插件；Compose 版本要求 **2.24 或更新**。
缺少工具时先参照 [安装说明](docs/zh/getting-started/installation.md) 准备环境，
确保当前部署账号能够执行 Docker 命令后继续。

镜像发布脚本上传的是构建机器所用平台的镜像，服务器 CPU 架构必须兼容：
`x86_64` 对应 `linux/amd64`，`aarch64` 对应 `linux/arm64`。
可以在构建机器上查询 API 镜像的平台：

```powershell
docker image inspect dramaclaw-local/api:latest --format '{{.Os}}/{{.Architecture}}'
```

### 2.2 用 Git 拉取项目部署文件

本文使用当前项目的 Git 远程地址 `https://github.com/longlongago2/dramaclaw.git` 和 `main` 分支。
如果公司使用其他远程地址或发布分支，替换下面对应的地址和分支，
服务器应使用与本次镜像发布相配套的部署文件。

首次部署：

```bash
mkdir -p "$HOME/apps"
cd "$HOME/apps"
git clone --branch main https://github.com/longlongago2/dramaclaw.git dramaclaw
cd dramaclaw
git pull --ff-only
```

服务器已经有该项目时，进入原部署目录更新，不要重新创建另一套目录：

```bash
cd "$HOME/apps/dramaclaw"
git pull --ff-only
```

如果 Git 提示没有仓库访问权限，先配置 Git 账号的访问权限；它与 Harbor 登录是两套权限。
如需固定构建时记录的 Git 提交，可在拉取后执行 `git checkout --detach <提交SHA>`，
其中 `<提交SHA>` 替换为实际提交。

确认发布文件存在：

```bash
ls docker-compose.release.yml .env.example
```

服务器只从 Harbor 拉取已构建镜像，不需要再克隆网关源码，也不需要安装项目 Python 依赖。

### 2.3 创建服务器环境配置

以下命令只在 `.env` 不存在时创建文件，已有部署的配置会保留：

```bash
if [ ! -f .env ]; then
  cp .env.example .env
fi
chmod 600 .env
nano .env
```

没有 `nano` 时，可使用服务器现有的文本编辑器。
在 `.env` 中配置第一章记录的三个值，每个变量只保留一条未注释的配置：

```dotenv
DRAMACLAW_IMAGE_PREFIX=harbor.n.nebulaedata.com/dramaclaw
DRAMACLAW_VERSION=20261019-01f4db4f
DRAMACLAW_GATEWAY_VERSION=20261019-01f4db4f
```

前缀填写 `Harbor域名/项目名`，不要添加 `https://` 或 Harbor 网页中的 `/harbor/projects/...` 路径。
三个镜像都由本脚本发布时，两项版本填写同一个标签。
其他运行参数沿用现有发布 Compose 默认值；按服务器需求配置模型访问凭据，真实凭据不要提交到 Git。

### 2.4 登录 Harbor 并校验目标镜像

后续命令统一使用 Compose 项目名 `dramaclaw`。
已有部署如使用其他项目名，应在所有命令中替换为原项目名，以继续使用原数据卷。

```bash
docker login harbor.n.nebulaedata.com

docker compose -p dramaclaw -f docker-compose.release.yml config --quiet
docker compose -p dramaclaw -f docker-compose.release.yml config --images
```

`docker login` 使用具有该 Harbor 项目拉取权限的账号。
`config --quiet` 成功时通常没有输出；`config --images` 应显示第一章的三个 Harbor 镜像及实际标签。
如果仍显示 `claymorelab/...` 或其他版本，先检查当前目录的 `.env` 是否保存、变量是否仍被注释，
以及终端是否设置了同名环境变量覆盖 `.env`；修正后重新校验。

### 2.5 拉取镜像并启动服务

```bash
docker compose -p dramaclaw -f docker-compose.release.yml pull
```

三个镜像全部拉取成功后，启动服务：

```bash
docker compose -p dramaclaw -f docker-compose.release.yml up -d --no-build
```

这里始终指定 `docker-compose.release.yml`，服务器使用 Harbor 镜像运行。
不要在这一步执行裸 `docker compose up -d --build`，那会使用源码构建入口。

### 2.6 检查部署结果并访问页面

```bash
docker compose -p dramaclaw -f docker-compose.release.yml ps
docker compose -p dramaclaw -f docker-compose.release.yml logs --tail=100 api newapi web
```

等待首次启动完成，确认 `api`、`newapi`、`web` 均在运行，
带健康检查的服务进入 `healthy`，日志没有反复退出或重启的报错。
在服务器本机检查 API 和前端：

```bash
curl -fsS -o /dev/null -w 'API HTTP %{http_code}\n' http://127.0.0.1:8780/api/v1/config
curl -fsS -o /dev/null -w 'Web HTTP %{http_code}\n' http://127.0.0.1:8080/
```

两个命令均返回 HTTP `200` 后，在浏览器打开 `http://服务器地址:8080`。
如果 `.env` 自定义了 `ST_API_PORT` 或 `ST_WEB_PORT`，上述检查和访问地址也使用相应端口。
远程访问需要服务器防火墙和云安全组允许前端端口；已有域名和反向代理时，通过配置好的域名访问。

首次部署进入页面的「设置 → 模型配置」，按所用网关方式完成配置，
再提交一次实际任务确认业务可用。容器运行和页面可访问是部署检查，实际任务成功才代表业务验收完成。

### 2.7 后续更新

先完成第一章的新镜像发布，记录新标签。在服务器原部署目录中执行：

```bash
cd "$HOME/apps/dramaclaw"
git pull --ff-only
nano .env
```

将 `.env` 中的 `DRAMACLAW_VERSION` 和 `DRAMACLAW_GATEWAY_VERSION` 改为新标签，保存后执行：

```bash
docker compose -p dramaclaw -f docker-compose.release.yml config --quiet
docker compose -p dramaclaw -f docker-compose.release.yml config --images
docker compose -p dramaclaw -f docker-compose.release.yml pull
docker compose -p dramaclaw -f docker-compose.release.yml up -d --no-build
docker compose -p dramaclaw -f docker-compose.release.yml ps
```

如果之前固定到某个 Git 提交，应先 `git fetch origin`，再切换到本次发布对应的提交，
代替 detached HEAD 状态下的 `git pull`。
更新前备份现有数据，方法见 [自托管手册](docs/zh/guides/self-hosting.md)。
数据保存在 `ce-data` 和 `newapi-data` 命名卷中，推送镜像不会同步这些数据。
保持原 Compose 项目名；不要使用 `docker compose down -v`，该命令会删除数据卷。

### 2.8 常见失败处理

| 现象 | 处理步骤 |
| --- | --- |
| Docker 提示无法连接 daemon 或 permission denied | 确认 Docker 服务已启动，当前账号有 Docker 执行权限，再重试。 |
| Harbor 提示 `unauthorized` 或 `denied` | 重新执行 `docker login harbor.n.nebulaedata.com`，确认账号对 `dramaclaw` 项目有本步骤所需的推送或拉取权限。 |
| 拉取提示 `manifest unknown` 或 `not found` | 在 Harbor 检查三个仓库是否都有 `.env` 中的标签，确认项目名与镜像前缀正确。 |
| 提示平台不匹配或 `exec format error` | 核对服务器 CPU 架构与镜像平台，发布与服务器兼容的平台镜像后再部署。 |
| 启动提示端口已占用 | 在 `.env` 中调整对应的 `ST_WEB_PORT`、`ST_API_PORT` 或 `ST_NEWAPI_PORT`，再次执行启动命令。 |
| 容器退出、重启或不健康 | 使用第 2.6 节的日志命令定位具体服务和报错；修正配置后再次执行启动命令并重新检查。 |
| 服务器本机返回 200，但浏览器打不开 | 检查访问地址、前端端口、防火墙、云安全组及反向代理配置。 |
