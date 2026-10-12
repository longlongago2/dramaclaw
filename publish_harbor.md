# 发布到公司 Harbor

`scripts/publish_harbor.py` 使用 Python 3.11+ 标准库，无需安装 Python 依赖。
需要 Docker CLI、Docker Compose，以及运行中的 Docker Engine。

**首次发布前，需要自己在 Harbor 网页中创建“文件夹”（Harbor 中称为项目）。
脚本不会自动创建项目，登录成功也不代表项目已经存在。**

1. 打开 <https://harbor.n.nebulaedata.com/> 并登录。
2. 进入「项目」→「新建项目」，项目名填写 `dramaclaw`（脚本默认值）。
   创建普通项目，可保持私有。
3. 确认发布账号有该项目的推送权限。
4. 如果使用其他项目名，运行脚本时指定 `--project 你的项目名`。

例如，镜像地址 `harbor.n.nebulaedata.com/dramaclaw/dramaclaw:20261009-1`
中，域名后的第一个 `dramaclaw` 是需要手动创建的项目，第二个是镜像仓库名。
三个镜像仓库会在成功推送时创建，无需分别手动建文件夹，也无需在本地创建同名目录。

构建网关需要源码，默认取 `../dramaclaw-gateway`；可通过仓库 `.env` 的
`DRAMACLAW_GATEWAY_SRC` 修改路径，与 `docker compose build` 的行为一致。

```powershell
# 预览命令，不登录、不构建、不上传
python scripts/publish_harbor.py --dry-run

# 交互登录并构建、上传三个镜像，默认标签为本机时间 YYYYMMDD-HHMMSS
python scripts/publish_harbor.py

# 自定义 Harbor 项目、标签、登录账号；密码由 Docker 交互提示输入
python scripts/publish_harbor.py --project dramaclaw --tag 20261009-1 --username your-account

# 上传之前已经构建的本地镜像
python scripts/publish_harbor.py --tag 20261009-1 --skip-build
```

默认上传到 `harbor.n.nebulaedata.com/dramaclaw`，镜像名称分别为
`dramaclaw`、`dramaclaw-gateway`、`dramaclaw-frontend`，三者使用同一个标签。
脚本可从任意目录调用，Docker 命令始终在仓库根目录执行。
登录信息由 Docker 管理，脚本不接受密码参数，也不修改 `.env`。

任何 Docker 命令失败都会停止执行并返回非零退出码。三个镜像的推送不是原子操作，
失败前已经成功推送的镜像会保留；全部成功后再更新部署环境的版本。
`--skip-build` 使用当前的 `dramaclaw-local/*:latest`，不会检查其是否对应最新源码。

脚本成功后会输出目标服务器 `.env` 所需的三个配置值。例如：

```dotenv
DRAMACLAW_IMAGE_PREFIX=harbor.n.nebulaedata.com/dramaclaw
DRAMACLAW_VERSION=20261009-1
DRAMACLAW_GATEWAY_VERSION=20261009-1
```

目标服务器准备好 `docker-compose.release.yml` 和运行所需的 `.env` 后执行：

```powershell
docker login harbor.n.nebulaedata.com
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
docker compose -f docker-compose.release.yml ps
```

上传的是本机构建平台的镜像，目标服务器需要兼容的 CPU 架构。
