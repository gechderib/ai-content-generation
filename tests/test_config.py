import os

from pipeline.config import load_env


def test_load_env_does_not_override_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=from_file\nBAR=also_from_file\n# a comment\n\nBAZ=\"quoted\"\n")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "from_shell")

    load_env(env_file)

    assert os.environ["FOO"] == "from_file"
    assert os.environ["BAR"] == "from_shell"
    assert os.environ["BAZ"] == "quoted"


def test_load_env_missing_file_is_a_noop(tmp_path):
    missing = tmp_path / "does_not_exist.env"
    load_env(missing)  # should not raise
