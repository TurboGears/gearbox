About gearbox
-------------------------

Gearbox is a command-line tool designed as a replacement for `paster` in TurboGears2 projects.
It originated during the effort to provide Python 3 support for TurboGears2, while maintaining
compatibility with existing projects.

Gearbox is built upon a streamlined version of the *Cliff* command-line framework. For more complex
command-line applications and custom interpreters, consider exploring `Cliff <https://cliff.readthedocs.io/en/latest/>`_.

Installing
-------------------------------

Install gearbox using pip::

    pip install gearbox

Out of The Box
------------------------------

Installing gearbox provides system-wide commands for TurboGears projects, including
``gearbox serve``, ``gearbox setup-app``, and ``gearbox makepackage``. These commands
replace their `paster` counterparts.

The primary difference from `paster` is that Gearbox commands require explicit specification of the
configuration file using the ``--config`` option. By default, Gearbox loads `development.ini`.
Therefore, ``gearbox serve`` can be used instead of ``paster serve development.ini``.

To view a list of available commands, run ``gearbox --help``::

    $ gearbox --help
    usage: gearbox [--version] [-v] [--log-file LOG_FILE] [-q] [-h] [--debug]

    TurboGears2 Gearbox toolset

    optional arguments:
      --version            show program's version number and exit
      -v, --verbose        Increase verbosity of output. Can be repeated.
      --log-file LOG_FILE  Specify a file to log output. Disabled by default.
      -q, --quiet          suppress output except warnings and errors
      -h, --help           show this help message and exit
      --debug              show tracebacks on errors

    Commands:
      help           print detailed help for another command
      makepackage    Creates a basic python package
      migrate        Handles TurboGears2 Database Migrations
      quickstart     Creates a new TurboGears2 project
      serve          Serves a web application that uses a PasteDeploy configuration file
      setup-app      Setup an application, given a config file
      tgshell        Opens an interactive shell with a TurboGears2 app loaded
      scaffold       Creates a new file from a scaffold template
      patch          Patches files by replacing, appending or deleting text.

For detailed help on a specific command, use ``gearbox help command``::

    $ gearbox help serve
    usage: gearbox serve [-h] [-n NAME] [-s SERVER_TYPE]
                         [--server-name SECTION_NAME] [--daemon]
                         [--pid-file FILENAME] [--reload]
                         [--reload-interval RELOAD_INTERVAL] [--monitor-restart]
                         [--status] [--user USERNAME] [--group GROUP]
                         [--stop-daemon] [-c CONFIG_FILE]
                         [args [args ...]]

    Serves a web application that uses a PasteDeploy configuration file

    positional arguments:
      args

    optional arguments:
      -h, --help            show this help message and exit
      -n NAME, --app-name NAME
                            Load the named application (default main)
      -s SERVER_TYPE, --server SERVER_TYPE
                            Use the named server.
      --server-name SECTION_NAME
                            Use the named server as defined in the configuration
                            file (default: main)
      --daemon              Run in daemon (background) mode
      --pid-file FILENAME   Save PID to file (default to gearbox.pid if running in
                            daemon mode)
      --reload              Use auto-restart file monitor
      --reload-interval RELOAD_INTERVAL
                            Seconds between checking files (low number can cause
                            significant CPU usage)
      --monitor-restart     Auto-restart server if it dies
      --status              Show the status of the (presumably daemonized) server
      --user USERNAME       Set the user (usually only possible when run as root)
      --group GROUP         Set the group (usually only possible when run as root)
      --stop-daemon         Stop a daemonized server (given a PID file, or default
                            gearbox.pid file)
      -c CONFIG_FILE, --config CONFIG_FILE
                            application config file to read (default:
                            development.ini)


Development Tools Commands
-------------------------------

Installing the TurboGears development tools provides access to gearbox commands
specific to TurboGears2 project management: ``gearbox quickstart``, ``gearbox tgshell``, and
``gearbox migrate``.

The *quickstart* command is immediately available. However, project-scope plugins must be
enabled for Gearbox to recognize a TurboGears2 project and make the other two commands available.

Enabling migrate and tgshell commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable ``gearbox migrate`` and ``gearbox tgshell``, ensure that the `[project.entry-points."gearbox.plugins"]` section
in your `pyproject.toml` resembles the following:

.. code-block:: toml

    [project.entry-points."gearbox.plugins"]
    turbogears-devtools = "tg.devtools"


Gearbox Interactive Mode
-------------------------------

Running gearbox without a subcommand starts the interactive mode. This provides a prompt
for executing Gearbox commands, system shell commands, and Python statements. Use the
``help`` command to list available commands (``help somecommand`` provides help for a
specific command).

Gearbox HTTP Servers
------------------------------

When migrating a TurboGears2 project from `paster`, you might still be serving the
application with the Paste HTTP server even when using ``gearbox serve``.

This occurs because Gearbox uses the settings in the **server:main** section of your *.ini*
file. Projects created before TurboGears2 used Paste, so the project is likely configured
to use `Paste#http` as the server. This requires Paste to be installed. To remove the Paste
dependency, replace `Paste#http` with `gearbox#wsgiref`.

The **gearbox#wsgiref** server also supports an experimental multithreaded version, enabled by
setting `wsgiref.threaded = true` in the server configuration section.

Serving with GEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gearbox includes built-in support for gevent. To serve an application with Gevent, use
**gearbox#gevent** as the server in the **server:main** section of the configuration file.

The Gearbox gevent server automatically monkey patches all Python modules except for
DNS-related functions before loading the application. Ensure your code is gevent-compatible.

Scaffolding
-----------

Scaffolding creates new application components from templates.

The ``gearbox scaffold`` command creates files from scaffolds (file templates) placed within
your project. Scaffold files should have the ``.template`` extension and are used as follows::

    $ gearbox scaffold templatename target

This creates a `target` file (without specifying the extension, which is defined in the
`templatename` scaffold) from the `templatename` scaffold.

A typical scaffold filename is `model.py.template` and contains:

.. code-block:: python

    class {{target.capitalize()}}(DeclarativeBase):
        __tablename__ = '{{target.lower()}}s'

        uid = Column(Integer, primary_key=True)
        data = Column(Unicode(255), nullable=False)

The scaffold command also supports looking up templates in specific paths using the `-l` or `--lookup` option,
and placing the newly created files in a specific directory using the `-p` or `--path` option.
You can also create the files in a subdirectory using the `-s` or `--subdir` option.

Patching
--------

``patch`` is a built-in Gearbox command for updating code. It functions as a Python-enhanced
`sed` command.

Examples:

Replace all `xi:include` occurrences with `py:extends` in all HTML template files recursively::

    $ gearbox patch -R '*.html' xi:include -r py:extends

Update the copyright year in documentation using regular expressions and Python::

    $ gearbox patch -R '*.rst' -x 'Copyright(\s*)(\d+)' -e -r '"Copyright\\g<1>"+__import__("datetime").datetime.utcnow().strftime("%Y")'

Refer to ``gearbox help patch`` for available options.

Writing new gearbox commands
----------------------------

Gearbox automatically loads commands registered as setuptools entry points under the
`[project.entry-points."gearbox.commands"]` key in `pyproject.toml`. To create a new command, subclass ``gearbox.command.Command``,
and override the `get_parser` and `take_action` methods to define custom options and behavior:

.. code-block:: python

    class MyCcommand(Command):
        def take_action(self, opts):
            print('Hello World!')

Register the command in the `[project.entry-points."gearbox.commands"]` section of your `pyproject.toml`:

.. code-block:: toml

    [project.entry-points."gearbox.commands"]
    mycommand = "mypackage.commands:MyCommand"

Template Based Commands
~~~~~~~~~~~~~~~~~~~~~~~

Creating new template commands involves subclassing
**gearbox.command.TemplateCommand** within a `command.py` file in a Python package.

Inherit from the class and implement the *get_description*, *get_parser* and *take_action* methods
as described by the  documentation.

The only difference is that your *take_action* method has to end by calling ``self.run_template(output_dir, opts)``
where *output_dir* is the directory where the template output has to be written and *opts* are the command options
as your take_action method received them.

When the run_template command is called Gearbox will automatically run the **template**
directory in the same package where the command was available.

Each file ending with the *_tmpl* syntax will be processed with the Tempita template engine and
whenever the name of a file or directory contains *+optname+* it will be substituted with the
value of the option having the same name (e.g., +package+ will be substituted with the value
of the --package options which will probably end being the name of the package).
