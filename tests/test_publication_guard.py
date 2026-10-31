from pathlib import Path

from ai_crypto_signals.config import project_root


def test_workflow_is_manual_and_blocks_main():
    root = project_root()
    workflow = (root / ".github" / "workflows" / "daily_collect.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "refs/heads/main" in workflow
    for line in workflow.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not stripped.startswith("schedule:")
        assert "peaceiris/actions-gh-pages" not in stripped
        assert "gh release" not in stripped
        assert "action-gh-release" not in stripped
    workflows = list((root / ".github" / "workflows").glob("*.yml"))
    assert [path.name for path in workflows] == ["daily_collect.yml"]
    assert not (root / "CNAME").exists()
