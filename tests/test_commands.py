import argparse
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from gearbox.commandmanager import CommandManager
from gearbox.commands.help import HelpAction
from gearbox.commands.serve import ServeCommand
from gearbox.commands.setup_app import SetupAppCommand
from gearbox.main import main


# --- Test for ServeCommand using external wsgiref ---
def test_serve_command():
    with tempfile.NamedTemporaryFile() as f:
        f.write(b"""
[server:main]
use = egg:gearbox#wsgiref
host = 127.0.0.1
port = 8080

[app:dummy_app]
use = egg:dummy_app""")
        f.flush()

        opts = argparse.Namespace(
            config_file=f.name,
            app_name="dummy_app",
            server="wsgiref",
            server_name=None,
            daemon=False,
            pid_file=None,
            reload=False,
            reload_interval=1,
            monitor_restart=False,
            set_user=None,
            set_group=None,
            args=[],
            stop_daemon=False,
            show_status=False,
        )
        server_instance = MagicMock()  # Serve instance with serve_forever auto-mocked.
        with (
            patch(
                "wsgiref.simple_server.make_server", return_value=server_instance
            ) as mock_make_server,
            patch.object(ServeCommand, "loadapp", return_value=MagicMock()),
        ):
            cmd = ServeCommand(MagicMock(), argparse.Namespace(verbose_level=0))
            cmd.take_action(opts)
            mock_make_server.assert_called_once()
            server_instance.serve_forever.assert_called_once()


# --- Test for HelpAction using real CommandManager ---
def test_help_action(capsys):
    cm = CommandManager(namespace="test")
    cm.add_command(
        "dummy",
        MagicMock(
            return_value=MagicMock(
                deprecated=False, get_description=lambda: "Dummy command description"
            )
        ),
    )
    app = MagicMock(command_manager=cm)
    parser = argparse.ArgumentParser(prog="fakeapp")
    ns = argparse.Namespace(debug=True)
    action = HelpAction(option_strings=[], dest="help", nargs=0, default=app)
    with pytest.raises(SystemExit):
        action(parser, ns, None)
    output = capsys.readouterr().out
    assert "dummy" in output
    assert "Dummy command description" in output


# --- Test for makepackage command ---
def test_makepackage(tmp_path, monkeypatch):
    # Simulate command line call to `gearbox makepackage --name TestProject`
    script = tmp_path / "dummy_script.py"
    script.write_text("")  # dummy script placeholder
    # Change working dir so that 'makepackage' creates the project dir there.
    monkeypatch.chdir(tmp_path)

    with patch.object(sys, "argv", ["gearbox", "makepackage", "--name", "TestProject"]):
        main()

    project_dir = tmp_path / "TestProject"
    assert project_dir.is_dir()


# --- Test for setup-app command ---
def test_setup_app(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_file = project_dir / "development.ini"
    config_file.write_text("[app:main]\nuse=egg:fakeegg\n")

    fake_setup_app = MagicMock(return_value=0)

    with (
        patch.object(sys, "argv", ["gearbox", "setup-app", "-c", str(config_file)]),
        patch(
            "gearbox.commands.setup_app.appconfig",
            return_value=MagicMock(
                context=MagicMock(
                    entry_point_name="main",
                    protocol="app",
                    distribution=MagicMock(
                        read_text=MagicMock(return_value="fakemodule")
                    ),
                )
            ),
        ),
        patch.object(
            SetupAppCommand,
            "_import_module",
            return_value=MagicMock(setup_app=fake_setup_app),
        ),
    ):
        main()

    fake_setup_app.assert_called_once()


# --- Test for scaffold command ---
def test_scaffold(tmp_path):
    lookup_dir = tmp_path / "scaffolds"
    lookup_dir.mkdir()
    template_file = lookup_dir / "model.template"
    template_file.write_text("class {{target.capitalize()}}:\n    pass\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch.object(
        sys,
        "argv",
        [
            "gearbox",
            "scaffold",
            "model",
            "TestModel",
            "-l",
            str(lookup_dir),
            "-p",
            str(project_dir),
        ],
    ):
        main()

    output_file = project_dir / "TestModel"
    assert output_file.is_file()
    content = output_file.read_text()
    # Expect the template engine to substitute, e.g., "Testmodel" from {{target.capitalize()}}
    assert "class Testmodel" in content


# --- Test for patch command ---
def test_patch(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\n")

    with (
        patch(
            "gearbox.commands.patch.PatchCommand._walk_flat",
            return_value=[str(test_file)],
        ),
        patch.object(
            sys, "argv", ["gearbox", "patch", str(test_file), "World", "-r", "Gearbox"]
        ),
    ):
        main()

    content = test_file.read_text()
    assert "Gearbox" in content
