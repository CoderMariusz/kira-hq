from __future__ import annotations

import pytest

from kira_hq.cli import main as cli_main


pytestmark = pytest.mark.smoke


def test_dispatcher_shows_help_for_root_command(capsys):
    exit_code = cli_main.main(["--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "add-project" in captured.out
    assert "archive-project" in captured.out


def test_dispatcher_invokes_add_project_help(capsys):
    exit_code = cli_main.main(["add-project", "--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "project root" in captured.out


def test_dispatcher_uses_sys_argv_when_invoked_as_console_script(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["kira-hq", "add-project", "--help"])

    exit_code = cli_main.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "project root" in captured.out
