About gearbox
-------------------------

gearbox is a paster command replacement for TurboGears2.
It has been created during the process of providing Python3 support to the TurboGears2 web framework,
while still being backward compatible with the existing TurboGears projects.

Installing
-------------------------------

gearbox can be installed from pypi::

    easy_install gearbox

or::

    pip install gearbox

should just work for most of the users

Out of The Box
------------------------------

Just by installing gearbox itself your TurboGears project will be able to use gearbox system wide
commands like ``gearbox serve``, ``gearbox setup-app`` and ``gearbox makepackage`` commands.
These commands provide a replacement for the paster serve, paster setup-app and paster create commands.

The main difference with the paster command is usually only that gearbox commands explicitly set the
configuration file using the ``--config`` option instead of accepting it positionally.  By default gearbox
will always load a configuration file named `development.ini`, this mean you can simply run ``gearbox serve``
in place of ``paster serve development.ini``

To have a list of the available commands simply run ``gearbox --help``::

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


Then it is possible to ask for help for a given command by using ``gearbox help command``::

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

Installing the TurboGears 2.3 development tools you will get access some some gearbox commands specific
to TurboGears2 projects management, those are the ``gearbox quickstart``, ``gearbox tgshell`` and
``gearbox migrate`` commands.

While the *quickstart* command will be automatically available, you will have to enable project scope plugins
for gearbox before the other two became available. This will let gearbox know that you are running it inside
a TurboGears2 project and so that the commands that only make sense for TurboGears2 projects will became available.

Enabling migrate and tgshell commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To enable ``gearbox migrate`` and ``gearbox tgshell`` commands make sure that your *setup.py* `entry_points`
look like::

    entry_points={
        'paste.app_factory': [
            'main = makonoauth.config.middleware:make_app'
        ],
        'gearbox.plugins': [
            'turbogears-devtools = tg.devtools'
        ]
    }

The **paste.app_factory** section will let ``gearbox serve`` know how to create the application that
has to be served. Gearbox relies on PasteDeploy for application setup, so it required a paste.app_factory
section to be able to correctly load the application.

While the **gearbox.plugins** section will let *gearbox* itself know that inside that directory the tg.devtools
commands have to be enabled making ``gearbox tgshell`` and ``gearbox migrate`` available when we run gearbox
from inside our project directory.

Gearbox Interactive Mode
-------------------------------

By default launching gearbox without any subcommand will start the interactive mode.
This provides an interactive prompt where gearbox commands, system shell commands and python statements
can be executed. If you have any doubt about what you can do simply run the ``help`` command to get
a list of the commands available (running ``help somecommand`` will provide help for the given sub command).

Gearbox HTTP Servers
------------------------------

If you are moving your TurboGears2 project from paster you will probably end serving your
application with Paste HTTP server even if you are using the ``gearbox serve`` command.

The reason for this behavior is that gearbox is going to use what is specified inside
the **server:main** section of your *.ini* file to serve your application.
TurboGears2 projects quickstarted before 2.3 used Paste and so the projects is probably
configured to use Paste#http as the server. This is not an issue by itself, it will just require
you to have Paste installed to be able to serve the application, to totally remove the Paste
dependency simply replace **Paste#http** with **gearbox#wsgiref**.

Serving with GEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gearbox cames with builtin support for gevent, so serving an application under Gevent
is just a matter of using **gearbox#gevent** as your server inside the **server:main** section
of the configuration file.

The gearbox gevent server will automatically monkeypatch all the python modules apart
from the DNS related functions before loading your application.
Not much more apart making sure that your code is gevent compatible is required.

Writing new gearbox commands
---------------------------------

gearbox relies on the Cliff command framework for commands crations. Most of what
the `Cliff <https://cliff.readthedocs.org/en/latest/>`_ documentation states is perfectly
valid for gearbox commands, some differences only apply in the case of *Template based commands*.

Template Based Commands
~~~~~~~~~~~~~~~~~~~~~~~~

Writing new gearbox template commands is as simple as creating a **gearbox.command.TemplateCommand** subclass and
place it inside a *command.py* file in a python package.

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
