import importlib
import os

from paste.deploy import appconfig

from gearbox.command import Command


class SetupAppCommand(Command):
    def get_description(self):
        return "Setup an application, given a config file"

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)

        parser.add_argument(
            "-c",
            "--config",
            help="application config file to read (default: development.ini)",
            dest="config_file",
            default="development.ini",
        )

        parser.add_argument(
            "--name",
            action="store",
            dest="section_name",
            default=None,
            help="The name of the section to set up (default: app:main)",
        )

        return parser

    def take_action(self, opts):
        config_spec = opts.config_file
        section = opts.section_name
        if section is None:
            if "#" in config_spec:
                config_spec, section = config_spec.split("#", 1)
            else:
                section = "main"
        if ":" not in section:
            plain_section = section
            section = "app:" + section
        else:
            plain_section = section.split(":", 1)[0]
        if not config_spec.startswith("config:"):
            config_spec = "config:" + config_spec
        if plain_section != "main":
            config_spec += "#" + plain_section
        config_file = config_spec[len("config:") :].split("#", 1)[0]
        config_file = os.path.join(os.getcwd(), config_file)
        conf = appconfig(config_spec, relative_to=os.getcwd())
        # ep_name = conf.context.entry_point_name
        # ep_group = conf.context.protocol
        dist = conf.context.distribution
        if dist is None:
            raise RuntimeError(
                "The section %r is not the application (probably a filter).  You should add #section_name, where section_name is the section that configures your application"
                % plain_section
            )

        self._setup_config(
            dist, config_file, section, {}, verbosity=self.app.options.verbose_level
        )

    def _setup_config(self, dist, filename, section, vars, verbosity):
        """
        Called to setup an application, given its configuration
        file/directory.

        The default implementation calls
        ``package.websetup.setup_config(command, filename, section,
        vars)`` or ``package.websetup.setup_app(command, config,
        vars)``

        With ``setup_app`` the ``config`` object is a dictionary with
        the extra attributes ``global_conf``, ``local_conf`` and
        ``filename``
        """
        modules = self._find_websetup_modules(dist)

        if not modules:
            print("Unable to find any websetup modules from distribution metadata.")
            print("Try reinstalling the application and rerun setup-app.")
            return

        modules = sorted(set(modules))

        websetup_executed = False
        for mod_name in modules:
            mod_name = mod_name + ".websetup"
            try:
                mod = self._import_module(mod_name)
            except ModuleNotFoundError as e:
                print(e)
                mod = None

            if mod is None:
                continue

            if hasattr(mod, "setup_app"):
                if verbosity:
                    print("Running setup_app() from %s" % mod_name)
                websetup_executed = True
                self._call_setup_app(mod.setup_app, filename, section, vars)
            elif hasattr(mod, "setup_config"):
                if verbosity:
                    print("Running setup_config() from %s" % mod_name)
                websetup_executed = True
                mod.setup_config(None, filename, section, vars)
            else:
                print(
                    "No setup_app() or setup_config() function in %s (%s)"
                    % (mod.__name__, mod.__file__)
                )

        if not websetup_executed:
            print("No websetup found in any of the top modules")

    def _find_websetup_modules(self, dist):
        modules = []
        for path in dist.files or ():
            parts = tuple(path.parts)
            if any(part.endswith((".dist-info", ".egg-info")) for part in parts):
                continue

            if parts[-1] == "websetup.py":
                package_parts = parts[:-1]
            elif len(parts) >= 2 and parts[-2:] == ("websetup", "__init__.py"):
                package_parts = parts[:-2]
            else:
                continue

            if not package_parts:
                continue
            if not all(part.isidentifier() for part in package_parts):
                continue

            modules.append(".".join(package_parts))

        if modules:
            return sorted(set(modules))

        return self._find_websetup_modules_from_top_level(dist)

    def _find_websetup_modules_from_top_level(self, dist):
        top_level_text = dist.read_text("top_level.txt")
        if not top_level_text:
            return []

        return [
            line.strip()
            for line in top_level_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _call_setup_app(self, func, filename, section, vars):
        filename = os.path.abspath(filename)
        if ":" in section:
            section = section.split(":", 1)[1]
        conf = "config:%s#%s" % (filename, section)
        conf = appconfig(conf)
        conf.filename = filename
        func(None, conf, vars)

    def _import_module(self, s):
        """
        Import a module.
        """
        return importlib.import_module(s)
