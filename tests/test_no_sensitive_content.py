"""守卫测试：已跟踪的文件里不允许出现密钥或真实个人环境信息。

这里只扫描当前工作树。历史提交里的旧 blob 只能靠 `git filter-repo` 重写，
排查用 `scripts/audit_history.py`。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_history.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("laozhang_audit_history", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _tracked_text_files() -> list[Path]:
    audit = _load_audit_module()
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode()
    files = []
    for name in listing.split("\0"):
        if not name or name in audit.SKIPPED_PATHS:
            continue
        path = REPO_ROOT / name
        if path.suffix.lower() in audit.SKIPPED_SUFFIXES or not path.is_file():
            continue
        files.append(path)
    return files


@pytest.fixture(scope="module")
def audit():
    return _load_audit_module()


def test_tracked_files_contain_no_secrets_or_personal_paths(audit):
    findings = []
    for path in _tracked_text_files():
        payload = path.read_bytes()
        if not audit._is_text(payload):
            continue
        findings.extend(
            audit._scan_text(
                payload.decode("utf-8", errors="replace"),
                str(path.relative_to(REPO_ROOT)),
                [],
            )
        )
    assert not findings, "工作树中发现敏感内容:\n" + "\n".join(
        f"{item.kind} {item.where}: {item.detail}" for item in findings
    )


def test_dotenv_files_are_not_tracked():
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode()
    offenders = [
        name
        for name in listing.split("\0")
        if Path(name).name == ".env"
        or (Path(name).name.startswith(".env.") and Path(name).name != ".env.sample")
    ]
    assert offenders == [], f"dotenv 文件不应被跟踪: {offenders}"


def test_home_directory_detector_distinguishes_placeholders(audit):
    # 用拼接构造样本，这样这份守卫测试自身不会命中自己的探测器。
    name = "somebody"
    real = audit._scan_text(f"C:\\Users\\{name}\\AppData", "sample.md", [])
    assert [item.kind for item in real] == ["home-directory"]
    assert audit._scan_text(r"C:\Users\<user>\AppData", "sample.md", []) == []
    assert audit._scan_text("/home/ubuntu/work", "sample.md", []) == []


def test_api_key_detector_ignores_placeholder_values(audit):
    assert audit._scan_text("LAOZHANG_KEY=your-real-api-key", "sample.md", []) == []
    prefixed = audit._scan_text("LAOZHANG_KEY=sk-" + "a1" * 12, "sample.md", [])
    assert [item.kind for item in prefixed] == ["api-key"]
    opaque = audit._scan_text("LAOZHANG_KEY=" + "a1b2" * 8, "sample.md", [])
    assert [item.kind for item in opaque] == ["opaque-secret"]
