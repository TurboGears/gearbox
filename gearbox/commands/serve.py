# (c) 2005 Ian Bicking and contributors; written for Paste
# (http://pythonpaste.org) Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license.php
#
# For discussion of daemonizing:
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/278731
#
# Code taken also from QP: http://www.mems-exchange.org/software/qp/ From
# lib/site.py

import atexit
import ctypes
import errno
import logging
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import platform

import hupper
import hupper.reloader
from paste.deploy import loadapp, loadserver
from paste.deploy.converters import asbool

from gearbox.utils.log import setup_logging
from gearbox.command import Command

MAXFD = 1024

if platform.system() == 'Windows' and not hasattr(os, 'kill'): # pragma: no cover
    # py 2.6 on windows
    def kill(pid, sig=None):
        """kill function for Win32"""
        # signal is ignored, semibogus raise message
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(1, 0, pid)
        if (0 == kernel32.TerminateProcess(handle, 0)):
            raise OSError('No such process %s' % pid)
else:
    kill = os.kill


class DaemonizeException(Exception):
    pass


class ServeCommand(Command):
    _scheme_re = re.compile(r'^[a-z][a-z]+:', re.I)

    _monitor_environ_key = 'PASTE_MONITOR_SHOULD_RUN'

    possible_subcommands = ('start', 'stop', 'restart', 'status')

    def get_parser(self, prog_name):
        parser = super(ServeCommand, self).get_parser(prog_name)

        parser.add_argument("-c", "--config",
            help='application config file to read (default: development.ini)',
            dest='config_file', default="development.ini")

        parser.add_argument(
            '-n', '--app-name',
            dest='app_name',
            metavar='NAME',
            help="Load the named application (default main)")
        parser.add_argument(
            '-s', '--server',
            dest='server',
            metavar='SERVER_TYPE',
            help="Use the named server.")
        parser.add_argument(
            '--server-name',
            dest='server_name',
            metavar='SECTION_NAME',
            help=("Use the named server as defined in the configuration file "
                  "(default: main)"))
        if hasattr(os, 'fork'):
            parser.add_argument(
                '--daemon',
                dest="daemon",
                action="store_true",
                help="Run in daemon (background) mode")
        parser.add_argument(
            '--pid-file',
            dest='pid_file',
            metavar='FILENAME',
            help=("Save PID to file (default to gearbox.pid if running in "
                  "daemon mode)"))
        parser.add_argument(
            '--reload',
            dest='reload',
            action='store_true',
            help="Use auto-restart file monitor")
        parser.add_argument(
            '--reload-interval',
            dest='reload_interval',
            default=1,
            help=("Seconds between checking files (low number can cause "
                  "significant CPU usage)"))
        parser.add_argument(
            '--monitor-restart',
            dest='monitor_restart',
            action='store_true',
            help="Auto-restart server if it dies")
        parser.add_argument(
            '--status',
            action='store_true',
            dest='show_status',
            help="Show the status of the (presumably daemonized) server")

        if hasattr(os, 'setuid'):
            # I don't think these are available on Windows
            parser.add_argument(
                '--user',
                dest='set_user',
                metavar="USERNAME",
                help="Set the user (usually only possible when run as root)")
            parser.add_argument(
                '--group',
                dest='set_group',
                metavar="GROUP",
                help="Set the group (usually only possible when run as root)")
    
        parser.add_argument(
            '--stop-daemon',
            dest='stop_daemon',
            action='store_true',
            help=('Stop a daemonized server (given a PID file, or default '
                  'gearbox.pid file)'))

        parser.add_argument('args', nargs='*')

        return parser

    def get_description(self):
        return 'Serves a web application that uses a PasteDeploy configuration file'

    @classmethod
    def out(cls, msg, error=False): # pragma: no cover
        log = logging.getLogger('gearbox')
        if error:
            log.error(msg)
        else:
            log.info(msg)

    def take_action(self, opts):
        if opts.stop_daemon:
            return self.stop_daemon(opts)

        if not hasattr(opts, 'set_user'):
            # Windows case:
            opts.set_user = opts.set_group = None

        self.verbose = self.app_args.verbose_level

        # @@: Is this the right stage to set the user at?
        self.change_user_group(opts.set_user, opts.set_group)

        app_spec = opts.config_file
        if opts.args and opts.args[0] in self.possible_subcommands:
            cmd = opts.args[0]
            restvars = opts.args[1:]
        else:
            cmd = None
            restvars = opts.args[0:]

        if cmd not in (None, 'start', 'stop', 'restart', 'status'):
            self.out('Error: must give start|stop|restart (not %s)' % cmd)
            return 2

        if cmd == 'status' or opts.show_status:
            return self.show_status(opts)

        if opts.monitor_restart and opts.reload:
            self.out('Cannot user --monitor-restart with --reload')
            return 2

        if opts.monitor_restart and not os.environ.get(self._monitor_environ_key):
            # gearbox serve was started with an angel and we are not already inside the angel.
            # Switch this process to being the angel and start a new one with the real server.
            return self.restart_with_monitor()

        if opts.reload and not hupper.is_active():
            if self.verbose > 1:
                self.out('Running reloading file monitor')
            reloader = hupper.reloader.Reloader(
                worker_path='gearbox.main.main',
                reload_interval=opts.reload_interval,
                monitor_factory=hupper.reloader.find_default_monitor_factory(
                    logging.getLogger('gearbox')
                ),
                logger=logging.getLogger('gearbox'),
            )
            reloader.run()

        if hupper.is_active():
            # Tack also config file changes
            hupper.get_reloader().watch_files([opts.config_file])

        if cmd == 'restart' or cmd == 'stop':
            result = self.stop_daemon(opts)
            if result:
                if cmd == 'restart':
                    self.out("Could not stop daemon; aborting")
                else:
                    self.out("Could not stop daemon")
                return result
            if cmd == 'stop':
                return result
            opts.daemon = True

        if cmd == 'start':
            opts.daemon = True

        app_name = opts.app_name
        parsed_vars = self.parse_vars(restvars)
        if not self._scheme_re.search(app_spec):
            app_spec = 'config:' + app_spec
        server_name = opts.server_name
        if opts.server:
            server_spec = 'egg:gearbox'
            assert server_name is None
            server_name = opts.server
        else:
            server_spec = app_spec
        base = os.getcwd()

        if getattr(opts, 'daemon', False):
            if not opts.pid_file:
                opts.pid_file = 'gearbox.pid'

        # Ensure the pid file is writeable
        if opts.pid_file:
            try:
                writeable_pid_file = open(opts.pid_file, 'a')
            except IOError as ioe:
                msg = 'Error: Unable to write to pid file: %s' % ioe
                raise ValueError(msg)
            writeable_pid_file.close()

        if getattr(opts, 'daemon', False):
            try:
                self.daemonize(opts)
            except DaemonizeException as ex:
                if self.verbose > 0:
                    self.out(str(ex))
                return 2

        if opts.pid_file:
            self.record_pid(opts.pid_file)

        log_fn = app_spec
        if log_fn.startswith('config:'):
            log_fn = app_spec[len('config:'):]
        elif log_fn.startswith('egg:'):
            log_fn = None

        if self.app.options.log_file:
            stdout_log = LazyWriter(self.app.options.log_file, 'a')
            sys.stdout = stdout_log
            sys.stderr = stdout_log

        try:
            server = self.loadserver(server_spec, name=server_name,
                                     relative_to=base, global_conf=parsed_vars)
        except Exception:
            self.out('Failed to load server', error=True)
            raise

        if log_fn:
            log_fn = os.path.join(base, log_fn)
            setup_logging(log_fn)

        try:
            app = self.loadapp(app_spec, name=app_name,
                               relative_to=base, global_conf=parsed_vars)
        except Exception:
            self.out('Failed to load application', error=True)
            raise

        if self.verbose > 0:
            if hasattr(os, 'getpid'):
                msg = 'Starting server in PID %i.' % os.getpid()
            else:
                msg = 'Starting server.'
            self.out(msg)

        def serve():
            try:
                server(app)
            except (SystemExit, KeyboardInterrupt) as e:
                if self.verbose > 1:
                    raise
                if str(e):
                    msg = ' ' + str(e)
                else:
                    msg = ''
                self.out('Exiting%s (-v to see traceback)' % msg)

        serve()

    def loadserver(self, server_spec, name, relative_to, **kw):# pragma:no cover
        return loadserver(
            server_spec, name=name, relative_to=relative_to, **kw)

    def loadapp(self, app_spec, name, relative_to, **kw): # pragma: no cover
        return loadapp(app_spec, name=name, relative_to=relative_to, **kw)

    def parse_vars(self, args):
        """
        Given variables like ``['a=b', 'c=d']`` turns it into ``{'a':
        'b', 'c': 'd'}``
        """
        result = {}
        for arg in args:
            if '=' not in arg:
                raise ValueError(
                    'Variable assignment %r invalid (no "=")'
                    % arg)
            name, value = arg.split('=', 1)
            result[name] = value
        return result

    def get_fixed_argv(self):  # pragma: no cover
        """Get proper arguments for re-running the command.

        This is primarily for fixing some issues under Windows.

        First, there was a bug in Windows when running an executable
        located at a path with a space in it. This has become a
        non-issue with current versions of Python and Windows,
        so we don't take measures like adding quotes or calling
        win32api.GetShortPathName() as was necessary in former times.

        Second, depending on whether gearbox was installed as an egg
        or a wheel under Windows, it is run as a .py or an .exe stub.
        In the first case, we need to run it through the interpreter.
        On other operating systems, we can re-run the command as is.

        """
        argv = sys.argv[:]
        if sys.platform == 'win32' and argv[0].endswith('.py'):
            argv.insert(0, sys.executable)
        return argv

    def daemonize(self, opts): # pragma: no cover
        pid = live_pidfile(opts.pid_file)
        if pid:
            raise DaemonizeException(
                "Daemon is already running (PID: %s from PID file %s)"
                % (pid, opts.pid_file))

        if self.verbose > 0:
            self.out('Entering daemon mode')
        pid = os.fork()
        if pid:
            # The forked process also has a handle on resources, so we
            # *don't* want proper termination of the process, we just
            # want to exit quick (which os._exit() does)
            os._exit(0)
            # Make this the session leader
        os.setsid()
        # Fork again for good measure!
        pid = os.fork()
        if pid:
            os._exit(0)

        # @@: Should we set the umask and cwd now?

        import resource  # Resource usage information.
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if (maxfd == resource.RLIM_INFINITY):
            maxfd = MAXFD
            # Iterate through and close all file descriptors.
        for fd in range(0, maxfd):
            try:
                os.close(fd)
            except OSError:  # ERROR, fd wasn't open to begin with (ignored)
                pass

        if (hasattr(os, "devnull")):
            REDIRECT_TO = os.devnull
        else:
            REDIRECT_TO = "/dev/null"
        os.open(REDIRECT_TO, os.O_RDWR)  # standard input (0)
        # Duplicate standard input to standard output and standard error.
        os.dup2(0, 1)  # standard output (1)
        os.dup2(0, 2)  # standard error (2)

    def _remove_pid_file(self, written_pid, filename, verbosity):
        current_pid = os.getpid()
        if written_pid != current_pid:
            # A forked process must be exiting, not the process that
            # wrote the PID file
            return
        if not os.path.exists(filename):
            return
        with open(filename) as f:
            content = f.read().strip()
        try:
            pid_in_file = int(content)
        except ValueError:
            pass
        else:
            if pid_in_file != current_pid:
                msg = "PID file %s contains %s, not expected PID %s"
                self.out(msg % (filename, pid_in_file, current_pid))
                return
        if verbosity > 0:
            self.out("Removing PID file %s" % filename)
        try:
            os.unlink(filename)
            return
        except OSError as e:
            # Record, but don't give traceback
            self.out("Cannot remove PID file: (%s)" % e)
            # well, at least lets not leave the invalid PID around...
        try:
            with open(filename, 'w') as f:
                f.write('')
        except OSError as e:
            self.out('Stale PID left in file: %s (%s)' % (filename, e))
        else:
            self.out('Stale PID removed')

    def record_pid(self, pid_file):
        pid = os.getpid()
        if self.verbose > 1:
            self.out('Writing PID %s to %s' % (pid, pid_file))
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        atexit.register(self._remove_pid_file, pid, pid_file, self.verbose)

    def stop_daemon(self, opts): # pragma: no cover
        pid_file = opts.pid_file or 'gearbox.pid'
        if not os.path.exists(pid_file):
            self.out('No PID file exists in %s' % pid_file)
            return 1
        pid = read_pidfile(pid_file)
        if not pid:
            self.out("Not a valid PID file in %s" % pid_file)
            return 1
        pid = live_pidfile(pid_file)
        if not pid:
            self.out("PID in %s is not valid (deleting)" % pid_file)
            try:
                os.unlink(pid_file)
            except (OSError, IOError) as e:
                self.out("Could not delete: %s" % e)
                return 2
            return 1
        for j in range(10):
            if not live_pidfile(pid_file):
                break
            import signal
            kill(pid, signal.SIGTERM)
            time.sleep(1)
        else:
            self.out("failed to kill web process %s" % pid)
            return 3
        if os.path.exists(pid_file):
            os.unlink(pid_file)
        return 0

    def show_status(self, opts): # pragma: no cover
        pid_file = opts.pid_file or 'gearbox.pid'
        if not os.path.exists(pid_file):
            self.out('No PID file %s' % pid_file)
            return 1
        pid = read_pidfile(pid_file)
        if not pid:
            self.out('No PID in file %s' % pid_file)
            return 1
        pid = live_pidfile(pid_file)
        if not pid:
            self.out('PID %s in %s is not running' % (pid, pid_file))
            return 1
        self.out('Server running in PID %s' % pid)
        return 0

    def restart_with_monitor(self):  # pragma: no cover
        if self.verbose > 0:
            self.out('Starting subprocess with angel')

        while 1:
            args = self.get_fixed_argv()
            new_environ = os.environ.copy()
            new_environ[self._monitor_environ_key] = 'true'
            proc = None
            try:
                try:
                    _turn_sigterm_into_systemexit()
                    proc = subprocess.Popen(args, env=new_environ)
                    exit_code = proc.wait()
                    proc = None
                except KeyboardInterrupt:
                    self.out('^C caught in monitor process')
                    if self.verbose > 1:
                        raise
                    return 1
            finally:
                if proc is not None:
                    import signal
                    try:
                        kill(proc.pid, signal.SIGTERM)
                    except (OSError, IOError):
                        pass

            if self.verbose > 0:
                self.out('%s %s %s' % ('-' * 20, 'Server died, restarting', '-' * 20))

    def change_user_group(self, user, group): # pragma: no cover
        if not user and not group:
            return
        import pwd, grp
        uid = gid = None
        if group:
            try:
                gid = int(group)
                group = grp.getgrgid(gid).gr_name
            except ValueError:
                import grp
                try:
                    entry = grp.getgrnam(group)
                except KeyError:
                    raise ValueError(
                        "Bad group: %r; no such group exists" % group)
                gid = entry.gr_gid
        try:
            uid = int(user)
            user = pwd.getpwuid(uid).pw_name
        except ValueError:
            try:
                entry = pwd.getpwnam(user)
            except KeyError:
                raise ValueError(
                    "Bad username: %r; no such user exists" % user)
            if not gid:
                gid = entry.pw_gid
            uid = entry.pw_uid
        if self.verbose > 0:
            self.out('Changing user to %s:%s (%s:%s)' % (
                user, group or '(unknown)', uid, gid))
        if gid:
            os.setgid(gid)
        if uid:
            os.setuid(uid)


class LazyWriter(object):

    """
    File-like object that opens a file lazily when it is first written
    to.
    """

    def __init__(self, filename, mode='w'):
        self.filename = filename
        self.fileobj = None
        self.lock = threading.Lock()
        self.mode = mode

    def open(self):
        if self.fileobj is None:
            with self.lock:
                self.fileobj = open(self.filename, self.mode)
        return self.fileobj

    def close(self):
        fileobj = self.fileobj
        if fileobj is not None:
            fileobj.close()

    def __del__(self):
        self.close()

    def write(self, text):
        fileobj = self.open()
        fileobj.write(text)
        fileobj.flush()

    def writelines(self, text):
        fileobj = self.open()
        fileobj.writelines(text)
        fileobj.flush()

    def flush(self):
        self.open().flush()


def live_pidfile(pidfile): # pragma: no cover
    """(pidfile:str) -> int | None
    Returns an int found in the named file, if there is one,
    and if there is a running process with that process id.
    Return None if no such process exists.
    """
    pid = read_pidfile(pidfile)
    if pid:
        try:
            kill(int(pid), 0)
            return pid
        except OSError as e:
            if e.errno == errno.EPERM:
                return pid
    return None


def read_pidfile(filename):
    if os.path.exists(filename):
        try:
            with open(filename) as f:
                content = f.read()
            return int(content.strip())
        except (ValueError, IOError):
            return None
    else:
        return None


def _turn_sigterm_into_systemexit(): # pragma: no cover
    """
    Attempts to turn a SIGTERM exception into a SystemExit exception.
    """
    try:
        import signal
    except ImportError:
        return
    def handle_term(signo, frame):
        raise SystemExit
    signal.signal(signal.SIGTERM, handle_term)


# For paste.deploy server instantiation (egg:gearbox#wsgiref)
def wsgiref_server_runner(wsgi_app, global_conf, **kw): # pragma: no cover
    """
    Entry point for wsgiref's WSGI server

    Additional parameters:

    ``certfile``, ``keyfile``

        Optional SSL certificate file and host key file names. You can
        generate self-signed test files as follows:

            $ openssl genrsa 1024 > keyfile
            $ chmod 400 keyfile
            $ openssl req -new -x509 -nodes -sha1 -days 365  \\
                          -key keyfile > certfile
            $ chmod 400 certfile

        The file names should contain full paths.

    """
    from wsgiref.simple_server import make_server, WSGIServer

    host = kw.get('host', '0.0.0.0')
    port = int(kw.get('port', 8080))
    threaded = asbool(kw.get('wsgiref.threaded', False))

    server_class = WSGIServer
    certfile = kw.get('wsgiref.certfile')
    keyfile = kw.get('wsgiref.keyfile')
    scheme = 'http'

    if certfile and keyfile:
        """
        based on code from nullege:
        description='Dropbox REST API Client with more consistent responses.',
        author='Rick van Hattem',
        author_email='Rick@Wol.ph',
        url='http://wol.ph/',
        """
        import ssl
        class SecureWSGIServer(WSGIServer):

            def get_request(self):
                socket, client_address = WSGIServer.get_request(self)
                socket = ssl.wrap_socket(socket,
                                         server_side=True,
                                         certfile=certfile,
                                         keyfile=keyfile)
                return socket, client_address

        port = int(kw.get('port', 4443))
        server_class = SecureWSGIServer

    if threaded:
        from SocketServer import ThreadingMixIn
        class GearboxWSGIServer(ThreadingMixIn, server_class): pass
        server_type = 'Threaded'
    else:
        class GearboxWSGIServer(server_class): pass
        server_type = 'Standard'

    server = make_server(host, port, wsgi_app, server_class=GearboxWSGIServer)
    if certfile and keyfile:
        server_type += ' Secure'
        scheme += 's'
    ServeCommand.out('Starting %s HTTP server on %s://%s:%s' % (server_type, scheme, host, port))
    server.serve_forever()


# For paste.deploy server instantiation (egg:gearbox#gevent)
def gevent_server_factory(global_config, **kw):
    from gevent import reinit
    try:
        from gevent.pywsgi import WSGIServer
    except ImportError:
        from gevent.wsgi import WSGIServer
    from gevent.monkey import patch_all
    reinit()
    patch_all(dns=False)
    
    host = kw.get('host', '0.0.0.0')
    port = int(kw.get('port', 8080))

    def _gevent_serve(wsgi_app):
        ServeCommand.out('Starting Gevent HTTP server on http://%s:%s' % (host, port))
        WSGIServer((host, port), wsgi_app).serve_forever()

    return _gevent_serve


# For paste.deploy server instantiation (egg:gearbox#cherrypy)
def cherrypy_server_runner(
        app, global_conf=None, host='127.0.0.1', port=None,
        ssl_pem=None, protocol_version=None, numthreads=None,
        server_name=None, max=None, request_queue_size=None,
        timeout=None
): # pragma: no cover
    """
    Entry point for CherryPy's WSGI server

    Serves the specified WSGI app via CherryPyWSGIServer.

    ``app``

        The WSGI 'application callable'; multiple WSGI applications
        may be passed as (script_name, callable) pairs.

    ``host``

        This is the ipaddress to bind to (or a hostname if your
        nameserver is properly configured).  This defaults to
        127.0.0.1, which is not a public interface.

    ``port``

        The port to run on, defaults to 8080 for HTTP, or 4443 for
        HTTPS. This can be a string or an integer value.

    ``ssl_pem``

        This an optional SSL certificate file (via OpenSSL) You can
        generate a self-signed test PEM certificate file as follows:

            $ openssl genrsa 1024 > host.key
            $ chmod 400 host.key
            $ openssl req -new -x509 -nodes -sha1 -days 365  \\
                          -key host.key > host.cert
            $ cat host.cert host.key > host.pem
            $ chmod 400 host.pem

    ``protocol_version``

        The protocol used by the server, by default ``HTTP/1.1``.

    ``numthreads``

        The number of worker threads to create.

    ``server_name``

        The string to set for WSGI's SERVER_NAME environ entry.

    ``max``

        The maximum number of queued requests. (defaults to -1 = no
        limit).

    ``request_queue_size``

        The 'backlog' argument to socket.listen(); specifies the
        maximum number of queued connections.

    ``timeout``

        The timeout in seconds for accepted connections.
    """
    is_ssl = False
    if ssl_pem:
        port = port or 4443
        is_ssl = True

    if not port:
        if ':' in host:
            host, port = host.split(':', 1)
        else:
            port = 8080
    bind_addr = (host, int(port))

    kwargs = {}
    for var_name in ('numthreads', 'max', 'request_queue_size', 'timeout'):
        var = locals()[var_name]
        if var is not None:
            kwargs[var_name] = int(var)

    server = None
    try:
        # Try to import from newer CherryPy releases.
        import cheroot.wsgi as wsgiserver
        server = wsgiserver.Server(bind_addr, app,
            server_name=server_name, **kwargs)
    except ImportError:
        # Nope. Try to import from older CherryPy releases.
        # We might just take another ImportError here. Oh well.
        from cherrypy import wsgiserver
        server = wsgiserver.CherryPyWSGIServer(bind_addr, app,
            server_name=server_name, **kwargs)

    server.ssl_certificate = server.ssl_private_key = ssl_pem
    if protocol_version:
        server.protocol = protocol_version

    try:
        protocol = is_ssl and 'https' or 'http'
        if host == '0.0.0.0':
            print('serving on 0.0.0.0:%s view at %s://127.0.0.1:%s' %
                  (port, protocol, port))
        else:
            print('serving on %s://%s:%s' % (protocol, host, port))
        server.start()
    except (KeyboardInterrupt, SystemExit):
        server.stop()

    return server
