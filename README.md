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

`meta.toml` 是 Challenge / GameBox 的唯一元数据来源，用于生成 `catalog.json`。

```text
meta.toml
    ↓
scripts/content.py
    ↓
catalog.json
    ↓
FloatCTF Platform
```

本仓库只负责元数据校验与 Catalog 生成，**不负责构建、发布或验证镜像**。

三个概念要区分清楚：

| 概念 | 来源 | 用途 |
|------|------|------|
| `id` | 目录名 | FloatCTF 内部稳定 ID，Event 引用、catalog 中的 `id` |
| `name` | `meta.toml` | UI 显示名称 |
| `safe_name` | `meta.toml`（可选） | Docker repository 名，用于 catalog 中的 image 引用 |

`id` 不需要在 `meta.toml` 中声明，Challenge 与 GameBox 允许使用相同 `id`
与相同 `safe_name`，因为 image tag（`challenge-v*` / `gamebox-v*`）不同。

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

## Image Reference

Catalog 中的 `image` 只是**规范化的引用**，由 `scripts/content.py` 生成，
供 FloatCTF 平台使用。本仓库不构建、不推送、不验证该镜像：

```text
Challenge: floatctf/{safe_name}:challenge-v{version}
GameBox:   floatctf/{safe_name}:gamebox-v{version}
```

例如：

```text
floatctf/comment:challenge-v1.0.0
floatctf/cirnos-perfect-math-class:challenge-v1.0.0
```

**只有存在 `src/Dockerfile` 的内容才有 `image`**：

```text
challenges/<id>/src/Dockerfile 存在  → Catalog 包含 image
不存在（附件题 static / attachment） → 仍然进入 Catalog，只是没有 image
```

不检查 Docker Hub 是否已有该镜像、本地是否能构建、tag 是否存在，也不做
pull / push。

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
        └─ Pull Request          # validate + catalog 生成测试 + unittest
              └─ main            # validate + unittest + 重新生成 catalog.json
                    └─ catalog.json   # 有变化时由 github-actions[bot] 自动提交
                          └─ FloatCTF 平台读取 raw catalog.json
```

- Pull Request：`validate` → `catalog --output`（不修改工作树）→ unittest。
  不要求 `catalog.json` 已经是最新。
- `main`（push 或 `workflow_dispatch`）：`validate` + unittest 通过后重新生成
  `catalog.json`，有变化时用 `github-actions[bot]` 提交
  `chore: update catalog [skip ci]`。
- 只有 `main` 会提交 catalog；PR 与其他分支不会。
- Action 不登录任何 Registry、不构建镜像、不需要任何 Secret。


