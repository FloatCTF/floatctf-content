#!/usr/bin/env bash

set -Eeuo pipefail

die() {
    echo "error: $*" >&2
    exit 1
}

git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
    die "not inside a git repository"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

EVENT="$(basename "$ROOT")"
EVENT_FILE="events/${EVENT}.toml"
DOC_FILE="docs/${EVENT}.md"

[[ -f "$EVENT_FILE" ]] ||
    die "event manifest not found: $EVENT_FILE"

command -v python3 >/dev/null 2>&1 ||
    die "python3 is required"

python3 - "$EVENT" "$EVENT_FILE" "$DOC_FILE" <<'PY'
from __future__ import annotations

import html
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        print(
            "error: Python 3.11+ or the 'tomli' package is required",
            file=sys.stderr,
        )
        sys.exit(1)


EVENT = sys.argv[1]
EVENT_FILE = Path(sys.argv[2])
DOC_FILE = Path(sys.argv[3])

BEGIN_MARKER = "# BEGIN GENERATED CONTENT"
END_MARKER = "# END GENERATED CONTENT"


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def load_toml(path: Path) -> dict:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception as exc:
        die(f"failed to parse {path}: {exc}")


def markdown_text(value) -> str:
    """Escape text used inside Markdown tables."""
    if value is None:
        return ""

    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = " ".join(line.strip() for line in text.splitlines())
    text = html.escape(text, quote=False)
    text = text.replace("|", r"\|")

    return text


def display_category(category: str) -> str:
    known = {
        "ai": "AI",
        "crypto": "Crypto",
        "misc": "Misc",
        "pwn": "Pwn",
        "reverse": "Reverse",
        "web": "Web",
    }

    category = category.strip()
    return known.get(category.lower(), category)


def scan_content(root: Path, kind: str) -> list[dict]:
    if not root.exists():
        return []

    result = []

    for directory in sorted(
        (p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda p: p.name.lower(),
    ):
        meta_path = directory / "meta.toml"

        if not meta_path.is_file():
            die(f"{kind} directory missing meta.toml: {directory}")

        data = load_toml(meta_path)

        required = [
            "name",
            "version",
            "author",
            "category",
            "description",
        ]

        missing = [
            field
            for field in required
            if field not in data or data[field] in (None, "")
        ]

        if missing:
            die(
                f"{meta_path}: missing required field(s): "
                + ", ".join(missing)
            )

        result.append(
            {
                "id": directory.name,
                "name": str(data["name"]),
                "version": str(data["version"]),
                "author": str(data["author"]),
                "category": display_category(str(data["category"])),
                "description": str(data["description"]),
                "meta_path": meta_path,
            }
        )

    # 文档首先按 category 排序，再按 name 排序
    result.sort(
        key=lambda x: (
            x["category"].lower(),
            x["name"].lower(),
            x["id"].lower(),
        )
    )

    return result


def toml_array(name: str, values: list[str]) -> list[str]:
    lines = [f"{name} = ["]

    for value in values:
        escaped = (
            value
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )
        lines.append(f'    "{escaped}",')

    lines.append("]")
    return lines


def update_event_manifest(
    challenges: list[dict],
    gameboxes: list[dict],
) -> None:
    text = EVENT_FILE.read_text(encoding="utf-8")

    if BEGIN_MARKER not in text or END_MARKER not in text:
        die(
            f"{EVENT_FILE}: generated content markers are missing"
        )

    block = [
        BEGIN_MARKER,
        "[content]",
        *toml_array(
            "challenges",
            sorted(item["id"] for item in challenges),
        ),
        "",
        *toml_array(
            "gameboxes",
            sorted(item["id"] for item in gameboxes),
        ),
        END_MARKER,
    ]

    generated = "\n".join(block)

    pattern = re.compile(
        rf"{re.escape(BEGIN_MARKER)}"
        rf".*?"
        rf"{re.escape(END_MARKER)}",
        re.DOTALL,
    )

    new_text, count = pattern.subn(generated, text, count=1)

    if count != 1:
        die(f"failed to update generated block in {EVENT_FILE}")

    if not new_text.endswith("\n"):
        new_text += "\n"

    EVENT_FILE.write_text(new_text, encoding="utf-8")


def category_summary(items: list[dict]) -> list[str]:
    counts = Counter(item["category"] for item in items)

    if not counts:
        return ["_暂无内容。_"]

    categories = sorted(counts, key=str.lower)

    header = "| 类别 | " + " | ".join(categories) + " |"
    separator = "|------|" + "|".join(
        "---:" for _ in categories
    ) + "|"
    values = "| 数量 | " + " | ".join(
        str(counts[category])
        for category in categories
    ) + " |"

    return [
        header,
        separator,
        values,
    ]


def content_table(
    items: list[dict],
    kind: str,
) -> list[str]:
    if not items:
        return ["_暂无内容。_"]

    rows = [
        "| 名称 | 分类 | 版本 | 作者 | 描述 |",
        "|------|------|------|------|------|",
    ]

    for item in items:
        directory = quote(item["id"], safe="")

        link = (
            f"../{kind}/{directory}/meta.toml"
        )

        name = markdown_text(item["name"])
        category = markdown_text(item["category"])
        version = markdown_text(item["version"])
        author = markdown_text(item["author"])
        description = markdown_text(item["description"])

        rows.append(
            f"| [{name}]({link}) "
            f"| {category} "
            f"| {version} "
            f"| {author} "
            f"| {description} |"
        )

    return rows


def generate_doc(
    event_meta: dict,
    challenges: list[dict],
    gameboxes: list[dict],
) -> None:
    title = str(event_meta.get("title", "")).strip()

    if not title:
        title = EVENT

    # Event title 建议填写：
    # title = "2025 FloatCTF 新生赛"
    #
    # 文档自动追加“题目仓库”
    heading = f"{title}题目仓库"

    lines = [
        f"# {heading}",
        "",
        "> 此文件由 `scripts/sync-event.sh` 自动生成，请勿手动修改。",
        "",
        "## Category Summary",
        "",
        "### Challenges",
        "",
        *category_summary(challenges),
        "",
        "### GameBoxes",
        "",
        *category_summary(gameboxes),
        "",
        "## Challenges",
        "",
        *content_table(challenges, "challenges"),
        "",
        "## GameBoxes",
        "",
        *content_table(gameboxes, "gameboxes"),
        "",
    ]

    DOC_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOC_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


event_meta = load_toml(EVENT_FILE)

if str(event_meta.get("id", "")) != EVENT:
    die(
        f"{EVENT_FILE}: id must match repository directory name "
        f"('{EVENT}')"
    )

challenges = scan_content(Path("challenges"), "challenge")
gameboxes = scan_content(Path("gameboxes"), "gamebox")

update_event_manifest(challenges, gameboxes)
generate_doc(event_meta, challenges, gameboxes)

print(f"Synced event: {EVENT}")
print(f"  Challenges: {len(challenges)}")
print(f"  GameBoxes:  {len(gameboxes)}")
print(f"  Manifest:   {EVENT_FILE}")
print(f"  Document:   {DOC_FILE}")
PY
