# FloatCTF Event Content

用于开发一场 FloatCTF 比赛。

## 1. 创建私有仓库

创建一个空的 Private Repository，例如：

```text
git@github.com:fb0sh/freshcup-2027.git
```

## 2. 克隆模板

```bash
git clone -b event/base --single-branch --filter=blob:none \
  git@github.com:FloatCTF/floatctf-content.git \
  freshcup-2027

cd freshcup-2027
```

目录名即 Event ID，建议使用：

```text
freshcup-2027
summer-2027
xzmu-2027
```

## 3. 初始化

```bash
./scripts/init-event.sh git@github.com:fb0sh/freshcup-2027.git
git push -u origin main
```

初始化后：

```text
origin   → 当前比赛私有仓库
upstream → FloatCTF/floatctf-content
```

并创建：

```text
challenges/
gameboxes/
events/<event-id>.toml
```

## 4. 开发

将 Challenge 和 GameBox 分别放入：

```text
challenges/
gameboxes/
```

每个子目录必须包含：

```text
meta.toml
```

`meta.toml` 字段见 [Content Metadata](#content-metadata)。

内容发生变化后运行：

```bash
./scripts/sync-event.sh
```

脚本会自动：

- 校验 `meta.toml`（`scripts/content.py validate`）
- 扫描 `challenges/`
- 扫描 `gameboxes/`
- 更新 `events/<event-id>.toml`
- 生成 `docs/<event-id>.md`

然后正常提交：

```bash
git add .
git commit -m "..."
git push
```

## 5. 发布

比赛结束并确认可以公开后：

```bash
./scripts/publish.sh
```

脚本会发布到：

```text
floatctf-content:event/freshcup-2027
```

并创建合并到：

```text
floatctf-content:main
```

的 Pull Request。

> 比赛公开前，只向 `origin` 推送，不要向 `upstream` 推送。

## Content Metadata

`meta.toml` 是 Challenge / GameBox 的唯一元数据来源，同时用于：

- `catalog.json`
- Docker Image 的 OCI / FloatCTF Labels

目录名即内容 ID（例如 `challenges/comment/` → `comment`），
不需要在 `meta.toml` 中额外声明 `id`。
Challenge 与 GameBox 允许使用相同 ID，因为镜像 tag 不同。

```toml
name = "comment"
version = "1.0.0"
author = "fb0sh@outlook.com"
category = "web"
difficulty = "easy"
tags = ["php", "web"]
description = "注释里面有什么？"

[flag]
type = "dynamic"

[docker]
port = 80

[docker.recommended_resources]
cpu_millis = 500
memory_bytes = 268435456
pids_limit = 100
```

必填字段：

```text
name  version  author  category  difficulty  tags  description
```

新增字段：

| 字段 | 说明 |
|------|------|
| `difficulty` | `unknown` / `beginner` / `easy` / `medium` / `hard` / `expert` |
| `tags` | 字符串数组，可以为空数组，每项必须是非空字符串 |

- `version` 使用 `x.y.z`（SemVer），例如 `1.0.0`。
- `category` 不限制取值，现有内容使用 `ai` / `crypto` / `misc` / `pwn` / `reverse` / `web`。
- 旧内容已统一补充 `difficulty = "unknown"` 与 `tags = []`；
  `unknown` 仅用于兼容，新内容请填写真实难度。
- `events` 关系由 `events/*.toml` 自动反向生成，不要在 `meta.toml` 中手工维护。

校验整个仓库：

```bash
python3 scripts/content.py validate
```

## Official Images

镜像名规则只在 `scripts/content.py` 中实现，不要在别处重新拼接：

```text
Challenge: floatctf/{id}:challenge-v{version}
GameBox:   floatctf/{id}:gamebox-v{version}
```

例如：

```text
floatctf/comment:challenge-v1.0.0
```

Challenge 的构建上下文固定为 `challenges/{id}/src`，Dockerfile 为
`challenges/{id}/src/Dockerfile`；GameBox 同理使用 `gameboxes/{id}/src`。

本地查看某个内容的镜像信息（镜像名、构建上下文、Labels）：

```bash
python3 scripts/content.py image-meta challenges/comment
```

## Catalog

`catalog.json` 是自动生成的官方题库索引，由 GitHub Actions 在 `main`
分支上重新生成并提交。平台可以直接读取：

```text
https://raw.githubusercontent.com/FloatCTF/floatctf-content/main/catalog.json
```

本地重新生成与校验：

```bash
python3 scripts/content.py catalog
python3 scripts/content.py catalog --check
```

> **catalog.json is generated. Do not edit it manually.**

提交到 `main` 的原因：Git 历史可追踪、`raw.githubusercontent.com` 直接访问、
不需要 GitHub Pages、本地开发也能查看。

## Publishing Flow

```text
Event private repo
  └─ ./scripts/sync-event.sh     # validate + 更新 event manifest / docs
  └─ ./scripts/publish.sh        # 推送到 upstream event/<event-id> 并创建 PR
        └─ Pull Request          # validate + catalog --check + docker build（不 push）
              └─ main            # 构建并推送变化的镜像到 Docker Hub
                    └─ catalog.json   # 自动重新生成并提交
                          └─ FloatCTF 平台读取 raw catalog.json
```

GitHub Actions 需要配置的 Secrets（仅 `main` 使用，PR 不会接触）：

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

手动触发（`workflow_dispatch`）：

- `build_all = false`：只执行 validate 与 catalog。
- `build_all = true`：构建并推送所有带 Dockerfile 的 Challenge / GameBox，
  然后重新生成 `catalog.json`。

