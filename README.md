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

三个概念要区分清楚：

| 概念 | 来源 | 用途 |
|------|------|------|
| `id` | 目录名 | FloatCTF 内部稳定 ID，Event 引用、catalog 中的 `id` |
| `name` | `meta.toml` | UI 显示名称 |
| `safe_name` | `meta.toml`（可选） | Docker repository 名（`floatctf/{safe_name}`） |

`id` 不需要在 `meta.toml` 中声明，Challenge 与 GameBox 允许使用相同 `id`
与相同 `safe_name`，因为镜像 tag（`challenge-v*` / `gamebox-v*`）不同。

```toml
name = "comment"
version = "1.0.0"
author = "fb0sh@outlook.com"
category = "web"
difficulty = "easy"
tags = ["php", "web"]
description = "注释里面有什么？"
# 可选；缺省由目录名派生
# safe_name = "comment"

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

字段说明：

| 字段 | 说明 |
|------|------|
| `difficulty` | `unknown` / `beginner` / `easy` / `medium` / `hard` / `expert` |
| `tags` | 字符串数组，可以为空数组，每项必须是非空字符串 |
| `safe_name` | 可选；Docker repository 名，必须匹配 `^[a-z0-9]+(?:[._-][a-z0-9]+)*$` |

- `version` 使用 `x.y.z`（SemVer），例如 `1.0.0`。
- `category` 不限制取值，现有内容使用 `ai` / `crypto` / `misc` / `pwn` / `reverse` / `web`。
- 旧内容已统一补充 `difficulty = "unknown"` 与 `tags = []`；
  `unknown` 仅用于兼容，新内容请填写真实难度。
- `events` 关系由 `events/*.toml` 自动反向生成，不要在 `meta.toml` 中手工维护。

### safe_name

`safe_name` 是 Docker repository 名，`id` 可以包含空格、大写、撇号甚至中文，
`safe_name` 必须始终是合法的 Docker repository 名。

没有显式写 `safe_name` 时，由**目录名**自动派生：

```text
comment                     → comment
Android_reverse             → android_reverse
FloatCTF-qidong             → floatctf-qidong
Cirno's perfect math class  → cirnos-perfect-math-class
```

派生规则：小写 → Unicode NFKD 归一化 → 删除撇号（`'` 与 `’`）→
非 `a-z0-9._-` 字符转成 `-` → 合并连续分隔符 → 去首尾 `. _ -`。

例如：

```text
challenges/Cirno's perfect math class/meta.toml

name = "Cirno's perfect math class"
safe_name = "cirnos-perfect-math-class"   # 可省略，自动派生结果相同
```

Catalog 中仍然是原始 `id`，只有 image 使用 `safe_name`：

```json
{
  "id": "Cirno's perfect math class",
  "image": "floatctf/cirnos-perfect-math-class:challenge-v1.0.0"
}
```

只有自动派生失败时才必须显式写 `safe_name`（例如全中文目录名）：

```toml
name = "题目"
safe_name = "challenge-001"
```

否则 `validate` 会报错：

```text
error: challenges/题目/meta.toml: unable to derive Docker safe_name; set safe_name explicitly
```

同一类型下 `safe_name` 不允许冲突（`challenges/Foo` 与 `challenges/foo`
都会派生成 `foo`，必须改名或显式指定）。

校验整个仓库：

```bash
python3 scripts/content.py validate
```

## Official Images

镜像名规则只在 `scripts/content.py` 中实现，不要在别处重新拼接：

```text
Challenge: floatctf/{safe_name}:challenge-v{version}
GameBox:   floatctf/{safe_name}:gamebox-v{version}
```

例如：

```text
floatctf/comment:challenge-v1.0.0
floatctf/cirnos-perfect-math-class:challenge-v1.0.0
```

构建上下文固定为 `challenges/{id}/src`（GameBox 为 `gameboxes/{id}/src`），
Dockerfile 固定为 `{context}/Dockerfile`，不支持自定义 context。

**只有存在 `src/Dockerfile` 的内容才有镜像**；附件题（static / attachment-only）
不会构建镜像，Catalog 中也不会出现 `image` 字段。

`version` 参与 tag 命名。同一个 tag 可以被重新构建并覆盖，例如
`floatctf/comment:challenge-v1.0.0` 再次发布会用新构建的镜像替换它。

只有以下变化会触发镜像构建：

```text
challenges/<id>/meta.toml
challenges/<id>/src/**
gameboxes/<id>/meta.toml
gameboxes/<id>/src/**
```

`README.md`、`attachment/**`、`solution/**`、`docs/**`、`events/**` 等变化
不会触发镜像构建。

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
python3 scripts/content.py catalog                       # 写入 ./catalog.json
python3 scripts/content.py catalog --output /tmp/c.json  # 写到别处，不动工作树
python3 scripts/content.py catalog --check               # 只检查是否最新
```

> **catalog.json is generated. Do not edit it manually.**

Catalog 只包含元数据，不包含 flag 值；只有带 `src/Dockerfile` 的内容才有
`image` 字段。

提交到 `main` 的原因：Git 历史可追踪、`raw.githubusercontent.com` 直接访问、
不需要 GitHub Pages、本地开发也能查看。

## Publishing Flow

```text
Event private repo
  └─ ./scripts/sync-event.sh     # validate + 更新 event manifest / docs
  └─ ./scripts/publish.sh        # 推送到 upstream event/<event-id> 并创建 PR
        └─ Pull Request          # validate + unittest + catalog 生成测试 + docker build（不 push）
              └─ main            # 构建并推送镜像到 Docker Hub
                    └─ catalog.json   # 自动重新生成并提交
                          └─ FloatCTF 平台读取 raw catalog.json
```

- 只有 `refs/heads/main` 上的 `push` / `workflow_dispatch` 会 push 镜像与提交
  `catalog.json`。
- Pull Request 与非 `main` 分支的手动触发只做 validate / 测试 / `docker build`，
  不登录 Docker Hub、不 push、不提交。

GitHub Actions 需要配置的 Secrets（仅 `main` 使用，PR 不会接触）：

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

手动触发（`workflow_dispatch`）：

- `build_all = false`：只执行 validate、unittest 与 catalog 生成测试；
  在 `main` 上还会刷新 `catalog.json`。
- `build_all = true`：构建所有带 Dockerfile 的 Challenge / GameBox；
  在 `main` 上会 push，在其他分支只 build。


