# 贡献指南

感谢你考虑为 DramaClaw 贡献。无论是修 bug、补文档还是加功能，都欢迎。

## 开始之前

- 请先读 [行为准则](CODE_OF_CONDUCT.md)。
- 关于许可：本项目采用 [Elastic License 2.0](LICENSE)（source available）。**提交贡献前，请花一分钟读 [LICENSE](LICENSE) 与下方的[贡献者协议](#贡献者协议)。**
- 安全问题请勿走公开 issue，见 [SECURITY.md](SECURITY.md)。

## 报告 Bug / 提功能建议

- **Bug**：开一个 [Bug 报告](https://github.com/dramaclaw/dramaclaw/issues/new?template=bug_report.yml)，附复现步骤、运行环境、相关日志。
- **功能建议**：开一个 [功能建议](https://github.com/dramaclaw/dramaclaw/issues/new?template=feature_request.yml)，说清场景与动机。
- 不确定从哪入手？看带 [`good first issue`](https://github.com/dramaclaw/dramaclaw/labels/good%20first%20issue) 标签的 issue。

## 提交 PR

### 本地开发

```bash
git clone https://github.com/dramaclaw/dramaclaw.git
cd dramaclaw
uv sync
cp .env.example .env      # 按文档配置模型网关
uv run novelvideo api --port 8780
```

### 跨平台共享技能与项目技能

子仓库默认只提交 `.agents/skills/.gitkeep`，不忽略 `skills/` 目录本身，仅忽略其余内部内容。
该目录必须是普通目录：共享技能的子目录分别链接到工作区根目录的同名技能，项目专属技能使用自己的普通目录。
需要 Python 3.11+ 和 Git；Windows 使用 CPython 创建逐项 Junction，Linux/macOS 创建符号链接。
先从已有工作区或备份恢复根目录的 `.agents/skills` 技能源，再在每个子仓库执行：

```bash
python scripts/init-shared-skills.py
```

默认技能源为 `../.agents/skills`，其他位置可传 `--shared-skills-path <目录>`。脚本可重复运行，
后续新增共享技能时再次运行即可补建链接。原有整个 `skills` 目录的链接若指向正确技能源，
会安全迁移为普通目录加逐项链接；不修改共享源文件，不覆盖项目技能。
重名冲突、共享路径仍被 Git 跟踪或链接指向其他位置时会先报错，不覆盖已有内容。
不要重新提交共享链接。历史分支若仍跟踪共享技能，须先同步本修复，或在不建立这些链接的
独立 worktree 中操作；忽略规则不保护已跟踪文件。

跨平台回归验证：`python scripts/test_init_shared_skills.py`。

### 流程

首次克隆后安装提交前检查（需要 Python 3.11+）：

```bash
uv tool install pre-commit
python scripts/install_commit_hooks.py
```

提交时，安装器添加的准备步骤先根据 Git 暂存区自动更新并暂存
`license-inventory.csv` 的文件增删条目，再运行 pre-commit 的严格校验。
准备步骤在 pre-commit 隐藏未暂存改动之前执行；清单本身有未暂存修改、
已有人工许可元数据与生成规则冲突或清单已从暂存区删除时，会保留内容并暂停提交。
其他未暂存文件不会进入清单，也不会被自动暂存。无需为普通文件增删反复手工更新清单。
可单独运行 `python -X utf8 -m scripts.compliance.update_license_inventory --stage`。

密钥扫描仍照常执行。文案钩子只扫描本次提交的文本文件；CI 继续全量扫描。
每份本地克隆需要安装一次钩子；若运行了普通 `pre-commit install` 覆盖包装步骤，
重新运行上述安装器即可恢复。包含本安装器的分支之间切换不需要重新安装；
未包含安装器的旧分支沿用其原有校验，不调用新的准备参数。

也可手动检查：`uv tool run pre-commit run license-inventory --all-files`。

1. Fork 仓库，从 `main` 切一个主题分支；
2. 改动 + 自测（`uv run pytest`）；
3. 提交信息清晰（建议 [Conventional Commits](https://www.conventionalcommits.org/)），并对**每个 commit** 用 `git commit -s` 附上 DCO 签署（见 [开发者原产证书](#开发者原产证书dco)）；
4. 开 PR，关联对应 issue，简述改动与验证方式。

## 贡献者协议

向本项目提交贡献，即表示你同意：

a. 维护方可按需调整本项目所采用的许可证（更严格或更宽松）；
b. 你贡献的代码可用于商业用途，包括但不限于 DramaClaw 的云 / 托管业务运营。

> 这一条让 DramaClaw 能在 source-available 许可下，把社区贡献也用于官方托管/商业版本——这是「同一套代码、社区与商业不分叉」得以成立的前提。提交贡献即视为接受，无需另外签署。

## 开发者原产证书（DCO）

本项目要求所有贡献通过 DCO（Developer Certificate of Origin 1.1，全文见 [`DCO`](./DCO)）签署 —— **每个 commit 都必须带 `Signed-off-by` 行**，以此声明你有权按本项目许可提交该贡献。

最简单的方式是提交时加 `-s`，git 会用你的 `user.name` / `user.email` 自动补上签署行：

```bash
git commit -s -m "fix: ……"
# 自动生成：Signed-off-by: Your Name <you@example.com>
```

补签历史 commit：`git rebase --signoff <base>`。CI（`.github/workflows/dco.yml` 调 `scripts/check_dco.py`）会校验 PR 内每个 commit，缺签署会标红。

## 获取帮助

[Discussions](https://github.com/dramaclaw/dramaclaw/discussions) ｜ [Issues](https://github.com/dramaclaw/dramaclaw/issues)
