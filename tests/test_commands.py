import argparse
import importlib.metadata
import pathlib
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from gearbox.command import Command
from gearbox.commandmanager import CommandManager
from gearbox.commands.help import HelpAction
from gearbox.commands.serve import ServeCommand
from gearbox.commands.setup_app import SetupAppCommand
from gearbox.main import GearBox, main
from gearbox.utils.copydir import copy_dir
from gearbox.utils.plugins import find_local_distribution


def _write_dist_info(
    base_dir,
    name,
    version,
    entry_points_text="",
    package_files=None,
    top_level_text="",
):
    dist_info_dir = base_dir / f"{name}-{version}.dist-info"
    dist_info_dir.mkdir()
    metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    (dist_info_dir / "METADATA").write_text(metadata)
    if entry_points_text:
        (dist_info_dir / "entry_points.txt").write_text(entry_points_text)
    if top_level_text:
        (dist_info_dir / "top_level.txt").write_text(top_level_text)
    if package_files:
        record_entries = []
        for package_file in package_files:
            package_path = base_dir / package_file
            package_path.parent.mkdir(parents=True, exist_ok=True)
            package_path.write_text("")
            record_entries.append(f"{package_file},,")
        (dist_info_dir / "RECORD").write_text("\n".join(record_entries) + "\n")
    return dist_info_dir


def _write_egg_info(base_dir, name, version, entry_points_text="", top_level_text=""):
    egg_info_dir = base_dir / f"{name}.egg-info"
    egg_info_dir.mkdir()
    pkg_info = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    (egg_info_dir / "PKG-INFO").write_text(pkg_info)
    if entry_points_text:
        (egg_info_dir / "entry_points.txt").write_text(entry_points_text)
    if top_level_text:
        (egg_info_dir / "top_level.txt").write_text(top_level_text)
    return egg_info_dir


def _write_project_with_command(tmp_path):
    project_root = tmp_path / "project"
    nested_cwd = project_root / "app" / "pkg"
    nested_cwd.mkdir(parents=True)
    (project_root / "fakecommands.py").write_text(
        "from gearbox.command import Command\n\n"
        "class ProjectCommand(Command):\n"
        "    '''Current directory command help.'''\n\n"
        "    def get_parser(self, prog_name):\n"
        "        parser = super().get_parser(prog_name)\n"
        "        parser.add_argument('--project-option', help='current directory option')\n"
        "        return parser\n"
    )
    _write_dist_info(
        project_root,
        "sampleproject",
        "0.1.0",
        "[gearbox.plugins]\nlocal-tools = localtools\n",
    )
    _write_dist_info(
        project_root,
        "localtools",
        "1.0.0",
        "[gearbox.project_commands]\nprojectcheck = fakecommands:ProjectCommand\n",
    )
    return project_root, nested_cwd


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
        with patch(
            "wsgiref.simple_server.make_server", return_value=server_instance
        ) as mock_make_server, patch.object(
            ServeCommand, "loadapp", return_value=MagicMock()
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
    assert (project_dir / "pyproject.toml").is_file()
    assert not (project_dir / "setup.py").exists()


# --- Test for setup-app command ---
def test_setup_app(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_file = project_dir / "development.ini"
    config_file.write_text("[app:main]\nuse=egg:fakeegg\n")

    fake_setup_app = MagicMock(return_value=0)

    with patch.object(
        sys, "argv", ["gearbox", "setup-app", "-c", str(config_file)]
    ), patch(
        "gearbox.commands.setup_app.appconfig",
        return_value=MagicMock(
            context=MagicMock(
                entry_point_name="main",
                protocol="app",
                distribution=MagicMock(
                    files=[pathlib.PurePosixPath("fakemodule/websetup.py")]
                ),
            )
        ),
    ), patch.object(
        SetupAppCommand,
        "_import_module",
        return_value=MagicMock(setup_app=fake_setup_app),
    ):
        main()

    fake_setup_app.assert_called_once()


def test_setup_app_uses_websetup_file_from_dist_files(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_file = project_dir / "development.ini"
    config_file.write_text("[app:main]\nuse=egg:fakeegg\n")

    fake_setup_app = MagicMock(return_value=0)
    fake_dist = MagicMock()
    fake_dist.files = [pathlib.PurePosixPath("fakemodule/websetup.py")]

    with patch.object(
        sys, "argv", ["gearbox", "setup-app", "-c", str(config_file)]
    ), patch(
        "gearbox.commands.setup_app.appconfig",
        return_value=MagicMock(
            context=MagicMock(
                entry_point_name="main",
                protocol="app",
                distribution=fake_dist,
            )
        ),
    ), patch.object(
        SetupAppCommand,
        "_import_module",
        return_value=MagicMock(setup_app=fake_setup_app),
    ):
        main()

    fake_setup_app.assert_called_once()


def test_setup_app_uses_websetup_package_from_dist_files(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_file = project_dir / "development.ini"
    config_file.write_text("[app:main]\nuse=egg:fakeegg\n")

    fake_setup_app = MagicMock(return_value=0)
    fake_dist = MagicMock()
    fake_dist.files = [pathlib.PurePosixPath("fakemodule/websetup/__init__.py")]

    with patch.object(
        sys, "argv", ["gearbox", "setup-app", "-c", str(config_file)]
    ), patch(
        "gearbox.commands.setup_app.appconfig",
        return_value=MagicMock(
            context=MagicMock(
                entry_point_name="main",
                protocol="app",
                distribution=fake_dist,
            )
        ),
    ), patch.object(
        SetupAppCommand,
        "_import_module",
        return_value=MagicMock(setup_app=fake_setup_app),
    ) as import_module:
        main()

    import_module.assert_called_once_with("fakemodule.websetup")
    fake_setup_app.assert_called_once()


def test_setup_app_falls_back_to_top_level_metadata(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_file = project_dir / "development.ini"
    config_file.write_text("[app:main]\nuse=egg:fakeegg\n")

    fake_setup_app = MagicMock(return_value=0)
    fake_dist = MagicMock()
    fake_dist.files = None
    fake_dist.read_text.return_value = "fakemodule\n"

    with patch.object(
        sys, "argv", ["gearbox", "setup-app", "-c", str(config_file)]
    ), patch(
        "gearbox.commands.setup_app.appconfig",
        return_value=MagicMock(
            context=MagicMock(
                entry_point_name="main",
                protocol="app",
                distribution=fake_dist,
            )
        ),
    ), patch.object(
        SetupAppCommand,
        "_import_module",
        return_value=MagicMock(setup_app=fake_setup_app),
    ) as import_module:
        main()

    import_module.assert_called_once_with("fakemodule.websetup")
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


def test_scaffold_derives_output_extension_from_template_name(tmp_path):
    lookup_dir = tmp_path / "scaffolds"
    lookup_dir.mkdir()
    template_file = lookup_dir / "controller.py.template"
    template_file.write_text("class {{target.capitalize()}}:\n    pass\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch.object(
        sys,
        "argv",
        [
            "gearbox",
            "scaffold",
            "controller",
            "Demo",
            "-l",
            str(lookup_dir),
            "-p",
            str(project_dir),
        ],
    ):
        main()

    output_file = project_dir / "Demo.py"
    assert output_file.is_file()
    assert "class Demo" in output_file.read_text()


def test_scaffold_no_package_prevents_subdir_init_file(tmp_path):
    lookup_dir = tmp_path / "scaffolds"
    lookup_dir.mkdir()
    template_file = lookup_dir / "controller.py.template"
    template_file.write_text("class {{target.capitalize()}}:\n    pass\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch.object(
        sys,
        "argv",
        [
            "gearbox",
            "scaffold",
            "controller",
            "Demo",
            "-l",
            str(lookup_dir),
            "-p",
            str(project_dir),
            "-s",
            "admin",
            "--no-package",
        ],
    ):
        main()

    assert (project_dir / "admin" / "Demo.py").is_file()
    assert not (project_dir / "admin" / "__init__.py").exists()


def test_scaffold_subdir_creates_package_init_by_default(tmp_path):
    lookup_dir = tmp_path / "scaffolds"
    lookup_dir.mkdir()
    template_file = lookup_dir / "controller.py.template"
    template_file.write_text("class {{target.capitalize()}}:\n    pass\n")
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch.object(
        sys,
        "argv",
        [
            "gearbox",
            "scaffold",
            "controller",
            "Demo",
            "-l",
            str(lookup_dir),
            "-p",
            str(project_dir),
            "-s",
            "admin",
        ],
    ):
        main()

    assert (project_dir / "admin" / "Demo.py").is_file()
    assert (project_dir / "admin" / "__init__.py").is_file()


# --- Test for patch command ---
def test_patch(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello World\n")

    with patch(
        "gearbox.commands.patch.glob.glob",
        return_value=[str(test_file)],
    ), patch.object(
        sys, "argv", ["gearbox", "patch", str(test_file), "World", "-r", "Gearbox"]
    ):
        main()

    content = test_file.read_text()
    assert "Gearbox" in content


def test_patch_accepts_relative_file_path(tmp_path, monkeypatch):
    test_file = tmp_path / "root.py"
    test_file.write_text("redirect('/demo')\n")
    monkeypatch.chdir(tmp_path)

    with patch.object(
        sys,
        "argv",
        [
            "gearbox",
            "patch",
            "root.py",
            "redirect('/demo')",
            "-r",
            "return 'Hello World'",
        ],
    ):
        main()

    assert test_file.read_text() == "return 'Hello World'\n"


def test_patch_accepts_relative_nested_file_path(tmp_path, monkeypatch):
    test_file = tmp_path / "controllers" / "root.py"
    test_file.parent.mkdir()
    test_file.write_text("    demo = DemoController()\n")
    monkeypatch.chdir(tmp_path)

    with patch.object(
        sys,
        "argv",
        ["gearbox", "patch", "controllers/root.py", "DemoController", "-d"],
    ):
        main()

    assert test_file.read_text() == ""


def test_copy_dir_interactive_diff_prefers_utf8_decoding(tmp_path):
    src_dir = tmp_path / "src"
    dest_dir = tmp_path / "dest"
    src_dir.mkdir()
    dest_dir.mkdir()
    (src_dir / "greeting.txt").write_text("I like crêpes\n", encoding="utf-8")
    (dest_dir / "greeting.txt").write_text("I like café\n", encoding="utf-8")

    captured = {}

    def fake_query_interactive(
        src_fn, dest_fn, src_content, dest_content, simulate, out_=sys.stdout
    ):
        captured["src_fn"] = src_fn
        captured["dest_fn"] = dest_fn
        captured["src_content"] = src_content
        captured["dest_content"] = dest_content
        return False

    with patch(
        "gearbox.utils.copydir.query_interactive", side_effect=fake_query_interactive
    ):
        copy_dir(
            str(src_dir),
            str(dest_dir),
            vars={},
            verbosity=0,
            interactive=True,
        )

    assert captured["src_fn"] == str(src_dir / "greeting.txt")
    assert captured["dest_fn"] == str(dest_dir / "greeting.txt")
    assert captured["src_content"] == "I like crêpes\n"
    assert captured["dest_content"] == "I like café\n"


def test_internal_command_help_flag_shows_command_help(capsys):
    result = GearBox().run(["serve", "--help"])

    output = capsys.readouterr().out
    assert result == 0
    assert "usage:" in output
    assert "serve [-c CONFIG_FILE]" in output
    assert "Serves a web application" in output
    assert "--config" in output
    assert "TurboGears2 Gearbox toolset" not in output
    assert "\nCommands:" not in output


def test_global_extension_command_help_flag_shows_command_help(monkeypatch, capsys):
    class ExtensionCommand(Command):
        """Global extension command help."""

        def get_parser(self, prog_name):
            parser = super().get_parser(prog_name)
            parser.add_argument("--extension-option", help="global extension option")
            return parser

    extension_ep = MagicMock()
    extension_ep.name = "extensioncheck"
    extension_ep.load.return_value = ExtensionCommand

    class EntryPointSet:
        def select(self, group):
            if group == "gearbox.commands":
                return [extension_ep]
            return []

    monkeypatch.setattr(
        "gearbox.commandmanager.importlib.metadata.entry_points",
        lambda: EntryPointSet(),
    )

    result = GearBox().run(["extensioncheck", "--help"])

    output = capsys.readouterr().out
    assert result == 0
    assert "usage:" in output
    assert "extensioncheck [--extension-option" in output
    assert "Global extension command help." in output
    assert "--extension-option" in output
    assert "TurboGears2 Gearbox toolset" not in output
    assert "\nCommands:" not in output


def test_current_directory_command_help_flag_shows_command_help(
    tmp_path, monkeypatch, capsys
):
    project_root, nested_cwd = _write_project_with_command(tmp_path)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.syspath_prepend(str(project_root))

    result = GearBox().run(["projectcheck", "--help"])

    output = capsys.readouterr().out
    assert result == 0
    assert "usage:" in output
    assert "projectcheck [--project-option" in output
    assert "Current directory command help." in output
    assert "--project-option" in output
    assert "TurboGears2 Gearbox toolset" not in output
    assert "\nCommands:" not in output


def test_loads_local_plugins_metadata_and_calls_project_package_loader():
    app = GearBox()
    plugin_ep = MagicMock(name="turbogears-devtools", group="gearbox.plugins")
    plugin_ep.module = "tg.devtools"
    dist = MagicMock()
    dist.entry_points = [plugin_ep]

    with patch(
        "gearbox.main.find_local_distribution", return_value=(dist, ".")
    ):
        with patch.object(app, "load_commands_for_package") as load_package:
            app._load_commands_for_current_dir()

    load_package.assert_called_once_with("tg.devtools", search_paths=["."])


def test_loads_tg_devtools_project_commands_from_project_plugins():
    app = GearBox()
    project_plugin_ep = MagicMock(group="gearbox.plugins")
    project_plugin_ep.name = "turbogears-devtools"
    project_plugin_ep.module = "tg.devtools"
    project_dist = MagicMock()
    project_dist.entry_points = [project_plugin_ep]

    migrate_ep = MagicMock(group="gearbox.project_commands")
    migrate_ep.name = "migrate"
    tgshell_ep = MagicMock(group="gearbox.project_commands")
    tgshell_ep.name = "tgshell"
    devtools_dist = MagicMock()
    devtools_dist.entry_points = [migrate_ep, tgshell_ep]

    with patch(
        "gearbox.main.find_local_distribution",
        return_value=(project_dist, "."),
    ), patch(
        "importlib.metadata.distribution", return_value=devtools_dist
    ):
        app._load_commands_for_current_dir()

    assert app.command_manager.commands["migrate"] is migrate_ep
    assert app.command_manager.commands["tgshell"] is tgshell_ep


def test_load_commands_for_package_adds_project_commands_with_spaces():
    app = GearBox()
    app.command_manager.commands = {}
    command_ep = MagicMock(group="gearbox.project_commands")
    command_ep.name = "foo_bar"
    dist = MagicMock()
    dist.entry_points = [command_ep]

    with patch("importlib.metadata.distribution", return_value=dist):
        app.load_commands_for_package("tg.devtools")

    assert app.command_manager.commands["foo bar"] is command_ep


def test_command_manager_loads_tgext_pluggable_style_global_commands():
    quickstart_ep = MagicMock()
    quickstart_ep.name = "quickstart-pluggable"
    migrate_ep = MagicMock()
    migrate_ep.name = "migrate-pluggable"
    plugin_eps = [quickstart_ep, migrate_ep]

    class EntryPointSet:
        def select(self, group):
            if group == "gearbox.commands":
                return plugin_eps
            return []

    with patch("gearbox.commandmanager.importlib.metadata.entry_points") as entry_points:
        entry_points.return_value = EntryPointSet()
        cm = CommandManager(namespace="gearbox.commands")

    assert cm.commands["quickstart-pluggable"] is quickstart_ep
    assert cm.commands["migrate-pluggable"] is migrate_ep


def test_loads_tg_devtools_commands_from_local_dist_info(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    nested_cwd = project_root / "app" / "pkg"
    nested_cwd.mkdir(parents=True)
    project_entry_points = (
        "[gearbox.plugins]\n"
        "turbogears-devtools = tg.devtools\n"
    )
    devtools_entry_points = (
        "[gearbox.project_commands]\n"
        "local_migrate_distinfo = devtools.gearbox.alembic_migrate:MigrateCommand\n"
        "local_tgshell_distinfo = devtools.gearbox.tgshell:ShellCommand\n"
    )
    _write_dist_info(project_root, "sampleproject", "0.1.0", project_entry_points)
    _write_dist_info(
        project_root,
        "TurboGears2.devtools",
        "2.5.0",
        devtools_entry_points,
        package_files=["tg/devtools/__init__.py"],
        top_level_text="tg\n",
    )

    monkeypatch.chdir(nested_cwd)
    app = GearBox()
    app._load_commands_for_current_dir()

    assert "local migrate distinfo" in app.command_manager.commands
    assert "local tgshell distinfo" in app.command_manager.commands


def test_loads_tgext_pluggable_global_commands_from_dist_info(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugins"
    plugin_root.mkdir()
    tgext_entry_points = (
        "[gearbox.commands]\n"
        "plug-local-distinfo = tgext.pluggable.commands.plug:PlugApplicationCommand\n"
        "quickstart-pluggable-local-distinfo = tgext.pluggable.commands.quickstart:QuickstartPluggableCommand\n"
    )
    _write_dist_info(plugin_root, "tgext.pluggable", "0.8.5", tgext_entry_points)

    monkeypatch.syspath_prepend(str(plugin_root))
    command_manager = CommandManager(namespace="gearbox.commands")

    assert "plug-local-distinfo" in command_manager.commands
    assert "quickstart-pluggable-local-distinfo" in command_manager.commands


def test_loads_tg_devtools_commands_from_local_egg_info(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    nested_cwd = project_root / "app" / "pkg"
    nested_cwd.mkdir(parents=True)
    project_entry_points = (
        "[gearbox.plugins]\n"
        "turbogears-devtools = tg.devtools\n"
    )
    devtools_entry_points = (
        "[gearbox.project_commands]\n"
        "local_migrate_egginfo = devtools.gearbox.alembic_migrate:MigrateCommand\n"
        "local_tgshell_egginfo = devtools.gearbox.tgshell:ShellCommand\n"
    )
    _write_egg_info(project_root, "sampleproject", "0.1.0", project_entry_points)
    _write_egg_info(
        project_root,
        "TurboGears2.devtools",
        "2.5.0",
        devtools_entry_points,
        top_level_text="tg\n",
    )
    (project_root / "tg").mkdir()
    (project_root / "tg" / "__init__.py").write_text("")

    monkeypatch.chdir(nested_cwd)
    app = GearBox()
    app._load_commands_for_current_dir()

    assert "local migrate egginfo" in app.command_manager.commands
    assert "local tgshell egginfo" in app.command_manager.commands


def test_run_continues_when_project_distribution_is_missing():
    app = GearBox()
    plugin_ep = MagicMock(name="turbogears-devtools", group="gearbox.plugins")
    plugin_ep.module = "tg.devtools"
    project_dist = MagicMock()
    project_dist.entry_points = [plugin_ep]

    with patch(
        "gearbox.main.find_local_distribution",
        return_value=(project_dist, "."),
    ), patch(
        "importlib.metadata.distribution",
        side_effect=importlib.metadata.PackageNotFoundError("tg.devtools"),
    ), patch.object(app, "_run_subcommand", return_value=42) as run_subcommand:
        result = app.run(["help"])

    assert result == 42
    run_subcommand.assert_called_once_with(["help"])


def test_find_local_distribution_continues_after_unreadable_directory(tmp_path):
    project_root = tmp_path / "project"
    nested_dir = project_root / "app" / "pkg"
    nested_dir.mkdir(parents=True)

    plugin_ep = MagicMock(group="gearbox.plugins")
    dist = MagicMock()
    dist.entry_points = [plugin_ep]

    def fake_distributions(path):
        scan_dir = path[0]
        if scan_dir == str(nested_dir):
            raise PermissionError("denied")
        if scan_dir == str(project_root):
            return [dist]
        return []

    with patch(
        "gearbox.utils.plugins.importlib.metadata.distributions",
        side_effect=fake_distributions,
    ):
        found_dist, found_path = find_local_distribution(
            str(nested_dir), "gearbox.plugins"
        )

    assert found_dist is dist
    assert found_path == str(project_root)


def test_load_commands_for_package_logs_context_when_distribution_missing(caplog):
    app = GearBox()

    with patch(
        "importlib.metadata.packages_distributions",
        return_value={"tg": ["TurboGears2.devtools"]},
    ), patch(
        "importlib.metadata.distribution",
        side_effect=importlib.metadata.PackageNotFoundError("missing"),
    ):
        with caplog.at_level("ERROR", logger="gearbox"):
            app.load_commands_for_package("tg.devtools")

    assert (
        "Failed to load project commands for package 'tg.devtools'" in caplog.text
    )
    assert "Have you installed your project?" in caplog.text


def test_version_option_uses_gearbox_version_fallback(capsys, monkeypatch):
    monkeypatch.setattr(GearBox, "VERSION", "unknown-test")
    app = GearBox()
    with pytest.raises(SystemExit):
        app.run(["--version"])
    assert "unknown-test" in capsys.readouterr().out
