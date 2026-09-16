#!/usr/bin/env python3
"""FloatCTF content metadata, catalog and container image helper.

This module is the single source of truth for:

* content ids, types and versions (``meta.toml``)
* Docker image references and OCI / FloatCTF labels
* ``catalog.json``
* changed content detection for CI

Only the Python standard library (3.11+) is required.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, NoReturn, Sequence

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHALLENGES_DIR = "challenges"
GAMEBOXES_DIR = "gameboxes"
EVENTS_DIR = "events"

CONTENT_CHALLENGE = "challenge"
CONTENT_GAMEBOX = "gamebox"

CONTENT_DIRS: dict[str, str] = {
    CONTENT_CHALLENGE: CHALLENGES_DIR,
    CONTENT_GAMEBOX: GAMEBOXES_DIR,
}

CATALOG_FILE = "catalog.json"
CATALOG_VERSION = 1

IMAGE_NAMESPACE = "floatctf"
IMAGE_VENDOR = "FloatCTF"
IMAGE_SOURCE = "https://github.com/FloatCTF/floatctf-content"

SOURCE_SUBDIR = "src"
DOCKERFILE_NAME = "Dockerfile"

VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

#: Valid Docker repository name used as ``floatctf/<safe_name>``.
SAFE_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")

DIFFICULTIES: tuple[str, ...] = (
    "unknown",
    "beginner",
    "easy",
    "medium",
    "hard",
    "expert",
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "version",
    "author",
    "category",
    "difficulty",
    "tags",
    "description",
)

TEXT_FIELDS: tuple[str, ...] = (
    "name",
    "author",
    "category",
    "description",
)

POSITIVE_RESOURCE_FIELDS: tuple[str, ...] = (
    "cpu_millis",
    "memory_bytes",
    "pids_limit",
)

PORT_MIN = 1
PORT_MAX = 65535

#: GitHub Actions output name used by ``changed --github-output``.
GITHUB_PATHS_OUTPUT = "paths"

#: Delimiter used for multi-line GitHub Actions outputs.
GITHUB_OUTPUT_DELIMITER = "EOF"


class ContentError(Exception):
    """A user facing content problem."""


# ---------------------------------------------------------------------------
# Docker safe names
# ---------------------------------------------------------------------------


def derive_safe_name(content_id: str) -> str:
    """Derive a Docker repository name from a content id.

    ``Cirno's perfect math class`` becomes ``cirnos-perfect-math-class``.
    Returns an empty string when nothing usable is left, in which case the
    content must set ``safe_name`` explicitly.
    """

    name = content_id.lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(char for char in name if not unicodedata.combining(char))
    name = name.replace("'", "").replace("\u2019", "")
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"[._-]{2,}", "-", name)
    name = name.strip("._-")

    if not SAFE_NAME_PATTERN.match(name):
        return ""

    return name


def explicit_safe_name(meta: dict[str, Any]) -> str | None:
    """Return the explicit ``safe_name`` when it is a usable string."""

    value = meta.get("safe_name")

    if isinstance(value, str) and value.strip():
        return value.strip()

    return None


def dockerfile_path(content: "Content", root: Path) -> Path:
    """Return the Dockerfile path of *content* below *root*."""

    return root / content.path / SOURCE_SUBDIR / DOCKERFILE_NAME


def has_dockerfile(content: "Content", root: Path) -> bool:
    """True when *content* is a container (``src/Dockerfile`` exists)."""

    return dockerfile_path(content, root).is_file()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass
class Content:
    """One challenge or gamebox directory."""

    id: str
    type: str  # CONTENT_CHALLENGE | CONTENT_GAMEBOX
    path: Path  # e.g. challenges/comment
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.meta.get("version", ""))

    @property
    def safe_name(self) -> str:
        """Docker repository name: explicit ``safe_name`` or derived from id."""

        return explicit_safe_name(self.meta) or derive_safe_name(self.id)

    @property
    def meta_path(self) -> Path:
        return self.path / "meta.toml"


@dataclass
class Event:
    """One event manifest (``events/<id>.toml``)."""

    id: str
    path: Path
    meta: dict[str, Any] = field(default_factory=dict)
    challenges: list[str] = field(default_factory=list)
    gameboxes: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Outcome of :func:`validate`."""

    challenges: list[Content] = field(default_factory=list)
    gameboxes: list[Content] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _display(path: Path, root: Path) -> str:
    """Render *path* relative to *root* when possible."""

    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _report(errors: list[str] | None, message: str) -> None:
    """Collect *message* or raise it when no collector is provided."""

    if errors is None:
        raise ContentError(message)
    errors.append(message)


def _label_text(value: Any) -> str:
    """Collapse whitespace so a value is safe for a Docker label."""

    return " ".join(str(value).split())


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_meta(path: Path) -> dict[str, Any]:
    """Parse a TOML file, raising :class:`ContentError` on failure."""

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ContentError(f"{path.as_posix()}: file not found") from exc
    except IsADirectoryError as exc:
        raise ContentError(f"{path.as_posix()}: expected a file") from exc
    except OSError as exc:
        raise ContentError(f"{path.as_posix()}: cannot read file: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ContentError(f"{path.as_posix()}: invalid TOML: {exc}") from exc

    if not isinstance(data, dict):
        raise ContentError(f"{path.as_posix()}: expected a TOML table")

    return data


def _content_dirs(base: Path) -> list[Path]:
    if not base.is_dir():
        return []

    return sorted(
        (
            entry
            for entry in base.iterdir()
            if entry.is_dir() and not entry.name.startswith(".")
        ),
        key=lambda entry: entry.name,
    )


def scan_contents(
    root: Path,
    content_type: str,
    errors: list[str] | None = None,
) -> list[Content]:
    """Scan ``challenges/`` or ``gameboxes/`` and return entries sorted by id."""

    if content_type not in CONTENT_DIRS:
        raise ValueError(f"unknown content type: {content_type}")

    base = root / CONTENT_DIRS[content_type]
    contents: list[Content] = []
    seen: dict[str, Path] = {}

    for directory in _content_dirs(base):
        meta_path = directory / "meta.toml"

        if not meta_path.is_file():
            _report(errors, f"{_display(meta_path, root)}: missing meta.toml")
            continue

        try:
            meta = load_meta(meta_path)
        except ContentError as exc:
            _report(errors, str(exc))
            continue

        if directory.name in seen:
            _report(
                errors,
                f"{_display(meta_path, root)}: duplicate {content_type} id "
                f"'{directory.name}' (already used by "
                f"{_display(seen[directory.name], root)})",
            )
        else:
            seen[directory.name] = meta_path

        contents.append(
            Content(
                id=directory.name,
                type=content_type,
                path=directory,
                meta=meta,
            )
        )

    return sorted(contents, key=lambda content: content.id)


def _event_reference_array(
    meta: dict[str, Any],
    key: str,
    display: str,
    errors: list[str] | None,
) -> list[str]:
    content = meta.get("content")

    if content is None:
        return []

    if not isinstance(content, dict):
        _report(errors, f"{display}: [content] must be a table")
        return []

    values = content.get(key, [])

    if not isinstance(values, list) or any(
        not isinstance(value, str) or not value.strip() for value in values
    ):
        _report(
            errors,
            f"{display}: [content].{key} must be an array of non-empty strings",
        )
        return []

    return [value.strip() for value in values]


def load_events(root: Path, errors: list[str] | None = None) -> list[Event]:
    """Load ``events/*.toml`` sorted by event id."""

    base = root / EVENTS_DIR

    if not base.is_dir():
        return []

    events: list[Event] = []

    for path in sorted(base.glob("*.toml"), key=lambda item: item.name):
        display = _display(path, root)

        try:
            meta = load_meta(path)
        except ContentError as exc:
            _report(errors, str(exc))
            continue

        raw_id = meta.get("id")

        if not isinstance(raw_id, str) or not raw_id.strip():
            _report(errors, f"{display}: missing field 'id'")
            continue

        event_id = raw_id.strip()

        if event_id != path.stem:
            _report(
                errors,
                f"{display}: id must match file name '{path.stem}'",
            )

        events.append(
            Event(
                id=event_id,
                path=path,
                meta=meta,
                challenges=_event_reference_array(
                    meta, "challenges", display, errors
                ),
                gameboxes=_event_reference_array(
                    meta, "gameboxes", display, errors
                ),
            )
        )

    return sorted(events, key=lambda event: event.id)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_meta(content: Content, root: Path) -> list[str]:
    """Return every metadata problem for a single content entry."""

    meta = content.meta
    display = _display(content.meta_path, root)
    errors: list[str] = []

    for name in REQUIRED_FIELDS:
        if name not in meta:
            errors.append(f"{display}: missing field '{name}'")

    for name in TEXT_FIELDS:
        if name in meta and (
            not isinstance(meta[name], str) or not meta[name].strip()
        ):
            errors.append(f"{display}: field '{name}' must be a non-empty string")

    if "version" in meta:
        version = meta["version"]
        if not isinstance(version, str) or not VERSION_PATTERN.match(version):
            errors.append(
                f"{display}: invalid version {version!r} (expected x.y.z)"
            )

    if "difficulty" in meta:
        difficulty = meta["difficulty"]
        if not isinstance(difficulty, str) or difficulty not in DIFFICULTIES:
            errors.append(
                f"{display}: invalid difficulty {difficulty!r} "
                f"(expected one of {', '.join(DIFFICULTIES)})"
            )

    if "tags" in meta:
        tags = meta["tags"]
        if not isinstance(tags, list):
            errors.append(
                f"{display}: field 'tags' must be an array of non-empty strings"
            )
        elif any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            errors.append(
                f"{display}: field 'tags' must be an array of non-empty strings"
            )

    if "safe_name" in meta:
        safe_name = explicit_safe_name(meta)

        if safe_name is None or not SAFE_NAME_PATTERN.match(safe_name):
            errors.append(f"{display}: invalid safe_name {meta['safe_name']!r}")
    elif not derive_safe_name(content.id):
        errors.append(
            f"{display}: unable to derive Docker safe_name; "
            f"set safe_name explicitly"
        )

    docker = meta.get("docker")

    if docker is not None:
        if not isinstance(docker, dict):
            errors.append(f"{display}: field 'docker' must be a table")
        else:
            port = docker.get("port")

            if port is not None and (
                not _is_plain_int(port) or not PORT_MIN <= port <= PORT_MAX
            ):
                errors.append(
                    f"{display}: invalid docker.port {port!r} "
                    f"(expected {PORT_MIN}..{PORT_MAX})"
                )

            resources = docker.get("recommended_resources")

            if resources is not None:
                if not isinstance(resources, dict):
                    errors.append(
                        f"{display}: field 'docker.recommended_resources' "
                        f"must be a table"
                    )
                else:
                    for name in POSITIVE_RESOURCE_FIELDS:
                        value = resources.get(name)
                        if value is None:
                            continue
                        if not _is_positive_int(value):
                            errors.append(
                                f"{display}: invalid "
                                f"docker.recommended_resources.{name} "
                                f"{value!r} (expected a positive integer)"
                            )

    return errors


def _duplicate_values(values: Sequence[str]) -> list[str]:
    """Return the values that occur more than once, sorted."""

    seen: set[str] = set()
    duplicates: set[str] = set()

    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)

    return sorted(duplicates)


def _safe_name_errors(contents: Sequence[Content]) -> list[str]:
    """Return duplicate Docker safe_name errors for one content type."""

    grouped: dict[str, list[Content]] = {}

    for content in contents:
        safe_name = content.safe_name

        # Invalid or underivable names are already reported by validate_meta.
        if safe_name and SAFE_NAME_PATTERN.match(safe_name):
            grouped.setdefault(safe_name, []).append(content)

    errors: list[str] = []

    for safe_name, items in sorted(grouped.items()):
        if len(items) < 2:
            continue

        names = "' and '".join(sorted(item.id for item in items))
        errors.append(
            f"duplicate {items[0].type} safe_name '{safe_name}': '{names}'"
        )

    return errors


def validate(root: Path) -> ValidationResult:
    """Validate all content and events below *root*."""

    errors: list[str] = []

    challenges = scan_contents(root, CONTENT_CHALLENGE, errors)
    gameboxes = scan_contents(root, CONTENT_GAMEBOX, errors)

    for content in (*challenges, *gameboxes):
        errors.extend(validate_meta(content, root))

    # Safe names must be unique per content type; a challenge and a gamebox may
    # share one because their image tags differ.
    errors.extend(_safe_name_errors(challenges))
    errors.extend(_safe_name_errors(gameboxes))

    events = load_events(root, errors)

    challenge_ids = {content.id for content in challenges}
    gamebox_ids = {content.id for content in gameboxes}

    for event in events:
        display = _display(event.path, root)

        for reference in _duplicate_values(event.challenges):
            errors.append(f"{display}: duplicate challenge '{reference}'")

        for reference in _duplicate_values(event.gameboxes):
            errors.append(f"{display}: duplicate gamebox '{reference}'")

        for reference in event.challenges:
            if reference not in challenge_ids:
                errors.append(f"{display}: unknown challenge '{reference}'")

        for reference in event.gameboxes:
            if reference not in gamebox_ids:
                errors.append(f"{display}: unknown gamebox '{reference}'")

    return ValidationResult(
        challenges=challenges,
        gameboxes=gameboxes,
        events=events,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def image_ref(content: Content) -> str:
    """Return ``floatctf/{safe_name}:{type}-v{version}``."""

    safe_name = content.safe_name

    if not safe_name:
        raise ContentError(
            f"{content.meta_path.as_posix()}: unable to derive Docker "
            f"safe_name; set safe_name explicitly"
        )

    if not SAFE_NAME_PATTERN.match(safe_name):
        raise ContentError(
            f"{content.meta_path.as_posix()}: invalid safe_name {safe_name!r}"
        )

    return (
        f"{IMAGE_NAMESPACE}/{safe_name}"
        f":{content.type}-v{content.version}"
    )


def image_context(content: Content) -> tuple[str, str]:
    """Return the Docker build context and Dockerfile paths, relative to root."""

    context = content.path / SOURCE_SUBDIR
    dockerfile = context / DOCKERFILE_NAME

    return context.as_posix(), dockerfile.as_posix()


def ensure_dockerfile(content: Content, root: Path) -> str:
    """Return the Dockerfile path or raise :class:`ContentError`."""

    _, dockerfile = image_context(content)

    if not (root / dockerfile).is_file():
        raise ContentError(
            f"{content.path.as_posix()}: Dockerfile not found: {dockerfile}"
        )

    return dockerfile


def image_labels(content: Content, revision: str | None = None) -> dict[str, str]:
    """Return the OCI / FloatCTF labels for *content*."""

    meta = content.meta
    tags = meta.get("tags")

    if not isinstance(tags, list):
        tags = []

    labels = {
        "org.opencontainers.image.title": _label_text(
            meta.get("name", content.id)
        ),
        "org.opencontainers.image.description": _label_text(
            meta.get("description", "")
        ),
        "org.opencontainers.image.version": _label_text(content.version),
        "org.opencontainers.image.vendor": IMAGE_VENDOR,
        "org.opencontainers.image.source": IMAGE_SOURCE,
        "io.floatctf.type": content.type,
        "io.floatctf.id": content.id,
        "io.floatctf.category": _label_text(meta.get("category", "")),
        "io.floatctf.difficulty": _label_text(meta.get("difficulty", "")),
        "io.floatctf.version": _label_text(content.version),
        "io.floatctf.tags": ",".join(_label_text(tag) for tag in tags),
    }

    revision = revision or os.environ.get("GITHUB_SHA") or ""

    if revision.strip():
        labels["org.opencontainers.image.revision"] = revision.strip()

    return labels


def load_content(root: Path, path: str) -> Content:
    """Load one ``challenges/<id>`` or ``gameboxes/<id>`` directory."""

    candidate = Path(path.strip().rstrip("/"))

    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(root)
        except ValueError:
            raise ContentError(
                f"{path}: must live inside the repository root"
            ) from None

    parts = candidate.parts

    if len(parts) != 2 or parts[0] not in CONTENT_DIRS.values():
        raise ContentError(
            f"{path}: expected challenges/<id> or gameboxes/<id>"
        )

    content_type = (
        CONTENT_CHALLENGE if parts[0] == CHALLENGES_DIR else CONTENT_GAMEBOX
    )
    directory = root / parts[0] / parts[1]
    meta_path = directory / "meta.toml"

    if not directory.is_dir():
        raise ContentError(f"{path}: directory not found")

    if not meta_path.is_file():
        raise ContentError(f"{_display(meta_path, root)}: missing meta.toml")

    content = Content(
        id=parts[1],
        type=content_type,
        path=Path(parts[0]) / parts[1],
        meta=load_meta(meta_path),
    )

    errors = validate_meta(content, root)

    if errors:
        raise ContentError(errors[0])

    ensure_dockerfile(content, root)

    return content


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def _event_index(events: Sequence[Event], attribute: str) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}

    for event in events:
        for reference in getattr(event, attribute):
            index.setdefault(reference, []).append(event.id)

    return {
        key: sorted(set(values))
        for key, values in index.items()
    }


def _flag_entry(meta: dict[str, Any]) -> dict[str, Any] | None:
    """Expose the flag *type* only; values never belong in the catalog."""

    flag = meta.get("flag")

    if not isinstance(flag, dict):
        return None

    entry: dict[str, Any] = {}

    if isinstance(flag.get("type"), str):
        entry["type"] = flag["type"]

    return entry or None


def _docker_entry(meta: dict[str, Any]) -> dict[str, Any] | None:
    docker = meta.get("docker")

    if not isinstance(docker, dict):
        return None

    entry: dict[str, Any] = {}

    if _is_plain_int(docker.get("port")):
        entry["port"] = docker["port"]

    resources = docker.get("recommended_resources")

    if isinstance(resources, dict):
        selected = {
            name: resources[name]
            for name in POSITIVE_RESOURCE_FIELDS
            if _is_positive_int(resources.get(name))
        }
        if selected:
            entry["recommended_resources"] = selected

    return entry or None


def content_entry(
    content: Content,
    event_ids: Sequence[str],
    root: Path,
) -> dict[str, Any]:
    """Build the catalog entry for one challenge or gamebox."""

    meta = content.meta

    entry: dict[str, Any] = {
        "id": content.id,
        "name": meta.get("name", content.id),
        "version": content.version,
        "author": meta.get("author", ""),
        "category": meta.get("category", ""),
        "difficulty": meta.get("difficulty", ""),
        "tags": list(meta.get("tags", [])),
        "description": meta.get("description", ""),
    }

    # Only container content publishes an image; attachment-only content is
    # simply served without one.
    if has_dockerfile(content, root):
        entry["image"] = image_ref(content)

    flag = _flag_entry(meta)

    if flag is not None:
        entry["flag"] = flag

    docker = _docker_entry(meta)

    if docker is not None:
        entry["docker"] = docker

    entry["events"] = sorted(set(event_ids))

    return entry


def event_entry(event: Event) -> dict[str, Any]:
    """Build the catalog entry for one event."""

    meta = event.meta

    return {
        "id": event.id,
        "title": meta.get("title", ""),
        "description": meta.get("description", ""),
        "started_at": meta.get("started_at", ""),
        "ended_at": meta.get("ended_at", ""),
        "challenges": sorted(set(event.challenges)),
        "gameboxes": sorted(set(event.gameboxes)),
    }


def build_catalog(root: Path) -> dict[str, Any]:
    """Build the catalog data structure (deterministic)."""

    challenges = scan_contents(root, CONTENT_CHALLENGE)
    gameboxes = scan_contents(root, CONTENT_GAMEBOX)
    events = load_events(root)

    challenge_events = _event_index(events, "challenges")
    gamebox_events = _event_index(events, "gameboxes")

    return {
        "version": CATALOG_VERSION,
        "challenges": [
            content_entry(content, challenge_events.get(content.id, []), root)
            for content in sorted(challenges, key=lambda item: item.id)
        ],
        "gameboxes": [
            content_entry(content, gamebox_events.get(content.id, []), root)
            for content in sorted(gameboxes, key=lambda item: item.id)
        ],
        "events": [
            event_entry(event)
            for event in sorted(events, key=lambda item: item.id)
        ],
    }


def render_catalog(catalog: dict[str, Any]) -> str:
    """Serialize a catalog exactly the way it is committed."""

    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Changed content detection
# ---------------------------------------------------------------------------


def content_paths(names: Iterable[str]) -> list[str]:
    """Map changed file paths to content directories (unique, sorted)."""

    found: set[str] = set()

    for name in names:
        parts = Path(name).parts

        if len(parts) < 2:
            continue

        if parts[0] in CONTENT_DIRS.values() and parts[1]:
            found.add(f"{parts[0]}/{parts[1]}")

    return sorted(found)


def _git_diff_names(root: Path, base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "-z", base, head],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContentError(
            f"git diff {base} {head} failed"
            + (f": {message}" if message else "")
        )

    output = result.stdout.decode("utf-8", errors="replace")

    return [name for name in output.split("\0") if name]


def _all_content_paths(root: Path) -> list[str]:
    paths: list[str] = []

    for content_type in CONTENT_DIRS:
        for content in scan_contents(root, content_type):
            paths.append(f"{CONTENT_DIRS[content_type]}/{content.id}")

    return sorted(set(paths))


def _is_zero_sha(value: str) -> bool:
    return bool(value) and set(value) <= {"0"}


def find_changed(
    root: Path,
    base: str | None = None,
    head: str | None = None,
    *,
    all_content: bool = False,
    dockerfile_only: bool = False,
) -> list[str]:
    """Return content directories touched between *base* and *head*."""

    if all_content:
        paths = _all_content_paths(root)
    else:
        if not base or not head:
            raise ContentError("changed requires --base and --head, or --all")

        if _is_zero_sha(base):
            # First push of a branch: everything is new.
            paths = _all_content_paths(root)
        else:
            paths = [
                path
                for path in content_paths(_git_diff_names(root, base, head))
                if (root / path).is_dir()
            ]

    if dockerfile_only:
        paths = [
            path
            for path in paths
            if (root / path / SOURCE_SUBDIR / DOCKERFILE_NAME).is_file()
        ]

    return sorted(set(paths))


# ---------------------------------------------------------------------------
# GitHub Actions output
# ---------------------------------------------------------------------------


def write_github_output(path: str, values: dict[str, str]) -> None:
    """Append step outputs to a ``$GITHUB_OUTPUT`` file.

    Multi-line values use the documented heredoc form so that e.g. the
    ``labels`` output of ``image-meta`` can be fed to
    ``docker/build-push-action`` unchanged.
    """

    with open(path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value or "\r" in value:
                handle.write(
                    f"{key}<<{GITHUB_OUTPUT_DELIMITER}\n"
                    f"{value}\n"
                    f"{GITHUB_OUTPUT_DELIMITER}\n"
                )
            else:
                handle.write(f"{key}={value}\n")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def fail(message: str) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate(Path(args.root))

    if result.errors:
        for message in result.errors:
            print(f"error: {message}", file=sys.stderr)
        return 1

    print("Validated content:")
    print(f"  Challenges: {len(result.challenges)}")
    print(f"  GameBoxes: {len(result.gameboxes)}")
    print(f"  Events: {len(result.events)}")

    return 0


def cmd_catalog(args: argparse.Namespace) -> int:
    root = Path(args.root)

    # Never write a catalog derived from broken metadata.
    result = validate(root)

    if result.errors:
        for message in result.errors:
            print(f"error: {message}", file=sys.stderr)
        return 1

    rendered = render_catalog(build_catalog(root))

    if args.check:
        catalog_path = root / CATALOG_FILE
        current = (
            catalog_path.read_text(encoding="utf-8")
            if catalog_path.is_file()
            else None
        )

        if current != rendered:
            print(f"error: {CATALOG_FILE} is out of date", file=sys.stderr)
            print("run:", file=sys.stderr)
            print("  python3 scripts/content.py catalog", file=sys.stderr)
            return 1

        print(f"{CATALOG_FILE} is up to date")
        return 0

    target = Path(args.output) if args.output else root / CATALOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    print(f"Wrote {target.as_posix()}")

    return 0


def cmd_image_meta(args: argparse.Namespace) -> int:
    root = Path(args.root)
    content = load_content(root, args.path)
    context, dockerfile = image_context(content)

    meta = {
        "id": content.id,
        "type": content.type,
        "version": content.version,
        "image": image_ref(content),
        "context": context,
        "dockerfile": dockerfile,
        "labels": image_labels(content, args.revision),
    }

    if args.github_output:
        labels = "\n".join(
            f"{key}={value}" for key, value in meta["labels"].items()
        )
        write_github_output(
            args.github_output,
            {
                "id": meta["id"],
                "type": meta["type"],
                "version": meta["version"],
                "image": meta["image"],
                "context": meta["context"],
                "dockerfile": meta["dockerfile"],
                "labels": labels,
            },
        )

    print(json.dumps(meta, indent=2, ensure_ascii=False))

    return 0


def cmd_changed(args: argparse.Namespace) -> int:
    root = Path(args.root)
    paths = find_changed(
        root,
        args.base,
        args.head,
        all_content=args.all,
        dockerfile_only=args.dockerfile_only,
    )

    if args.github_output:
        write_github_output(
            args.github_output,
            {
                GITHUB_PATHS_OUTPUT: json.dumps(
                    paths, ensure_ascii=False, separators=(",", ":")
                )
            },
        )

    print(json.dumps(paths, indent=2, ensure_ascii=False))

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content.py",
        description="FloatCTF content metadata, catalog and image helper.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        parents=[common],
        help="validate challenges, gameboxes and events",
    )
    validate_parser.set_defaults(func=cmd_validate)

    catalog_parser = subparsers.add_parser(
        "catalog",
        parents=[common],
        help="generate catalog.json",
    )
    catalog_group = catalog_parser.add_mutually_exclusive_group()
    catalog_group.add_argument(
        "--check",
        action="store_true",
        help="fail when catalog.json is out of date instead of writing it",
    )
    catalog_group.add_argument(
        "--output",
        metavar="FILE",
        help="write the catalog to FILE (default: <root>/catalog.json)",
    )
    catalog_parser.set_defaults(func=cmd_catalog)

    image_parser = subparsers.add_parser(
        "image-meta",
        parents=[common],
        help="print image metadata for one content directory",
    )
    image_parser.add_argument("path", help="challenges/<id> or gameboxes/<id>")
    image_parser.add_argument(
        "--github-output",
        metavar="FILE",
        help="also append step outputs to a GitHub Actions output file",
    )
    image_parser.add_argument(
        "--revision",
        help="value for org.opencontainers.image.revision "
        "(default: $GITHUB_SHA)",
    )
    image_parser.set_defaults(func=cmd_image_meta)

    changed_parser = subparsers.add_parser(
        "changed",
        parents=[common],
        help="list content directories changed between two revisions",
    )
    changed_parser.add_argument("--base", help="base git revision")
    changed_parser.add_argument("--head", help="head git revision")
    changed_parser.add_argument(
        "--all",
        action="store_true",
        help="list every content directory instead of diffing",
    )
    changed_parser.add_argument(
        "--dockerfile-only",
        action="store_true",
        help="only list content that has a Dockerfile",
    )
    changed_parser.add_argument(
        "--github-output",
        metavar="FILE",
        help="also append step outputs to a GitHub Actions output file",
    )
    changed_parser.set_defaults(func=cmd_changed)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except ContentError as exc:
        fail(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
