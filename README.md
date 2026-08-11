# FloatCTF Event Content

用于开发一场 FloatCTF 比赛。

## 1. 创建私有仓库

先创建一个空的 Private Repository，例如：

```text
git@github.com:fb0sh/freshcup-2027.git
````

## 2. 克隆模板

```bash
git clone -b event/base --depth 1 --single-branch \
  git@github.com:FloatCTF/floatctf-content.git \
  freshcup-2027

cd freshcup-2027
```

目录名就是 Event ID，建议使用：

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

## 4. 开发

正常使用 Git：

```bash
git add .
git commit -m "..."
git push
```

比赛内容：

```text
challenges/   Challenge
gameboxes/    GameBox
events/       Event
```

## 5. 发布

比赛结束并确认可以公开后：

```bash
./scripts/publish.sh
```

脚本会将本场比赛发布到：

```text
event/freshcup-2027
```

并用于合并到：

```text
floatctf-content/main
```

> 比赛公开前，只向 `origin` 推送，不要向 `upstream` 推送。

