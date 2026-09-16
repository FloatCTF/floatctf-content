#!/usr/bin/env python3
"""Unit tests for ``scripts/content.py``.

Run with::

    python3 -m unittest discover -s scripts/tests -v

The tests only use fixtures below ``scripts/tests/fixtures``; production
content is never required.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
VALID_FIXTURE = FIXTURES_DIR / "valid"
INVALID_FIXTURE = FIXTURES_DIR / "invalid"


def _load_content_module():
    spec = importlib.util.spec_from_file_location(
        "floatctf_content", SCRIPTS_DIR / "content.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["floatctf_content"] = module
    spec.loader.exec_module(module)
    return module


content = _load_content_module()


def quiet(function, *args, **kwargs):
    """Call *function* while swallowing stdout/stderr."""

    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            return function(*args, **kwargs)


def copy_fixture(fixture: Path, destination: Path) -> Path:
    shutil.copytree(fixture, destination, dirs_exist_ok=True)
    return destination


# ---------------------------------------------------------------------------
# 1. image naming
# ---------------------------------------------------------------------------


class ImageRefTests(unittest.TestCase):
    def _content(self, content_type: str, version: str = "1.0.0"):
        return content.Content(
            id="comment",
            type=content_type,
            path=Path("challenges/comment"),
            meta={"version": version},
        )

    def test_challenge_image_ref(self) -> None:
        self.assertEqual(
            content.image_ref(self._content(content.CONTENT_CHALLENGE)),
            "floatctf/comment:challenge-v1.0.0",
        )

    def test_gamebox_image_ref(self) -> None:
        self.assertEqual(
            content.image_ref(self._content(content.CONTENT_GAMEBOX, "1.2.0")),
            "floatctf/comment:gamebox-v1.2.0",
        )

    def test_image_ref_from_fixture(self) -> None:
        challenges = content.scan_contents(
            VALID_FIXTURE, content.CONTENT_CHALLENGE
        )
        gameboxes = content.scan_contents(VALID_FIXTURE, content.CONTENT_GAMEBOX)

        self.assertEqual(
            [content.image_ref(item) for item in challenges],
            [
                "floatctf/comment:challenge-v1.0.0",
                "floatctf/cookie:challenge-v1.0.0",
            ],
        )
        self.assertEqual(
            [content.image_ref(item) for item in gameboxes],
            ["floatctf/comment:gamebox-v1.0.0"],
        )

    def test_image_metadata_paths(self) -> None:
        challenge = content.load_content(VALID_FIXTURE, "challenges/comment")
        gamebox = content.load_content(VALID_FIXTURE, "gameboxes/comment")

        self.assertEqual(
            content.image_context(challenge),
            ("challenges/comment/src", "challenges/comment/src/Dockerfile"),
        )
        self.assertEqual(
            content.image_context(gamebox),
            ("gameboxes/comment/src", "gameboxes/comment/src/Dockerfile"),
        )

    def test_image_meta_requires_dockerfile(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            quiet(
                content.main,
                ["image-meta", "challenges/cookie", "--root", str(VALID_FIXTURE)],
            )

        self.assertEqual(raised.exception.code, 1)


# ---------------------------------------------------------------------------
# 2 - 5. validation
# ---------------------------------------------------------------------------


class ValidateTests(unittest.TestCase):
    def errors(self, root: Path) -> list[str]:
        return content.validate(root).errors

    def test_valid_fixture(self) -> None:
        result = content.validate(VALID_FIXTURE)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(len(result.challenges), 2)
        self.assertEqual(len(result.gameboxes), 1)
        self.assertEqual(len(result.events), 1)

    def test_missing_field(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_missing_difficulty/meta.toml: "
            "missing field 'difficulty'",
            errors,
        )

    def test_invalid_version(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_version/meta.toml: "
            "invalid version '1.0' (expected x.y.z)",
            errors,
        )

    def test_invalid_difficulty(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_difficulty/meta.toml: "
            "invalid difficulty 'impossible' "
            "(expected one of unknown, beginner, easy, medium, hard, expert)",
            errors,
        )

    def test_invalid_port(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_docker/meta.toml: "
            "invalid docker.port 70000 (expected 1..65535)",
            errors,
        )

    def test_invalid_tags(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_docker/meta.toml: "
            "field 'tags' must be an array of non-empty strings",
            errors,
        )

    def test_invalid_recommended_resources(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_docker/meta.toml: "
            "invalid docker.recommended_resources.cpu_millis 0 "
            "(expected a positive integer)",
            errors,
        )
        self.assertIn(
            "challenges/broken_docker/meta.toml: "
            "invalid docker.recommended_resources.pids_limit -1 "
            "(expected a positive integer)",
            errors,
        )

    def test_missing_meta_toml(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "challenges/broken_no_meta/meta.toml: missing meta.toml",
            errors,
        )

    def test_unknown_event_references(self) -> None:
        errors = self.errors(INVALID_FIXTURE)

        self.assertIn(
            "events/freshcup.toml: unknown challenge 'ghost'",
            errors,
        )
        self.assertIn(
            "events/freshcup.toml: unknown gamebox 'ghostbox'",
            errors,
        )

    def test_all_difficulties_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_fixture(VALID_FIXTURE, Path(tmp) / "content")
            meta_path = root / "challenges" / "comment" / "meta.toml"
            original = meta_path.read_text(encoding="utf-8")

            for difficulty in content.DIFFICULTIES:
                meta_path.write_text(
                    original.replace(
                        'difficulty = "easy"', f'difficulty = "{difficulty}"'
                    ),
                    encoding="utf-8",
                )
                self.assertTrue(
                    content.validate(root).ok,
                    f"difficulty '{difficulty}' should be accepted",
                )

    def test_empty_accounts_for_missing_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = content.validate(Path(tmp))

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(
                (len(result.challenges), len(result.gameboxes), len(result.events)),
                (0, 0, 0),
            )


# ---------------------------------------------------------------------------
# 6 - 9. catalog
# ---------------------------------------------------------------------------


class CatalogTests(unittest.TestCase):
    def catalog(self) -> dict:
        return content.build_catalog(VALID_FIXTURE)

    def entry(self, collection: str, content_id: str) -> dict:
        for item in self.catalog()[collection]:
            if item["id"] == content_id:
                return item
        raise AssertionError(f"{collection}/{content_id} missing from catalog")

    def test_catalog_root_structure(self) -> None:
        catalog = self.catalog()

        self.assertEqual(
            list(catalog.keys()),
            ["version", "challenges", "gameboxes", "events"],
        )
        self.assertEqual(catalog["version"], 1)

    def test_catalog_challenge_generation(self) -> None:
        self.assertEqual(
            self.entry("challenges", "comment"),
            {
                "id": "comment",
                "name": "comment",
                "version": "1.0.0",
                "author": "fb0sh@outlook.com",
                "category": "web",
                "difficulty": "easy",
                "tags": ["php", "web"],
                "description": "注释里面有什么？",
                "image": "floatctf/comment:challenge-v1.0.0",
                "flag": {"type": "dynamic"},
                "docker": {
                    "port": 80,
                    "recommended_resources": {
                        "cpu_millis": 500,
                        "memory_bytes": 268435456,
                        "pids_limit": 100,
                    },
                },
                "events": ["freshcup"],
            },
        )

    def test_catalog_gamebox_generation(self) -> None:
        self.assertEqual(
            self.entry("gameboxes", "comment"),
            {
                "id": "comment",
                "name": "comment",
                "version": "1.0.0",
                "author": "dev@floatctf.local",
                "category": "misc",
                "difficulty": "medium",
                "tags": ["box"],
                "description": "GameBox fixture",
                "image": "floatctf/comment:gamebox-v1.0.0",
                "docker": {"port": 8080},
                "events": ["freshcup"],
            },
        )

    def test_catalog_challenge_without_events_or_docker(self) -> None:
        self.assertEqual(
            self.entry("challenges", "cookie"),
            {
                "id": "cookie",
                "name": "cookie",
                "version": "1.0.0",
                "author": "dev@floatctf.local",
                "category": "web",
                "difficulty": "unknown",
                "tags": [],
                "description": "想成为管理员吗？也许你需要一个特殊的饼干！",
                "image": "floatctf/cookie:challenge-v1.0.0",
                "flag": {"type": "static"},
                "events": [],
            },
        )

    def test_catalog_event_entry(self) -> None:
        self.assertEqual(
            self.catalog()["events"],
            [
                {
                    "id": "freshcup",
                    "title": "Freshcup Fixture",
                    "description": "Fixture event",
                    "started_at": "2025-01-01 10:00",
                    "ended_at": "2025-01-01 18:00",
                    "challenges": ["comment"],
                    "gameboxes": ["comment"],
                }
            ],
        )

    def test_event_to_challenge_reverse_relation(self) -> None:
        catalog = self.catalog()

        comment_challenge = self.entry("challenges", "comment")
        comment_gamebox = self.entry("gameboxes", "comment")

        self.assertEqual(comment_challenge["events"], ["freshcup"])
        self.assertEqual(comment_gamebox["events"], ["freshcup"])

        # An event only lists what it references.
        self.assertEqual(catalog["events"][0]["challenges"], ["comment"])
        self.assertEqual(catalog["events"][0]["gameboxes"], ["comment"])

    def test_catalog_never_exposes_flag_values(self) -> None:
        entry = self.entry("challenges", "cookie")
        rendered = content.render_catalog(self.catalog())

        self.assertEqual(entry["flag"], {"type": "static"})
        self.assertNotIn("fixture-flag-must-not-leak", rendered)

    def test_catalog_is_deterministic(self) -> None:
        first = content.render_catalog(content.build_catalog(VALID_FIXTURE))
        second = content.render_catalog(content.build_catalog(VALID_FIXTURE))

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertNotIn("generated_at", first)

        catalog = self.catalog()
        self.assertEqual(
            [item["id"] for item in catalog["challenges"]],
            sorted(item["id"] for item in catalog["challenges"]),
        )
        self.assertEqual(
            [item["id"] for item in catalog["gameboxes"]],
            sorted(item["id"] for item in catalog["gameboxes"]),
        )
        self.assertEqual(
            [item["id"] for item in catalog["events"]],
            sorted(item["id"] for item in catalog["events"]),
        )

    def test_catalog_check_detects_missing_and_stale_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_fixture(VALID_FIXTURE, Path(tmp) / "content")

            self.assertEqual(quiet(content.main, ["catalog", "--check", "--root", str(root)]), 1)

            self.assertEqual(quiet(content.main, ["catalog", "--root", str(root)]), 0)
            self.assertEqual(quiet(content.main, ["catalog", "--check", "--root", str(root)]), 0)

            (root / "catalog.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(quiet(content.main, ["catalog", "--check", "--root", str(root)]), 1)

    def test_catalog_round_trips_through_json(self) -> None:
        rendered = content.render_catalog(content.build_catalog(VALID_FIXTURE))

        self.assertEqual(
            json.loads(rendered),
            content.build_catalog(VALID_FIXTURE),
        )
        self.assertIn("注释里面有什么？", rendered)


# ---------------------------------------------------------------------------
# labels / github output
# ---------------------------------------------------------------------------


class LabelTests(unittest.TestCase):
    def test_image_labels(self) -> None:
        challenge = content.load_content(VALID_FIXTURE, "challenges/comment")

        with mock.patch.dict(os.environ, {}, clear=True):
            labels = content.image_labels(challenge)

        self.assertEqual(
            labels,
            {
                "org.opencontainers.image.title": "comment",
                "org.opencontainers.image.description": "注释里面有什么？",
                "org.opencontainers.image.version": "1.0.0",
                "org.opencontainers.image.vendor": "FloatCTF",
                "org.opencontainers.image.source": (
                    "https://github.com/FloatCTF/floatctf-content"
                ),
                "io.floatctf.type": "challenge",
                "io.floatctf.id": "comment",
                "io.floatctf.category": "web",
                "io.floatctf.difficulty": "easy",
                "io.floatctf.version": "1.0.0",
                "io.floatctf.tags": "php,web",
            },
        )

    def test_image_labels_revision(self) -> None:
        challenge = content.load_content(VALID_FIXTURE, "challenges/comment")

        labels = content.image_labels(challenge, "deadbeef")
        self.assertEqual(labels["org.opencontainers.image.revision"], "deadbeef")

        with mock.patch.dict(os.environ, {"GITHUB_SHA": "cafebabe"}, clear=True):
            labels = content.image_labels(challenge)
        self.assertEqual(labels["org.opencontainers.image.revision"], "cafebabe")

    def test_image_labels_are_single_line(self) -> None:
        challenge = content.Content(
            id="multi",
            type=content.CONTENT_CHALLENGE,
            path=Path("challenges/multi"),
            meta={
                "name": "multi",
                "version": "1.0.0",
                "category": "web",
                "difficulty": "hard",
                "tags": ["a", "b"],
                "description": "line one\n\nline two",
            },
        )

        labels = content.image_labels(challenge)

        self.assertEqual(
            labels["org.opencontainers.image.description"], "line one line two"
        )
        for value in labels.values():
            self.assertNotIn("\n", value)

    def test_image_meta_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"

            result = quiet(
                content.main,
                [
                    "image-meta",
                    "challenges/comment",
                    "--root",
                    str(VALID_FIXTURE),
                    "--github-output",
                    str(output),
                    "--revision",
                    "deadbeef",
                ],
            )

            self.assertEqual(result, 0)

            text = output.read_text(encoding="utf-8")
            self.assertIn("image=floatctf/comment:challenge-v1.0.0\n", text)
            self.assertIn("context=challenges/comment/src\n", text)
            self.assertIn("labels<<EOF\n", text)
            self.assertTrue(text.endswith("EOF\n"))
            self.assertIn("org.opencontainers.image.revision=deadbeef\n", text)

    def test_changed_github_output_is_single_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"

            result = quiet(
                content.main,
                [
                    "changed",
                    "--all",
                    "--dockerfile-only",
                    "--root",
                    str(VALID_FIXTURE),
                    "--github-output",
                    str(output),
                ],
            )

            self.assertEqual(result, 0)
            self.assertEqual(
                output.read_text(encoding="utf-8"),
                'paths=["challenges/comment","gameboxes/comment"]\n',
            )


# ---------------------------------------------------------------------------
# 10. changed path detection
# ---------------------------------------------------------------------------


class ChangedTests(unittest.TestCase):
    def test_content_paths_filters_sorts_and_dedupes(self) -> None:
        names = [
            "challenges/comment/src/index.php",
            "challenges/comment/meta.toml",
            "challenges/comment/README.md",
            "gameboxes/foo/meta.toml",
            "events/freshcup.toml",
            "scripts/content.py",
            "scripts/tests/fixtures/valid/challenges/comment/meta.toml",
            "docs/freshcup.md",
            "README.md",
            "catalog.json",
        ]

        self.assertEqual(
            content.content_paths(names),
            ["challenges/comment", "gameboxes/foo"],
        )

    def test_content_paths_handles_spaces_and_quotes(self) -> None:
        names = [
            "challenges/Cirno's perfect math class/src/Dockerfile",
            "challenges/Cirno's perfect math class/meta.toml",
        ]

        self.assertEqual(
            content.content_paths(names),
            ["challenges/Cirno's perfect math class"],
        )

    def test_content_paths_ignores_non_content(self) -> None:
        self.assertEqual(
            content.content_paths(
                ["events/a.toml", "challenges", "challenges/", "gameboxes/x"]
            ),
            ["gameboxes/x"],
        )

    def test_find_changed_requires_revisions(self) -> None:
        with self.assertRaises(content.ContentError):
            content.find_changed(VALID_FIXTURE)

    def test_find_changed_dockerfile_filter(self) -> None:
        self.assertEqual(
            content.find_changed(VALID_FIXTURE, all_content=True),
            ["challenges/comment", "challenges/cookie", "gameboxes/comment"],
        )
        self.assertEqual(
            content.find_changed(
                VALID_FIXTURE, all_content=True, dockerfile_only=True
            ),
            ["challenges/comment", "gameboxes/comment"],
        )


@unittest.skipUnless(shutil.which("git"), "git is required")
class ChangedGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._git("init", "-q")

        self.write("challenges/comment/meta.toml", 'name = "comment"\n')
        self.write("challenges/comment/src/Dockerfile", "FROM scratch\n")
        self.write("gameboxes/box/meta.toml", 'name = "box"\n')
        self.write("events/freshcup.toml", 'id = "freshcup"\n')
        self.write("README.md", "root\n")

        self.commit("one")
        self.base = self.rev("HEAD")

        self.write("challenges/comment/src/Dockerfile", "FROM busybox\n")
        self.write("gameboxes/box/README.md", "docs only\n")
        self.write("events/freshcup.toml", 'id = "freshcup"\n# changed\n')
        self.commit("two")
        self.head = self.rev("HEAD")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            },
        )
        return result.stdout.strip()

    def rev(self, reference: str) -> str:
        return self._git("rev-parse", reference)

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def test_diff_detects_src_changes_only(self) -> None:
        self.assertEqual(
            content.find_changed(self.root, self.base, self.head),
            ["challenges/comment", "gameboxes/box"],
        )
        self.assertEqual(
            content.find_changed(
                self.root, self.base, self.head, dockerfile_only=True
            ),
            ["challenges/comment"],
        )

    def test_events_and_scripts_do_not_trigger_builds(self) -> None:
        self.write("scripts/content.py", "# changed\n")
        self.commit("scripts")
        scripts_head = self.rev("HEAD")

        self.assertEqual(
            content.find_changed(self.root, self.head, scripts_head, dockerfile_only=True),
            [],
        )

    def test_zero_base_builds_everything(self) -> None:
        self.assertEqual(
            content.find_changed(self.root, "0" * 40, self.head),
            ["challenges/comment", "gameboxes/box"],
        )


if __name__ == "__main__":
    unittest.main()
