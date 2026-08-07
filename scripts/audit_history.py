#!/usr/bin/env python3
"""审计整个 git 历史（所有 ref、所有 blob、所有提交元数据）中的敏感内容。

内置探测器只针对通用形态（API key、真实用户家目录、邮箱、被提交的 `.env`），
不在仓库里写死任何真实的个人标识。需要按姓名/公司等关键词排查时，把这些词写进
一个未跟踪的文件（例如 `.audit-patterns`，每行一个正则），再用
`--patterns-file` 传入，这样关键词本身不会进入仓库历史。

用法::

    uv run python scripts/audit_history.py
    uv run python scripts/audit_history.py --patterns-file .audit-patterns

发现问题时退出码为 1，干净时为 0。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# 明显是占位符的用户名，出现在家目录路径里不算泄漏。
PLACEHOLDER_USER_NAMES = {
    "<user>",
    "<username>",
    "username",
    "%username%",
    "$user",
    "user",
    "youruser",
    "your-user",
    "public",
    "default",
    "all users",
    "ubuntu",
    "runner",
    "runneradmin",
    "root",
}

# 只允许明确的示例/占位邮箱域名出现在文件内容里。
ALLOWED_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "noreply.github.com",
    "github.com",
    "cursor.com",
    "test",
}

# 扫描 blob 内容时跳过的路径（锁文件里全是哈希，只会产生噪声）。
SKIPPED_PATHS = {"uv.lock"}
SKIPPED_SUFFIXES = {".webp", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf"}

API_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{16,}")
OPAQUE_SECRET_RE = re.compile(
    r"\b(?:[A-Za-z_]*(?:KEY|TOKEN|SECRET|PASSWORD))\s*[:=]\s*[\"']?([A-Za-z0-9]{24,})[\"']?",
    re.IGNORECASE,
)
HOME_DIR_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]{1,2}Users|/Users|/home)[\\/]{1,2}([A-Za-z0-9_.%<>$-]+)",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


@dataclass(frozen=True)
class Finding:
    kind: str
    where: str
    detail: str


def _git(*args: str, repo: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _blob_paths(repo: Path) -> dict[str, set[str]]:
    """所有 ref 可达的 blob -> 它曾经使用过的路径集合。"""
    paths: dict[str, set[str]] = defaultdict(set)
    listing = _git("rev-list", "--objects", "--all", repo=repo)
    for line in listing.splitlines():
        sha, _, path = line.partition(" ")
        if path:
            paths[sha].add(path)
    return paths


def _read_blobs(repo: Path, shas: list[str]) -> dict[str, bytes]:
    """用一次 `git cat-file --batch` 批量读取 blob，避免逐个起进程。"""
    if not shas:
        return {}
    process = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=repo,
        input="\n".join(shas).encode() + b"\n",
        check=True,
        capture_output=True,
    )
    stream = process.stdout
    contents: dict[str, bytes] = {}
    offset = 0
    while offset < len(stream):
        newline = stream.index(b"\n", offset)
        header = stream[offset:newline].decode()
        offset = newline + 1
        sha, kind, size = header.split()
        length = int(size)
        if kind == "blob":
            contents[sha] = stream[offset : offset + length]
        offset += length + 1
    return contents


def _is_text(payload: bytes) -> bool:
    return b"\x00" not in payload[:8000]


def _is_placeholder_user(name: str) -> bool:
    lowered = name.lower()
    if lowered in PLACEHOLDER_USER_NAMES:
        return True
    return any(hint in lowered for hint in ("example", "placeholder", "your", "<", "%", "$"))


def _scan_text(text: str, where: str, extra: list[re.Pattern[str]]) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        location = f"{where}:{lineno}"
        for match in API_KEY_RE.finditer(line):
            findings.append(Finding("api-key", location, match.group(0)[:12] + "..."))
        for match in OPAQUE_SECRET_RE.finditer(line):
            findings.append(Finding("opaque-secret", location, match.group(1)[:8] + "..."))
        for match in HOME_DIR_RE.finditer(line):
            if not _is_placeholder_user(match.group(1)):
                findings.append(Finding("home-directory", location, match.group(0)))
        for match in EMAIL_RE.finditer(line):
            if match.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
                findings.append(Finding("email", location, match.group(0)))
        for pattern in extra:
            match = pattern.search(line)
            if match:
                findings.append(Finding("custom-pattern", location, pattern.pattern))
    return findings


def audit_blobs(repo: Path, extra: list[re.Pattern[str]]) -> list[Finding]:
    paths = _blob_paths(repo)
    interesting = [
        sha
        for sha, names in paths.items()
        if not all(
            name in SKIPPED_PATHS or Path(name).suffix.lower() in SKIPPED_SUFFIXES
            for name in names
        )
    ]
    findings: list[Finding] = []
    for sha, payload in _read_blobs(repo, interesting).items():
        if not _is_text(payload):
            continue
        where = "|".join(sorted(paths[sha]))
        text = payload.decode("utf-8", errors="replace")
        findings.extend(_scan_text(text, f"blob {sha[:10]} ({where})", extra))
    return findings


def _commit_metadata(repo: Path) -> list[tuple[str, str, str, str]]:
    log = _git("log", "--all", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>%x1f%s", repo=repo)
    rows = []
    for line in log.splitlines():
        if line:
            sha, author, committer, subject = line.split("\x1f")
            rows.append((sha, author, committer, subject))
    return rows


def audit_commit_metadata(repo: Path, extra: list[re.Pattern[str]]) -> list[Finding]:
    """提交元数据只按自定义关键词判定。

    作者身份本身不是泄漏——是否算个人信息取决于用的是哪个身份，所以默认只做
    清单展示（见 `identity_inventory`），失败判定交给 `--patterns-file`。
    """
    findings: list[Finding] = []
    for sha, author, committer, subject in _commit_metadata(repo):
        for label, value in (("author", author), ("committer", committer), ("subject", subject)):
            for pattern in extra:
                if pattern.search(value):
                    findings.append(
                        Finding("commit-custom-pattern", f"{sha[:10]} {label}", pattern.pattern)
                    )
    return findings


def identity_inventory(repo: Path) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for _sha, author, committer, _subject in _commit_metadata(repo):
        counts[author] += 1
        if committer != author:
            counts[committer] += 1
    return dict(counts)


def audit_tracked_env_files(repo: Path) -> list[Finding]:
    tracked = _git("log", "--all", "--pretty=format:", "--name-only", repo=repo).splitlines()
    findings: list[Finding] = []
    for name in sorted({item for item in tracked if item}):
        base = Path(name).name
        if base == ".env" or (base.startswith(".env.") and base != ".env.sample"):
            findings.append(Finding("committed-env-file", name, "dotenv file present in history"))
    return findings


def load_extra_patterns(values: list[str], patterns_file: Path | None) -> list[re.Pattern[str]]:
    raw = list(values)
    if patterns_file is not None:
        for line in patterns_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                raw.append(stripped)
    return [re.compile(item, re.IGNORECASE) for item in raw]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--pattern", action="append", default=[], help="额外的正则（可重复）")
    parser.add_argument("--patterns-file", type=Path, default=None, help="每行一个正则的文件")
    args = parser.parse_args(argv)

    extra = load_extra_patterns(args.pattern, args.patterns_file)
    findings = [
        *audit_blobs(args.repo, extra),
        *audit_commit_metadata(args.repo, extra),
        *audit_tracked_env_files(args.repo),
    ]

    print("历史中出现过的提交身份（需人工确认是否可公开）:")
    for identity, count in sorted(identity_inventory(args.repo).items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {identity}")

    if not findings:
        print("\nOK: 未在任何 ref 的历史中发现敏感内容。")
        return 0

    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.kind].append(finding)
    for kind in sorted(grouped):
        print(f"\n[{kind}] {len(grouped[kind])} 处")
        for finding in grouped[kind]:
            print(f"  {finding.where}: {finding.detail}")
    print(f"\n共 {len(findings)} 处待处理。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
