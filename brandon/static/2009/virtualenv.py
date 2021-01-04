#!/usr/bin/env python
"""Create a "virtual" Python installation
"""

import sys
import os
import optparse
import shutil
import logging
import distutils.sysconfig
import zlib
import base64
import subprocess
    
join = os.path.join
py_version = 'python%s.%s' % (sys.version_info[0], sys.version_info[1])
is_jython = sys.platform.startswith('java')
expected_exe = is_jython and 'jython' or 'python'

REQUIRED_MODULES = ['os', 'posix', 'posixpath', 'ntpath', 'genericpath',
                    'fnmatch', 'locale', 'encodings', 'codecs',
                    'stat', 'UserDict', 'readline', 'copy_reg', 'types',
                    're', 'sre', 'sre_parse', 'sre_constants', 'sre_compile',
                    'lib-dynload', 'config', 'zlib', 'warnings', 'linecache',
                    '_abcoll', 'abc', 'io', '_weakrefset', 'copyreg',
                    'tempfile', 'random', '__future__', 'collections',
                    'keyword', 'tarfile', 'shutil', 'struct', 'copy']

class Logger(object):

    """
    Logging object for use in command-line script.  Allows ranges of
    levels, to avoid some redundancy of displayed information.
    """

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    NOTIFY = (logging.INFO+logging.WARN)/2
    WARN = WARNING = logging.WARN
    ERROR = logging.ERROR
    FATAL = logging.FATAL

    LEVELS = [DEBUG, INFO, NOTIFY, WARN, ERROR, FATAL]

    def __init__(self, consumers):
        self.consumers = consumers
        self.indent = 0
        self.in_progress = None
        self.in_progress_hanging = False

    def debug(self, msg, *args, **kw):
        self.log(self.DEBUG, msg, *args, **kw)
    def info(self, msg, *args, **kw):
        self.log(self.INFO, msg, *args, **kw)
    def notify(self, msg, *args, **kw):
        self.log(self.NOTIFY, msg, *args, **kw)
    def warn(self, msg, *args, **kw):
        self.log(self.WARN, msg, *args, **kw)
    def error(self, msg, *args, **kw):
        self.log(self.WARN, msg, *args, **kw)
    def fatal(self, msg, *args, **kw):
        self.log(self.FATAL, msg, *args, **kw)
    def log(self, level, msg, *args, **kw):
        if args:
            if kw:
                raise TypeError(
                    "You may give positional or keyword arguments, not both")
        args = args or kw
        rendered = None
        for consumer_level, consumer in self.consumers:
            if self.level_matches(level, consumer_level):
                if (self.in_progress_hanging
                    and consumer in (sys.stdout, sys.stderr)):
                    self.in_progress_hanging = False
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                if rendered is None:
                    if args:
                        rendered = msg % args
                    else:
                        rendered = msg
                    rendered = ' '*self.indent + rendered
                if hasattr(consumer, 'write'):
                    consumer.write(rendered+'\n')
                else:
                    consumer(rendered)

    def start_progress(self, msg):
        assert not self.in_progress, (
            "Tried to start_progress(%r) while in_progress %r"
            % (msg, self.in_progress))
        if self.level_matches(self.NOTIFY, self._stdout_level()):
            sys.stdout.write(msg)
            sys.stdout.flush()
            self.in_progress_hanging = True
        else:
            self.in_progress_hanging = False
        self.in_progress = msg

    def end_progress(self, msg='done.'):
        assert self.in_progress, (
            "Tried to end_progress without start_progress")
        if self.stdout_level_matches(self.NOTIFY):
            if not self.in_progress_hanging:
                # Some message has been printed out since start_progress
                sys.stdout.write('...' + self.in_progress + msg + '\n')
                sys.stdout.flush()
            else:
                sys.stdout.write(msg + '\n')
                sys.stdout.flush()
        self.in_progress = None
        self.in_progress_hanging = False

    def show_progress(self):
        """If we are in a progress scope, and no log messages have been
        shown, write out another '.'"""
        if self.in_progress_hanging:
            sys.stdout.write('.')
            sys.stdout.flush()

    def stdout_level_matches(self, level):
        """Returns true if a message at this level will go to stdout"""
        return self.level_matches(level, self._stdout_level())

    def _stdout_level(self):
        """Returns the level that stdout runs at"""
        for level, consumer in self.consumers:
            if consumer is sys.stdout:
                return level
        return self.FATAL

    def level_matches(self, level, consumer_level):
        """
        >>> l = Logger()
        >>> l.level_matches(3, 4)
        False
        >>> l.level_matches(3, 2)
        True
        >>> l.level_matches(slice(None, 3), 3)
        False
        >>> l.level_matches(slice(None, 3), 2)
        True
        >>> l.level_matches(slice(1, 3), 1)
        True
        >>> l.level_matches(slice(2, 3), 1)
        False
        """
        if isinstance(level, slice):
            start, stop = level.start, level.stop
            if start is not None and start > consumer_level:
                return False
            if stop is not None or stop <= consumer_level:
                return False
            return True
        else:
            return level >= consumer_level

    #@classmethod
    def level_for_integer(cls, level):
        levels = cls.LEVELS
        if level < 0:
            return levels[0]
        if level >= len(levels):
            return levels[-1]
        return levels[level]

    level_for_integer = classmethod(level_for_integer)

def mkdir(path):
    if not os.path.exists(path):
        logger.info('Creating %s', path)
        os.makedirs(path)
    else:
        logger.info('Directory %s already exists', path)

def copyfile(src, dest, symlink=True):
    if not os.path.exists(src):
        # Some bad symlink in the src
        logger.warn('Cannot find file %s (bad symlink)', src)
        return
    if os.path.exists(dest):
        logger.debug('File %s already exists', dest)
        return
    if not os.path.exists(os.path.dirname(dest)):
        logger.info('Creating parent directories for %s' % os.path.dirname(dest))
        os.makedirs(os.path.dirname(dest))
    if symlink and hasattr(os, 'symlink'):
        logger.info('Symlinking %s', dest)
        os.symlink(os.path.abspath(src), dest)
    else:
        logger.info('Copying to %s', dest)
        if os.path.isdir(src):
            shutil.copytree(src, dest, True)
        else:
            shutil.copy2(src, dest)

def writefile(dest, content, overwrite=True):
    if not os.path.exists(dest):
        logger.info('Writing %s', dest)
        f = open(dest, 'wb')
        f.write(content)
        f.close()
        return
    else:
        f = open(dest, 'rb')
        c = f.read()
        f.close()
        if c != content:
            if not overwrite:
                logger.notify('File %s exists with different content; not overwriting', dest)
                return
            logger.notify('Overwriting %s with new content', dest)
            f = open(dest, 'wb')
            f.write(content)
            f.close()
        else:
            logger.info('Content %s already in place', dest)

def rmtree(dir):
    if os.path.exists(dir):
        logger.notify('Deleting tree %s', dir)
        shutil.rmtree(dir)
    else:
        logger.info('Do not need to delete %s; already gone', dir)

def make_exe(fn):
    if hasattr(os, 'chmod'):
        oldmode = os.stat(fn).st_mode & 0o7777
        newmode = (oldmode | 0o555) & 0o7777
        os.chmod(fn, newmode)
        logger.info('Changed mode of %s to %s', fn, oct(newmode))

def install_setuptools(py_executable, unzip=False):
    setup_fn = 'setuptools-0.6c9-py%s.egg' % sys.version[:3]
    search_dirs = ['.', os.path.dirname(__file__), join(os.path.dirname(__file__), 'support-files')]
    if os.path.splitext(os.path.dirname(__file__))[0] != 'virtualenv':
        # Probably some boot script; just in case virtualenv is installed...
        try:
            import virtualenv
        except ImportError:
            pass
        else:
            search_dirs.append(os.path.join(os.path.dirname(virtualenv.__file__), 'support-files'))
    for dir in search_dirs:
        if os.path.exists(join(dir, setup_fn)):
            setup_fn = join(dir, setup_fn)
            break
    if is_jython and os._name == 'nt':
        # Jython's .bat sys.executable can't handle a command line
        # argument with newlines
        import tempfile
        fd, ez_setup = tempfile.mkstemp('.py')
        os.write(fd, EZ_SETUP_PY)
        os.close(fd)
        cmd = [py_executable, ez_setup]
    else:
        cmd = [py_executable, '-c', EZ_SETUP_PY]
    if unzip:
        cmd.append('--always-unzip')
    env = {}
    if logger.stdout_level_matches(logger.DEBUG):
        cmd.append('-v')
    if os.path.exists(setup_fn):
        logger.info('Using existing Setuptools egg: %s', setup_fn)
        cmd.append(setup_fn)
        if os.environ.get('PYTHONPATH'):
            env['PYTHONPATH'] = setup_fn + os.path.pathsep + os.environ['PYTHONPATH']
        else:
            env['PYTHONPATH'] = setup_fn
    else:
        logger.info('No Setuptools egg found; downloading')
        cmd.extend(['--always-copy', '-U', 'setuptools'])
    logger.start_progress('Installing setuptools...')
    logger.indent += 2
    cwd = None
    if not os.access(os.getcwd(), os.W_OK):
        cwd = '/tmp'
    try:
        call_subprocess(cmd, show_stdout=False,
                        filter_stdout=filter_ez_setup,
                        extra_env=env,
                        cwd=cwd)
    finally:
        logger.indent -= 2
        logger.end_progress()
        if is_jython and os._name == 'nt':
            os.remove(ez_setup)

def filter_ez_setup(line):
    if not line.strip():
        return Logger.DEBUG
    for prefix in ['Reading ', 'Best match', 'Processing setuptools',
                   'Copying setuptools', 'Adding setuptools',
                   'Installing ', 'Installed ']:
        if line.startswith(prefix):
            return Logger.DEBUG
    return Logger.INFO

def main():
    parser = optparse.OptionParser(
        version="1.3.4dev",
        usage="%prog [OPTIONS] DEST_DIR")

    parser.add_option(
        '-v', '--verbose',
        action='count',
        dest='verbose',
        default=0,
        help="Increase verbosity")

    parser.add_option(
        '-q', '--quiet',
        action='count',
        dest='quiet',
        default=0,
        help='Decrease verbosity')

    parser.add_option(
        '-p', '--python',
        dest='python',
        metavar='PYTHON_EXE',
        help='The Python interpreter to use, e.g., --python=python2.5 will use the python2.5 '
        'interpreter to create the new environment.  The default is the interpreter that '
        'virtualenv was installed with (%s)' % sys.executable)

    parser.add_option(
        '--clear',
        dest='clear',
        action='store_true',
        help="Clear out the non-root install and start from scratch")

    parser.add_option(
        '--no-site-packages',
        dest='no_site_packages',
        action='store_true',
        help="Don't give access to the global site-packages dir to the "
             "virtual environment")

    parser.add_option(
        '--unzip-setuptools',
        dest='unzip_setuptools',
        action='store_true',
        help="Unzip Setuptools when installing it")

    parser.add_option(
        '--relocatable',
        dest='relocatable',
        action='store_true',
        help='Make an EXISTING virtualenv environment relocatable.  '
        'This fixes up scripts and makes all .pth files relative')

    if 'extend_parser' in globals():
        extend_parser(parser)

    options, args = parser.parse_args()

    global logger

    if 'adjust_options' in globals():
        adjust_options(options, args)

    verbosity = options.verbose - options.quiet
    logger = Logger([(Logger.level_for_integer(2-verbosity), sys.stdout)])

    if options.python and not os.environ.get('VIRTUALENV_INTERPRETER_RUNNING'):
        env = os.environ.copy()
        interpreter = resolve_interpreter(options.python)
        if interpreter == sys.executable:
            logger.warn('Already using interpreter %s' % interpreter)
        else:
            logger.notify('Running virtualenv with interpreter %s' % interpreter)
            env['VIRTUALENV_INTERPRETER_RUNNING'] = 'true'
            file = __file__
            if file.endswith('.pyc'):
                file = file[:-1]
            os.execvpe(interpreter, [interpreter, file] + sys.argv[1:], env)

    if not args:
        print('You must provide a DEST_DIR')
        parser.print_help()
        sys.exit(2)
    if len(args) > 1:
        print('There must be only one argument: DEST_DIR (you gave %s)' % (
            ' '.join(args)))
        parser.print_help()
        sys.exit(2)

    home_dir = args[0]

    if os.environ.get('WORKING_ENV'):
        logger.fatal('ERROR: you cannot run virtualenv while in a workingenv')
        logger.fatal('Please deactivate your workingenv, then re-run this script')
        sys.exit(3)

    if os.environ.get('PYTHONHOME'):
        if sys.platform == 'win32':
            name = '%PYTHONHOME%'
        else:
            name = '$PYTHONHOME'
        logger.warn('%s is set; this can cause problems creating environments' % name)

    if options.relocatable:
        make_environment_relocatable(home_dir)
        return

    create_environment(home_dir, site_packages=not options.no_site_packages, clear=options.clear,
                       unzip_setuptools=options.unzip_setuptools)
    if 'after_install' in globals():
        after_install(options, home_dir)

def call_subprocess(cmd, show_stdout=True,
                    filter_stdout=None, cwd=None,
                    raise_on_returncode=True, extra_env=None):
    cmd_parts = []
    for part in cmd:
        if isinstance(part, bytes):
            part = part.decode('utf-8')
        if len(part) > 40:
            part = part[:30]+"..."+part[-5:]
        if ' ' in part or '\n' in part or '"' in part or "'" in part:
            part = '"%s"' % part.replace('"', '\\"')
        cmd_parts.append(part)
    cmd_desc = ' '.join(cmd_parts)
    if show_stdout:
        stdout = None
    else:
        stdout = subprocess.PIPE
    logger.debug("Running command %s" % cmd_desc)
    if extra_env:
        env = os.environ.copy()
        env.update(extra_env)
    else:
        env = None
    try:
        proc = subprocess.Popen(
            cmd, stderr=subprocess.STDOUT, stdin=None, stdout=stdout,
            cwd=cwd, env=env)
    except Exception as e:
        logger.fatal(
            "Error %s while executing command %s" % (e, cmd_desc))
        raise
    all_output = []
    if stdout is not None:
        stdout = proc.stdout
        while 1:
            line = stdout.readline().decode('ascii')
            if not line:
                break
            line = line.rstrip()
            all_output.append(line)
            if filter_stdout:
                level = filter_stdout(line)
                if isinstance(level, tuple):
                    level, line = level
                logger.log(level, line)
                if not logger.stdout_level_matches(level):
                    logger.show_progress()
            else:
                logger.info(line)
    else:
        proc.communicate()
    proc.wait()
    if proc.returncode:
        if raise_on_returncode:
            if all_output:
                logger.notify('Complete output from command %s:' % cmd_desc)
                logger.notify('\n'.join(all_output) + '\n----------------------------------------')
            raise OSError(
                "Command %s failed with error code %s"
                % (cmd_desc, proc.returncode))
        else:
            logger.warn(
                "Command %s had error code %s"
                % (cmd_desc, proc.returncode))


def create_environment(home_dir, site_packages=True, clear=False,
                       unzip_setuptools=False):
    """
    Creates a new environment in ``home_dir``.

    If ``site_packages`` is true (the default) then the global
    ``site-packages/`` directory will be on the path.

    If ``clear`` is true (default False) then the environment will
    first be cleared.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)

    py_executable = install_python(
        home_dir, lib_dir, inc_dir, bin_dir, 
        site_packages=site_packages, clear=clear)

    install_distutils(lib_dir, home_dir)

    install_setuptools(py_executable, unzip=unzip_setuptools)

    install_activate(home_dir, bin_dir)

def path_locations(home_dir):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    # XXX: We'd use distutils.sysconfig.get_python_inc/lib but its
    # prefix arg is broken: http://bugs.python.org/issue3386
    if sys.platform == 'win32':
        # Windows has lots of problems with executables with spaces in
        # the name; this function will remove them (using the ~1
        # format):
        mkdir(home_dir)
        if ' ' in home_dir:
            try:
                import win32api
            except ImportError:
                print('Error: the path "%s" has a space in it' % home_dir)
                print('To handle these kinds of paths, the win32api module must be installed:')
                print('  http://sourceforge.net/projects/pywin32/')
                sys.exit(3)
            home_dir = win32api.GetShortPathName(home_dir)
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'Scripts')
    elif is_jython:
        lib_dir = join(home_dir, 'Lib')
        inc_dir = join(home_dir, 'Include')
        bin_dir = join(home_dir, 'bin')
    else:
        lib_dir = join(home_dir, 'lib', py_version)
        inc_dir = join(home_dir, 'include', py_version)
        bin_dir = join(home_dir, 'bin')
    return home_dir, lib_dir, inc_dir, bin_dir

def install_python(home_dir, lib_dir, inc_dir, bin_dir, site_packages, clear):
    """Install just the base environment, no distutils patches etc"""
    if sys.executable.startswith(bin_dir):
        print('Please use the *system* python to run this script')
        return
        
    if clear:
        rmtree(lib_dir)
        ## FIXME: why not delete it?
        ## Maybe it should delete everything with #!/path/to/venv/python in it
        logger.notify('Not deleting %s', bin_dir)

    if hasattr(sys, 'real_prefix'):
        logger.notify('Using real prefix %r' % sys.real_prefix)
        prefix = sys.real_prefix
    else:
        prefix = sys.prefix
    mkdir(lib_dir)
    fix_lib64(lib_dir)
    stdlib_dirs = [os.path.dirname(os.__file__)]
    if sys.platform == 'win32':
        stdlib_dirs.append(join(os.path.dirname(stdlib_dirs[0]), 'DLLs'))
    elif sys.platform == 'darwin':
        stdlib_dirs.append(join(stdlib_dirs[0], 'site-packages'))
    for stdlib_dir in stdlib_dirs:
        if not os.path.isdir(stdlib_dir):
            continue
        if hasattr(os, 'symlink'):
            logger.info('Symlinking Python bootstrap modules')
        else:
            logger.info('Copying Python bootstrap modules')
        logger.indent += 2
        try:
            for fn in os.listdir(stdlib_dir):
                if fn != 'site-packages' and os.path.splitext(fn)[0] in REQUIRED_MODULES:
                    copyfile(join(stdlib_dir, fn), join(lib_dir, fn))
        finally:
            logger.indent -= 2
    mkdir(join(lib_dir, 'site-packages'))
    writefile(join(lib_dir, 'site.py'), SITE_PY)
    writefile(join(lib_dir, 'orig-prefix.txt'), prefix.encode('utf-8'))
    site_packages_filename = join(lib_dir, 'no-global-site-packages.txt')
    if not site_packages:
        writefile(site_packages_filename, b'')
    else:
        if os.path.exists(site_packages_filename):
            logger.info('Deleting %s' % site_packages_filename)
            os.unlink(site_packages_filename)

    stdinc_dir = join(prefix, 'include', py_version)
    if os.path.exists(stdinc_dir):
        copyfile(stdinc_dir, inc_dir)
    else:
        logger.debug('No include dir %s' % stdinc_dir)

    if sys.exec_prefix != prefix:
        if sys.platform == 'win32':
            exec_dir = join(sys.exec_prefix, 'lib')
        elif is_jython:
            exec_dir = join(sys.exec_prefix, 'Lib')
        else:
            exec_dir = join(sys.exec_prefix, 'lib', py_version)
        for fn in os.listdir(exec_dir):
            copyfile(join(exec_dir, fn), join(lib_dir, fn))
    
    if is_jython:
        # Jython has either jython-dev.jar and javalib/ dir, or just
        # jython.jar
        for name in 'jython-dev.jar', 'javalib', 'jython.jar':
            src = join(prefix, name)
            if os.path.exists(src):
                copyfile(src, join(home_dir, name))
        # XXX: registry should always exist after Jython 2.5rc1
        src = join(prefix, 'registry')
        if os.path.exists(src):
            copyfile(src, join(home_dir, 'registry'), symlink=False)
        copyfile(join(prefix, 'cachedir'), join(home_dir, 'cachedir'),
                 symlink=False)

    mkdir(bin_dir)
    py_executable = join(bin_dir, os.path.basename(sys.executable))
    if 'Python.framework' in prefix:
        if py_executable.endswith('/Python'):
            # The name of the python executable is not quite what
            # we want, rename it.
            py_executable = os.path.join(
                    os.path.dirname(py_executable), 'python')

    logger.notify('New %s executable in %s', expected_exe, py_executable)
    if sys.executable != py_executable:
        ## FIXME: could I just hard link?
        executable = sys.executable
        if sys.platform == 'cygwin' and os.path.exists(executable + '.exe'):
            # Cygwin misreports sys.executable sometimes
            executable += '.exe'
            py_executable += '.exe'
            logger.info('Executable actually exists in %s' % executable)
        shutil.copyfile(executable, py_executable)
        make_exe(py_executable)
        if sys.platform == 'win32' or sys.platform == 'cygwin':
            pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            if os.path.exists(pythonw):
                logger.info('Also created pythonw.exe')
                shutil.copyfile(pythonw, os.path.join(os.path.dirname(py_executable), 'pythonw.exe'))
                
    if os.path.splitext(os.path.basename(py_executable))[0] != expected_exe:
        secondary_exe = os.path.join(os.path.dirname(py_executable),
                                     expected_exe)
        py_executable_ext = os.path.splitext(py_executable)[1]
        if py_executable_ext == '.exe':
            # python2.4 gives an extension of '.4' :P
            secondary_exe += py_executable_ext
        if os.path.exists(secondary_exe):
            logger.warn('Not overwriting existing %s script %s (you must use %s)'
                        % (expected_exe, secondary_exe, py_executable))
        else:
            logger.notify('Also creating executable in %s' % secondary_exe)
            shutil.copyfile(sys.executable, secondary_exe)
            make_exe(secondary_exe)
    
    if 'Python.framework' in prefix:
        logger.debug('MacOSX Python framework detected')
        
        # Make sure we use the the embedded interpreter inside
        # the framework, even if sys.executable points to
        # the stub executable in ${sys.prefix}/bin
        # See http://groups.google.com/group/python-virtualenv/
        #                              browse_thread/thread/17cab2f85da75951
        shutil.copy(
                os.path.join(
                    prefix, 'Resources/Python.app/Contents/MacOS/Python'),
                py_executable)

        # Copy the framework's dylib into the virtual 
        # environment
        virtual_lib = os.path.join(home_dir, '.Python')

        if os.path.exists(virtual_lib):
            os.unlink(virtual_lib)
        copyfile(
            os.path.join(prefix, 'Python'),
            virtual_lib)

        # And then change the install_name of the copied python executable
        try:
            call_subprocess(
                ["install_name_tool", "-change",
                 os.path.join(prefix, 'Python'),
                 '@executable_path/../.Python',
                 py_executable])
        except:
            logger.fatal(
                "Could not call install_name_tool -- you must have Apple's development tools installed")
            raise

        # Some tools depend on pythonX.Y being present
        py_executable_version = '%s.%s' % (
            sys.version_info[0], sys.version_info[1])
        if not py_executable.endswith(py_executable_version):
            # symlinking pythonX.Y > python
            pth = py_executable + '%s.%s' % (
                    sys.version_info[0], sys.version_info[1])
            if os.path.exists(pth):
                os.unlink(pth)
            os.symlink('python', pth)
        else:
            # reverse symlinking python -> pythonX.Y (with --python)
            pth = join(bin_dir, 'python')
            if os.path.exists(pth):
                os.unlink(pth)
            os.symlink(os.path.basename(py_executable), pth)

    if sys.platform == 'win32' and ' ' in py_executable:
        # There's a bug with subprocess on Windows when using a first
        # argument that has a space in it.  Instead we have to quote
        # the value:
        py_executable = '"%s"' % py_executable
    cmd = [py_executable, '-c',
           'import sys; sys.stdout.write(sys.prefix)']
    logger.info('Testing executable with %s %s "%s"' % tuple(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    proc_stdout, proc_stderr = proc.communicate()
    proc_stdout = proc_stdout.decode('utf-8').strip()
    proc_stdout = os.path.normcase(os.path.abspath(proc_stdout))
    if proc_stdout != os.path.normcase(os.path.abspath(home_dir)):
        logger.fatal(
            'ERROR: The executable %s is not functioning' % py_executable)
        logger.fatal(
            'ERROR: It thinks sys.prefix is %r (should be %r)'
            % (proc_stdout, os.path.normcase(os.path.abspath(home_dir))))
        logger.fatal(
            'ERROR: virtualenv is not compatible with this system or executable')
        sys.exit(100)
    else:
        logger.info('Got sys.prefix result: %r' % proc_stdout)

    pydistutils = os.path.expanduser('~/.pydistutils.cfg')
    if os.path.exists(pydistutils):
        logger.notify('Please make sure you remove any previous custom paths from '
                      'your %s file.' % pydistutils)
    ## FIXME: really this should be calculated earlier
    return py_executable

def install_activate(home_dir, bin_dir):
    if sys.platform == 'win32' or is_jython and os._name == 'nt':
        files = {'activate.bat': ACTIVATE_BAT,
                 'deactivate.bat': DEACTIVATE_BAT}
        if os.environ.get('OS') == 'Windows_NT' and os.environ.get('OSTYPE') == 'cygwin':
            files['activate'] = ACTIVATE_SH
    else:
        files = {'activate': ACTIVATE_SH}
    files['activate_this.py'] = ACTIVATE_THIS
    for name, content in list(files.items()):
        content = content.replace(b'__VIRTUAL_ENV__',
                                  os.path.abspath(home_dir).encode('utf-8'))
        content = content.replace(b'__VIRTUAL_NAME__',
                                  os.path.basename(os.path.abspath(home_dir))
                                  .encode('utf-8'))
        content = content.replace(b'__BIN_NAME__',
                                  os.path.basename(bin_dir).encode('utf-8'))
        writefile(os.path.join(bin_dir, name), content)

def install_distutils(lib_dir, home_dir):
    distutils_path = os.path.join(lib_dir, 'distutils')
    mkdir(distutils_path)
    ## FIXME: maybe this prefix setting should only be put in place if
    ## there's a local distutils.cfg with a prefix setting?
    home_dir = os.path.abspath(home_dir)
    ## FIXME: this is breaking things, removing for now:
    #distutils_cfg = DISTUTILS_CFG + "\n[install]\nprefix=%s\n" % home_dir
    writefile(os.path.join(distutils_path, '__init__.py'), DISTUTILS_INIT)
    writefile(os.path.join(distutils_path, 'distutils.cfg'), DISTUTILS_CFG, overwrite=False)

def fix_lib64(lib_dir):
    """
    Some platforms (particularly Gentoo on x64) put things in lib64/pythonX.Y
    instead of lib/pythonX.Y.  If this is such a platform we'll just create a
    symlink so lib64 points to lib
    """
    if [p for p in list(distutils.sysconfig.get_config_vars().values()) 
        if isinstance(p, str) and 'lib64' in p]:
        logger.debug('This system uses lib64; symlinking lib64 to lib')
        assert os.path.basename(lib_dir) == 'python%s' % sys.version[:3], (
            "Unexpected python lib dir: %r" % lib_dir)
        lib_parent = os.path.dirname(lib_dir)
        assert os.path.basename(lib_parent) == 'lib', (
            "Unexpected parent dir: %r" % lib_parent)
        copyfile(lib_parent, os.path.join(os.path.dirname(lib_parent), 'lib64'))

def resolve_interpreter(exe):
    """
    If the executable given isn't an absolute path, search $PATH for the interpreter
    """
    if os.path.abspath(exe) != exe:
        paths = os.environ.get('PATH', '').split(os.pathsep)
        for path in paths:
            if os.path.exists(os.path.join(path, exe)):
                exe = os.path.join(path, exe)
                break
    if not os.path.exists(exe):
        logger.fatal('The executable %s (from --python=%s) does not exist' % (exe, exe))
        sys.exit(3)
    return exe

############################################################
## Relocating the environment:

def make_environment_relocatable(home_dir):
    """
    Makes the already-existing environment use relative paths, and takes out 
    the #!-based environment selection in scripts.
    """
    activate_this = os.path.join(home_dir, 'bin', 'activate_this.py')
    if not os.path.exists(activate_this):
        logger.fatal(
            'The environment doesn\'t have a file %s -- please re-run virtualenv '
            'on this environment to update it' % activate_this)
    fixup_scripts(home_dir)
    fixup_pth_and_egg_link(home_dir)
    ## FIXME: need to fix up distutils.cfg

OK_ABS_SCRIPTS = ['python', 'python%s' % sys.version[:3],
                  'activate', 'activate.bat', 'activate_this.py']

def fixup_scripts(home_dir):
    # This is what we expect at the top of scripts:
    shebang = '#!%s/bin/python' % os.path.normcase(os.path.abspath(home_dir))
    # This is what we'll put:
    new_shebang = '#!/usr/bin/env python%s' % sys.version[:3]
    activate = "import os; activate_this=os.path.join(os.path.dirname(__file__), 'activate_this.py'); execfile(activate_this, dict(__file__=activate_this)); del os, activate_this"
    bin_dir = os.path.join(home_dir, 'bin')
    for filename in os.listdir(bin_dir):
        filename = os.path.join(bin_dir, filename)
        f = open(filename, 'rb')
        lines = f.readlines()
        f.close()
        if not lines:
            logger.warn('Script %s is an empty file' % filename)
            continue
        if not lines[0].strip().startswith(shebang):
            if os.path.basename(filename) in OK_ABS_SCRIPTS:
                logger.debug('Cannot make script %s relative' % filename)
            elif lines[0].strip() == new_shebang:
                logger.info('Script %s has already been made relative' % filename)
            else:
                logger.warn('Script %s cannot be made relative (it\'s not a normal script that starts with %s)'
                            % (filename, shebang))
            continue
        logger.notify('Making script %s relative' % filename)
        lines = [new_shebang+'\n', activate+'\n'] + lines[1:]
        f = open(filename, 'wb')
        f.writelines(lines)
        f.close()

def fixup_pth_and_egg_link(home_dir):
    """Makes .pth and .egg-link files use relative paths"""
    home_dir = os.path.normcase(os.path.abspath(home_dir))
    for path in sys.path:
        if not path:
            path = '.'
        if not os.path.isdir(path):
            continue
        path = os.path.normcase(os.path.abspath(path))
        if not path.startswith(home_dir):
            logger.debug('Skipping system (non-environment) directory %s' % path)
            continue
        for filename in os.listdir(path):
            filename = os.path.join(path, filename)
            if filename.endswith('.pth'):
                if not os.access(filename, os.W_OK):
                    logger.warn('Cannot write .pth file %s, skipping' % filename)
                else:
                    fixup_pth_file(filename)
            if filename.endswith('.egg-link'):
                if not os.access(filename, os.W_OK):
                    logger.warn('Cannot write .egg-link file %s, skipping' % filename)
                else:
                    fixup_egg_link(filename)

def fixup_pth_file(filename):
    lines = []
    prev_lines = []
    f = open(filename)
    prev_lines = f.readlines()
    f.close()
    for line in prev_lines:
        line = line.strip()
        if (not line or line.startswith('#') or line.startswith('import ')
            or os.path.abspath(line) != line):
            lines.append(line)
        else:
            new_value = make_relative_path(filename, line)
            if line != new_value:
                logger.debug('Rewriting path %s as %s (in %s)' % (line, new_value, filename))
            lines.append(new_value)
    if lines == prev_lines:
        logger.info('No changes to .pth file %s' % filename)
        return
    logger.notify('Making paths in .pth file %s relative' % filename)
    f = open(filename, 'w')
    f.write('\n'.join(lines) + '\n')
    f.close()

def fixup_egg_link(filename):
    f = open(filename)
    link = f.read().strip()
    f.close()
    if os.path.abspath(link) != link:
        logger.debug('Link in %s already relative' % filename)
        return
    new_link = make_relative_path(filename, link)
    logger.notify('Rewriting link %s in %s as %s' % (link, filename, new_link))
    f = open(filename, 'w')
    f.write(new_link)
    f.close()

def make_relative_path(source, dest, dest_is_directory=True):
    """
    Make a filename relative, where the filename is dest, and it is
    being referred to from the filename source.

        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/usr/share/another-place/src/Directory')
        '../another-place/src/Directory'
        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/home/user/src/Directory')
        '../../../home/user/src/Directory'
        >>> make_relative_path('/usr/share/a-file.pth', '/usr/share/')
        './'
    """
    source = os.path.dirname(source)
    if not dest_is_directory:
        dest_filename = os.path.basename(dest)
        dest = os.path.dirname(dest)
    dest = os.path.normpath(os.path.abspath(dest))
    source = os.path.normpath(os.path.abspath(source))
    dest_parts = dest.strip(os.path.sep).split(os.path.sep)
    source_parts = source.strip(os.path.sep).split(os.path.sep)
    while dest_parts and source_parts and dest_parts[0] == source_parts[0]:
        dest_parts.pop(0)
        source_parts.pop(0)
    full_parts = ['..']*len(source_parts) + dest_parts
    if not dest_is_directory:
        full_parts.append(dest_filename)
    if not full_parts:
        # Special case for the current directory (otherwise it'd be '')
        return './'
    return os.path.sep.join(full_parts)
                


############################################################
## Bootstrap script creation:

def create_bootstrap_script(extra_text, python_version=''):
    """
    Creates a bootstrap script, which is like this script but with
    extend_parser, adjust_options, and after_install hooks.

    This returns a string that (written to disk of course) can be used
    as a bootstrap script with your own customizations.  The script
    will be the standard virtualenv.py script, with your extra text
    added (your extra text should be Python code).

    If you include these functions, they will be called:

    ``extend_parser(optparse_parser)``:
        You can add or remove options from the parser here.

    ``adjust_options(options, args)``:
        You can change options here, or change the args (if you accept
        different kinds of arguments, be sure you modify ``args`` so it is
        only ``[DEST_DIR]``).

    ``after_install(options, home_dir)``:

        After everything is installed, this function is called.  This
        is probably the function you are most likely to use.  An
        example would be::

            def after_install(options, home_dir):
                subprocess.call([join(home_dir, 'bin', 'easy_install'),
                                 'MyPackage'])
                subprocess.call([join(home_dir, 'bin', 'my-package-script'),
                                 'setup', home_dir])

        This example immediately installs a package, and runs a setup
        script from that package.

    If you provide something like ``python_version='2.4'`` then the
    script will start with ``#!/usr/bin/env python2.4`` instead of
    ``#!/usr/bin/env python``.  You can use this when the script must
    be run with a particular Python version.
    """
    filename = __file__
    if filename.endswith('.pyc'):
        filename = filename[:-1]
    f = open(filename, 'rb')
    content = f.read()
    f.close()
    py_exe = 'python%s' % python_version
    content = (('#!/usr/bin/env %s\n' % py_exe)
               + '## WARNING: This file is generated\n'
               + content)
    return content.replace('##EXT' 'END##', extra_text)

##EXTEND##

##file site.py
SITE_PY = zlib.decompress(base64.b64decode(b"""
eJzVPGtz2za23/UrUHoypBKZTtJuZ8epeycPd+sdN/HW6d3cdTwaSoQs1hTJEmQc7Yf97fc8ABAg
KVtpez9cTcaRCODg4OC8ccAgCF5WlSxSsSnTNpdCyaRerkWVNGslVmUtmnVWp4dVUjdbeLq8TW6k
Ek0p1FbF2CueTB7/wc/ksXi/zpRBAb4lbVNukiZbJnm+FdmmKutGpiJt66y4EVmRNVmSZ/+GHmUR
i8d/HIMJIXCX5blImB4qa+ShquQyW2VLTQ9YdrOWI6SKhXhXTH4pss8iyopl3qaI50/JUry7/DCd
iawRqgES4hTNmmlXyxV0T4p0gj/lZ7mc62dRthJptlrJWhbNFLtopNQkzxZH1bZZl8V3n2StYPnf
HxGmdmsSmEPiMpTAztxII+LJu0KUsIBaVHnSwOZulIhUC2uAzv/MirS8U4xsU2cASibQVK5wzRNG
DR6mWS2XTb6duTPRqrrpLC6EtUyBPO8BRi1VmzdIGQZS4iwwH82wFfJzphoAW0s70GW0GdEqyVUJ
DIAbgxyBHIqNYlkWq+ymrYklxCrLpQLOfLmrkZiMv92tSyVFkWykWMNScIORNJPv9DK+j6tm/QKo
ohBOA1uiGMc0zRBekrvLEVFZSFEBjfOskNMJLGBBff3FAEXelsUhLblHEIBQTwpodJ5NacZCwp4P
Yb0QRWkBbGllusvEdAGWhfHNOgEGKJYSZn+VJ8Ut4aiIwfjbQt5kRYEI4Y5OwoOQJla3GWwIbOM5
9SJWNp1EyOLJPZGNW9gYoP0PsDXyc7KpcjkTqq0qJLPP+aLP+TSZbBD1o1bVR3kJGoB6ItvqXeuW
2vU56gTjefwXnw0nhGazriUAbxce763KciYWSc3YVMlmxrPdlcQ5kxG2okHIE9QTxuJ3oOhLpdqN
tI3IKwkwKknPqszz8g5IdjyZCHGAnYwy9ZkTWqEN/gJc/JvLZrmeTJyZLGANCpHfBQqBgGaTheZq
jYTHbZqV+7KW4Rggd1mnsqap9iP2ESO+Z2dc6+Rt2RBvNnq5uMvlJmtQvhdymbTAN6CT0lKqImxY
TbzgdcMyZCoV0cx07ei0weXl1TpZSGNKFnKFkqA36YXddphzMjInYFKUjdiA0ANFoQ3IIjNWoeOK
BZXOqpFoNyXAYOFLiqxqc+qkkMFEAhNtKoK/SVKJpGcpAvZm6zJBhcRWaNkqsIbZv0GM7tYZ0GcJ
EEDDoJaC7VtkTZ2AMHT6aOLbLjOe5wdOPVvx3uopV0mWaxWeFJMzenha1yS+S1nhqJkmhoIVFg2a
5JsC6IhiHgTBZKIhAfuYr6X9tmgzVPpqMjkQF8aKoN72WOEF4u/qVGtw8uxWOvwkUBFMLn4+/eHs
w+mlOBFXnU6Z9RXKNcx5WiTAV6SSYVd703bKBHqi5kHjV4ofwMzQrqSZotEkPzJpWmAeQP193VIz
LGPpNU5O3758dX46/+Xy9Of55dn7U0AQFL2cHNCSAVzTNkDuGLgT2CJVMVCmAdacDEbQg1cvL+2D
yTxT819JkuARrVqb8avjb67FyYkIf00+JeFkksoV8NWtRO6LHpPvMj0GqRS4XBhbaiP0a5kVpp2a
wRQ7k6BwRDQCQM/nyzxRCjvP5yEQgQaMfGBAzM4OslQEA6utO3SqUcFPLYFoBQ6Z4Z8RFJMFjUM0
GEV3iOkEvLhZJkpyL14/DJzPUSLn80jPCKx6CVsM1NZCFgrTBSWyzhZtQ9uKErpQZY4/cQLkcQSA
W7hBHQCcEuEGMBgVf0ryVqrIXRqQEtwJBBuBUQEq5CVIeo0EOPZIh/o8K4CfUJunJao4UFxGIMXF
6YX4+unzQ7SgeQYqwaBsgTT11oe4ie2yhoTsGqd2EMu5eGloQNI/jqWmbi035SeZAk7IPA6Bxc/U
Aq46YLtMgICgMMjQrOpyYw0MbEJpHAjgVDRKIEUbgmJIb6h+wNGBLBQImGJLgSKnwwDWsVVdfsrQ
ii22uhGUMCgBVMXGYmpoZQEKzNtf1LWgmMG9KnDf7mQIYl637AkR3ggSFVnaKYyYwJ2jBrqmr7dF
eVfMOVI4IRaZWq5Bpka+0cvvaHsgfgD1CEiWbeMQjaGALymQrw8BeVg+LBcoS04rAAILguZNlQ4s
40rTEjmEwGkRxvSFIMGpJRqiT2YKoFNpieFAotbYPjASipBgcVa5WLHULI/W0nSDiR2S+Ox0HrOL
7wPoUTEGcxBpaNzJ0O/qGPSdOHcVgjMOLc2HDx+YbdS6bGHbELEFLhpt04qMQFxBEKMgXLOmXkrk
IGKDO/CaAEyrNGuKw0tRVmzmYT8vOKIS4hKcynXTVMdHR3d3d7GOtMr65kitjv7y12+//etTVkdp
SvwDy3GkRcfe8RG1oasUf2eU+vdm53r8mBU+NxKsSJK5Jx8H8ftbm6WlOD6cWtWFXNyZH/xr7P+N
bOZmUqYy0DboMHqkDh/FX6tAPBKR2zeasr3Vgai1IEbtQRsoPhjRlGDhwB4vy7ZoXPWnxBOwLBCe
pnLR3oR2cs8+mR+wVJTTyPLA4bNrxMDnDMNXytiBOaoJ4ousWJUO7X9mvknI7GsVgfRF8zCIy7bj
asxQN91f4AfaGihmlpgpZA8UCb/L3hJoOw9FBz9az7/fVveqeEeqUmNN01S7TBGKDiGDuzFz5a6j
7UVdLtGGJYJccY6zM9wC4t0dLphFh0JHTD5gVGoYHoHMjPcN7tOC2hqdUWGkyHhz5KZBUfIkTbXV
KF10Z4JcXApYSQOs+nkaHdqKMDYLMzzu6nrQHOifdcTss5zj7iCvnYhn9ESCj3k8aHvKLNTmOaUk
esLgEZ8Bewy1wgEgAJEBMBNB/UvAPfX2n73rbT7vNf2kZa8ceGVtN2E14FtscX294CAY4VyPr+4Z
HQWa3AEgzV8/NsF0BCJuWsT5lb0moxWc8IS1AjmuIn/kLuGy5B5Odq+xI7YzG0fKRO0Q677eGhXn
e21itmLe6WD7jgjFDvh4zFAa4dYL7Rbs9DpBCI7NAmkKdT9M+ty0GB672QNEaZMpMp1IiDX8AQVg
VQF6HQTNgtlXsvyV/QlyZterv+xgAEtp3HK36y4fZ2CONBzTfiCQjDqHAKxeAAmH0kx+KauAHHjI
2SBPoKFZ7pRoA+OK1AnKM30BxLkFFwVfYkwvsxDjPgXTa2vKTH9FSfiIhjmcvJ9p+JNYdbmWy9u5
pJAeo3mc0bHpr7EZp7GRvp8YVcmKaUBJevRaJjT0PdqXtliSf9dIEFd99oE5NQrUWYes8uTGzfDL
4lNWlwUJwKekns4IWqWtH/hgRzcZOJS/tRCmgIBIcMiX5HzrppinJyYXbzjXwEltBWapzpotkCJR
pY5dKC3hdIRYhxYaeUiym8oUx0TFsbjEZWM7Ey7tWzPkVlyagkh6jhDnSLpBmE7TT/puXgmGNAAv
D5YUTLW8+y2SmtyYh7bRpROmGDzquEEF8LeGEk3FVyf6N/30FarG07LRCJY3u7G8uR/Lmz6WN6NY
3vhY3tyPpcvtuFedRjbcbdykaNTRQi2SjOe2XI3M85yiS0X98KADDzQAouCQxZET61B1Lhq7YARk
XW6kGwTTwy5XlfEJSl2ybdQgkaPRr+awSeiIQTmDKfOlB/NSTPpyV77OH3sUx5QXXdBwlqE0aRLf
c7vJywWIokV31gGYiX7qjlVs8Wm+YKOAapblHTc2Ci7+5/2P795idwQFTgvZScYLNxEdNlxK9BiM
pBpmvTr/oAJ+pJ5+Yo6GaYAHWkxN8IVbEoWlei43n0MIs+pMLUtlgqsD/vOGsknIOBDPsv9btQ1n
UG03N88Yhr3nOiGpnzOXs18KIWLRBN2idhDp5cXFm5fvX4LMwYYE/wlsf3daS2SYwH5Hs93REB+B
nDIDBVMfjMbSo163xwN3avAxYMUTN6C9enrde/D8eh9gHsMa19vzQb5w7UA2WHpM6e8vW7oIIIAP
9kG6GqXA8de/a8WGWQbJcNct5mDXtvkehfFHHfH0vIldM/iRC+Y75kABHYxHTA0gijmY6ocr1vbd
Q1IH6B60+cPEJQA4Z5+lzGeQP7CLGAk3HNLabmOkfShWeNgq+Wo7wp2vSogJFvlWOEUJU9dMGTWt
UVRdblVJWfAv65bqI2PYV3MY5CXf0VPXXbzOCOmevIeZzDjuPFBTRYPeRw/jpN1Rij+hWZ6Zw+M0
c5IVnDOv9mTLSebkvPNKVnRAcxT+nln21A+GEf8oJ4uhtpj+XqwNJG0SnD3Cz4EAK9SA4w1K9ZhS
QDDo22/ceADzPSGf8Cawng14z7eUQeoBclwjcKNz8MjTLbhQ4AJiVIanoG5/mmY+ctDmYv/tN/tS
/Y8rjzF7ZD5Ag6iXp7D4s5s8mMR0BzLkFCM7A5CUOrZ3P1eDMdWUZZgkUm/59Vh6pMcO3VwP7Tal
lP3dBhh1WdVZ0kh/ywY5WQaJ9AYnplz8CjCUPjf6lGQ5HQkD5oeH6Cub/DWn5EczPB2U3SvEM566
iZ7ORjN+CrwRUC+cKO/JzB7Hd/ipEqXuo9obuciSoqsb8IyOWzPyf69n/hRFMzCbv0vTWFfh/yX2
rCcZ0lBP+l7pGFhj/n731ANlv9OQYkSRJvVdVgTHPS5FVbGqIey4K+tbFjMlHqM8PiaVTPl9ian7
AiCk4mVV5bIHAzeSC2D6CjDUh3l2hhBlmxfysEYa3dCR0G7nxnvkY1cfTD+W9ARdwLMn3/S5bUj/
YXJ5rwUNET36UiQfxq3z7cxxjmMdPOfOd3hNTtTfrAey2g85uko2r07/dvb2/OzVxcv3PzpJRkwW
vrs8ei5Of/og6MAC0ymcdUvw7LDBs/qy0EUmumIhLeFfi4YjbZstwYJRb87PtXO8aVWD8QdxcgzP
+dTMQmODyeW79qFmZsQo5+1wq5LpQJuqlrEEdcMVtarUpWlU7LzAdGhbsNXS5dWmDJtOYGKIM6Gz
SwoGwUUY0EQFhI0RwJrT2Fw1PIaUzhjZk9OcHILBOZdT02U8YQB2mG4LrKPRXgw86QbrtMNV6OIa
XseqyrMmCl+ENgeth+EBcscy+qE9h2G8xqJ3ZzjMrDtOtITswAJzKC9CXpseP+0Y7bcWMOwY7A2s
u8By3zsunsPyDxFip5BcshA8tSa0W6/3QMGGYWzV4CYapstg9Ql4LWKdFQ14MGJd3lEmGiD0dsKP
Jo6daEKWeKwYvt6kh/8INUH83h8/jnRv6vzwX6LKWyX4rD0cIabb+Y2IsljG4vTdD9OQkaPCMfGP
Fisz64h9KEfO6YCfj4HmkZL5Sh+M9owaNOisFTX3hteyqvXw8UxtiBLwSEUU1D1Shn4hFkRY2DNc
yrQHGotOLWbLMpXuWZr5HIjLtcxzXel49ub8VICpWq5Jgi6p0OcUppsBMzQccXB5CrZndQ8UnhJB
c41sXGNCdZmXqh+ijPq7KyxiOHw2eO5XdMQ0AUgjaqeiHDvvtcBs95g7R0PjA8Ch61cn4uk4HJPD
pFXoxfE5PS5R4eCnowO7uWloNOYx73CR3Qd1kil3EyLcRIZl6lpjFExYrWFSFtReH+QXtw/xD2oA
ZvD5RU0Faz6Hg2TS04TPGyB4wZphE45wDiQrGlOhlGdLsApgQMA8zEDkkVVAEbMclQUHB2WtTD09
PKy2dXazbjBug8Ex1fJi959efjg/e0vltc+/7jLaI6I2oyz7jM91T7AkCI31iVcKSTIyn49JoG5C
GKhL4b9+Ex8Yn/AEg3GcJML/+k18oeHEOWbhFYC6bau+sKMv6gwb0wKdZDOu9pAJP27FT4eZD4ac
WJQDc5zqrG9EGk3PnmEkN8Y0DuVpVLIJXmUrQ/RgtzKk/9FrXFUYsacjcssgR2XLfBYw9HbQsqsG
xf0MpBDvQwFGw97+HKYkY9BVL8dhtl3cQkdG2mP4WITTsX7LAkUZiBi5g6cuk42bFN2dOdArmxwA
E99pdI0kjhqm4GMRaH/Jw8QSexDfmYFYAsYmDdOvUtewt+ARon0DBULVfpEjubPp4+feGh3b9vAa
te4CS/8jKEJdekfl1GUtqRDrN3aDuYnQQj16LELH7yrAiNjSDfzcrdFHfuavcdy64aE/il2dFDcy
YlgzA/OJT+wdRo20rUfqq+x6NBVzBq725x0cPpSL4TY5y33SY4RBv1u57asjnzzYYVBJM4SQFVXb
RLxR4xKN1TnQlZN8Igox3/1bv5x9T9Q0LHQefwvHITChjI9sjVWvmj+0Ddo5XtYQ6zWKgnhjf42P
a+1xZ/pOOuMb2KcBV7ba3yO3I5yTTwuUZ3ZBegsLdIdeoBz8nU/F6TJQRnWoXR27bkvlJ5mD+gZz
F2Gd8a+2zngajx4x3odUhwcS8aOOI5Lillzb1/88m4nXb3+Gv6/kO7AYeFdlJv4Fs4vXZQ1BId92
ospKLFBuONorW4UXWroYHq/88T3BC28RWC2jK6f9kmmrEATWc9Ubvt4LKPIC6QZgZw5NPTD89m80
2KUbh2hsPwLdiDTYXcONdc9Hume8bjY5qkUnkdFt5FVwfvb69O3ladx8biiHwz8DJ+V35VlyXI7O
9daYvZgJ+2TZ4pNrxz/8UebViHuoI0VTD46RogghmKhsdJgpvjRpIoKkxnBfVNu0XMbYE/iJL5o0
d+AvTp2g8EF75hkThBVNdXFV57TiY6CG+NgX8QA60hi9JhpJCCULvAvBj+Ng3OLMBFVHwH+Pb+9S
t7hC15DSAvuYdquO/OFWy6yZzhqe5STC68Rug+6f5FmiNoule//lXWFuUoMKoVIZuUravBGygNCB
InO6ykunk92VFZYQZhXW2nSPg3Ir+V2yVc7BQ6JEgLMGdBuRyqQxSQ2B80/JLWtavEsjWr66BtAJ
UQoTSmco3/ymKwZxrxjMTcqGd1nx9fNwQGGelMPaZeevwTrRO2KMbmSj188PounVs2vX8YHe3mWx
ZQX2xGWTA9Ca1ePHjwPxXw8beUYlzsvyFrwPgD1qnM+peYd11ouzuzV0YE1LDPy4XMsreHBNdRz2
eVtQOvGeobQh0v5vYIS4N6FlRtO/Z/E401Zz/SH34JonbTJ+KTIkBC4ll6hs9WsS6A4+wjEsCYoh
TNQyy0LOLcB+bMsW75pgblDzi/wMHJ8hmBm2YpEVR5RrdKToIqnlHovOiQgIcIABvJ6N7sjRZQvA
c36x1WjOz4rMXJwABJw8gL26iS4qGxPNVyK5Q8kw6+gRw8nwe6zaOZLlvSzqOebl8srNEvZWyc0P
4Q6sTS9SWBlM4aHZpGUp66Uxp7hj2TJrHDCmH8LhwRDKa+sTT0ZQCkC9k1VIrUTb1q/svriYvqNa
xEMzkz5eaewLMTgHkhS9A8Y47uanbIslpOVb82UKs7ylXLT2BLy5xFc6E4pl/d6FZ/e2Tlvoi8xc
1tvdbgY49A4JqyAtO3o6wlxRduEz02qXvbv33A2ykajudGouRKMSlrXTk/OhI/WB/33686t34Af0
U4tIVJ9+QL66ju9qLGn2HUS+ja0PQyz2L0iYvFm4ahlsr1wky9tjCA99QI/UMQR48Fg88hoinFnf
8J3PdcQ3n89wjVOTqNZnxXN9Y3mOzurcFgLp9dkLKPfe4bIOG0QQJXjYh5zrR9/JHG4jSbBcwLwa
4kSsdDIidm9wrLwcRFWio/vcM2WYqn/K16MdI4Y9n5gbAvtYPVOjfjU4p3CwhOWcZ4tw2j/DH/TC
c59Q19hTMn0ssPiiKQ0sNwjYF0AOAOA/dnzDJ72Tumlnsbn8YteBzQDot9/cB7YnO8MaFDol8cVG
34Fxi0G6Yxr8HFifdw1uNSqH1Fwg07qHb3yhomCrZy/EmkK03sEvcsX+S75nwXuc4YY42eEjFeow
w3DkfbSy+N1Hqq7T5HdRSY8apxV6ungOTyVR+FYEENe2OraRIN8JKighHbmlgvhpbkdrpRJ8CQkS
9LC5De9bPo+/b+26x8Su3JyYDdZOdQOhGqGBHrubX8ZowF64JsSYjuFyB0fJWIzmf47ozvRh7ng+
R3846uYzX0zrEA9q1GaaJTfJ0v2OBTGHaglquDEGADXQxAVpdr23pp2XXw07Dzl5yM18fIrP7UUr
OhNPI3O2jwaL3s4x55r/uby5UfMEX80yJ0ePSl8H5su4Dj/Qiz1korbG3OHFcABhWEXfJHAvAMGu
g91HfbHUV2ycC8CCpqZLEM6tCpWlHL13dVgxR+003qSD+FpEkEtMtqi2rmpwHgLB79Pik96xqxod
UBNEbhJ1a1A3I2b6vVI4BZcXQFcaz7kC9vI86gAhuFoNGBSW7Nz2ns9tG/DL0+4+dDazDCGLdiPr
pOmucvsnMZn43pmBCodxg50wsRO7Hqe4iGWWPxykMFCz359o8+95Nw8XOOtjhh7f7u3vFOUh78Ch
V/+ifR+vgH1/7u1nOu5ZBaU2tQI56SmUsUziWIUMSVf22b7WxX2lQforVrJQkMqvJBC2WycN9jY9
sMbf9bsUSDHrOJJb9bsb+MVVnOXC2xEOX4MecisT/ds+VoeyA2PRcJ65imp4Vx92mg3/2PtvBlw5
fNNNr87czu/rMcu8g2OAHZ0tFU+4x6gi7GabOuEVlqI9EF75t6++MLzy4O8XXpnXFYHYaHy0ghrc
x3KV2q4oBK00vaMxuQHsSTXiZV4dzyYO7zA47zVB9MS/ktp/0Y3RAJF7EQqCiexzYN9ox/q+6EqB
jTpA7h2+w4JA/MS1Ym6Y6L0yxMw7Fif4kmh6Di7fDM6ARt5VNX6/doQuD91QHB/yJd33Ucg7PSt9
IcM9l+yV8030U669Mr+cUybzyKSEmV26lK9p77J0mt8HSYxdO+JUQQ1FU3uc+nVKOxIsU1uLR5uB
yTk0TTY3Z6752QwQeyH9F6hSASFeezYXa4BNl9J5JQ69DYdBNf6bWuuWciGJYG9wZt+eR/04D6ns
ayHxkGGpi+/7b4oJhutzpSGV+Q4qTCasPPT7XhgRo0t05t6ecz1S4urwEKl1iNJ4bX/hnmkP9p8Z
nmY19t0Gik9+OZ8PnVdt7p5Q2TGDAeTZUdqzXDmX/kA1HAGdO7lTwN3oELHGWGxFCCGgPonBqiOi
o34niYM8GiEHe0Orp+Jw1/139/63EM92d0x7V8z1iOc8Qj0wQrXmRrJjzrD8ZdfFdvE9Qea8uaCX
GXiWHA9rdEEZfP109ezYJl3p9g40O1aFjukDx0peOWUu976cxxlOzFLPqA4Ci26cymnd4zoYPLJ7
fAxjRfRITWn8jruoAbuOwbCi2Q6Y8lXQwHv5ZTDEpdMpw4np+uSXTEzXMfeceKDTYH6ceqDsnFKa
LdfDRU91DLdo6UVl1inDmnyHzekk399iHmE8o45a/eHIpvsNZxTNeO7QZylNKpBW9vK519TLTuzW
8f2lm2eU/hsz1vy2h/Hxz/YYPyz4sMOf3+d12l5fj4UD2tHDGiE8U+6RyDyOwWqAIoxI/WKZrJFc
vMXU0dG9j9CtDfkCXR2dhdbuNzl6c23SrZaf/C/6oLr3
"""))

##file ez_setup.py
EZ_SETUP_PY = zlib.decompress(base64.b64decode(b"""
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
mP0HJ8SJTQ==
"""))

##file activate.sh
ACTIVATE_SH = zlib.decompress(base64.b64decode(b"""
eJytU11P2zAUffevuKQ8AFqJ+srUh6IhgcTKRFgnjSLXTW4aS6ld2U6zgvbfd50PSD+GNI08JLHv
8fW5557bg4dMWkhljrAsrIM5QmExgVK6DAKrCxMjzKUKRezkWjgM4Cw1eglzYbMz1oONLiAWSmkH
plAgHSTSYOzyDWMJtqfg5BReGNAjU3iEvoLgmN/dfuGTm/uH76Nb/m30cB3AE3wGl6GqkP7x28ND
0FcE/lpp4yrg616hLDrYO1TFU8mqb6+u3Ga6yBNI0BHnqigQKoFnm32CMpNxBplYIwj6UCjWy6UP
u0y4Sq8mFakWizwn3ZyGBd1NMtBfqo1frAQJ2xy15wA/SFtduCbspFo0abaAXgg49rwhzoRaoIWS
miQS/9qAF5yuNWhXxByTHXEvRxHp2df16md0zSdX99HN3fiAyFVpfbMlz9/aFA0OdSka7DWJgHs9
igbvtqgJtxRqSBu9Gk/eiB0RLyIyhEBplaB1pvBGwx1uPYgwT6EFHO3c3veh1qHt1b8ZmbqOS2Mw
p+4rB2thpJjnaLue3r6bsQ7VYcB5Z8l5wBoRuvWwPYuSjLW9m0UHHXJ+eTPm49HXK84vGljX/WxX
TZ/Mt6GSLJiRuVGJJcJ0K+80mFVKEsdd9by1pMjJ2xa9W2FEO4rst5BxM+baSBKlgSNC5tzqIgzL
sjx/RkdmXZ+ToUOrU1cKg6HwGUL26prHDq0ZpTxIcDqbPUFdC+YW306fvFPUaX2AWtqxH/ugsf+A
kf/Pcf/3UW/HnBT5Axjqy2Y=
"""))

##file activate.bat
ACTIVATE_BAT = zlib.decompress(base64.b64decode(b"""
eJx9kMsOgjAQRfdN+g+zoAn8goZEDESJPBpEViSzkFbZ0IX8f+RRaVW0u5mee3PanbjeFSgpKXmI
Hqq4KC9BglFW+YjWhEgJJa2ETvXQCNl2ogFe5CkvwaUEhjPm543vcOdAiacjLxzzJFw6f2bZCsZ0
2YitXPtswawi1zwgC9II0QPD/RELyuOb1jB/Sg0rNhM31Ss4n2I+7ibLb8epQGco2Rja1Fs/zeoa
cR9nWnprJaMspOQJdBR1/g==
"""))

##file deactivate.bat
DEACTIVATE_BAT = zlib.decompress(base64.b64decode(b"""
eJxzSE3OyFfIT0vj4spMU0hJTcvMS01RiPf3cYkP8wwKCXX0iQ8I8vcNCFHQ4FIAguLUEgWIgK0q
FlWqXJpcICVYpGzx2OAY4oFsPpCLbjpQCLvZILVcXFaufi5cACHzOrI=
"""))

##file distutils-init.py
DISTUTILS_INIT = zlib.decompress(base64.b64decode(b"""
eJytVk2L5DYQvetXFN0E28msCcltoVkIe1lYcgiBHIbBaGy5Wxm3ZCT1dHd+faokty35Y5PDGmZw
q0pVr56qnizPvTYOtGUyvNn7+HrlRkl1tPBYqLVq5bHnxgoD+/SntKC0Aw7v0rgL74R6h7NuLp14
AqvhKqDmCi5WgHTgNLRSNeBOAqxrOvnKWCON4mcBBwRT9tydymGFTNZdnOxsReuRx99aqnzmnsew
yqpqZSeqqniCbAyTFUy2YxClzZle8jRNAYcFlHyxZ4xffGSAz4Ozkl5yv0TP7k+sNGJmTAU9r9/4
UQB38IMF3vcCgRNBr8iUCgwRLZ2uuZNaAbdh8W6dOE+BPu0KJjorAozKl1BVpVTIgst/foJZdd5N
3ESd615MJHpGU1dkrqqkkg7D9fesKEojeJMXBWOt0REEGNqEFjZMiDocD2Nsv8fiXX2C14vsmkrc
HEyZodHCqszBm9JXOOEfUnIUzteO/YIO0ojaaXMfAp0AybliV+mrhQ/UZSdumlo3IhBGLkiw0Zeh
8Xxy0RCmsjeilTesCPvC/+64a/GMqQcyDPrrL1kgNi2rrPX5zFVTTiUMhU4LeF4aX8cFH6buuLWT
U554DK1ETyNamhTeyX9EpXtqAAu5FV0bOdFDuHG1RGoMN/cK2bE0k79rJVJPepauB3h+SdzYN/2j
vko6h7jD7uiqQOgT7L7iWe2KIgmXVFvO6wvlLcGsU79K+PijChIUAsxXo1M7TEbfmFMaehtaxX5k
jKCTdFWhjf30E3vkVn7Gf0a+XqiMcuHFhsNMV+PDbH1vHmA1SURLmP1qGpaZIi7mN2KtPWYhyD6S
QHFDB5vP4w6w9iO26NgXvuOB7eGvE/caX/OuC6MmzIcL3RKhIKCC2NC2iCHoPk5ar628ZVO/0h5f
/XAz7FCAklp2QcZG3VvdtLpn7rVo40cHJ45FhNq7S0umPHWasKCGoBKhTqOUdwgi9zQuZ5d8SqEa
e5V4qWQzxFmxHOFwHkac9bvIaXvBUhNdJarJV+Ab4S5GBTf2PxoX2Vk2czolo67PRgUVu+rv7qQV
3iA1Bhody9Tkh2M0zvblJMeV7UUtW1kfsPvC4RxI3QZukMSwuFS9Yd0nj9UpJmMJNk36SFmwLZD4
qdHouqqG+V03sq36Y2pmexdMohBvMUlfUptMonHJpHUoonhRknWT2dgJSHS/I9ULVCmm/yAePbaJ
j4zrxM+YnO2diB/M79zflGmoyLZCfWTNf+Tm+NBUz80QbyXL4Dvy/61PEnoQLd3LazqWXsedv47H
fSQ9FkUdCa9FPoKir8XaFf6os69ffvv85Y/Mf96jjI1OqSaNy8+PDS+I5oFrj7fyG35rkR7ipTDu
FN0mApLLGQLMTrRsJMZ00/tP8DzkfkmSU9S4GccdbPPcVvprxco2u2LRYXHH/Avon569
"""))

##file distutils.cfg
DISTUTILS_CFG = zlib.decompress(base64.b64decode(b"""
eJxNj00KwkAMhfc9xYNuxe4Ft57AjYiUtDO1wXSmNJnK3N5pdSEEAu8nH6lxHVlRhtDHMPATA4uH
xJ4EFmGbvfJiicSHFRzUSISMY6hq3GLCRLnIvSTnEefN0FIjw5tF0Hkk9Q5dRunBsVoyFi24aaLg
9FDOlL0FPGluf4QjcInLlxd6f6rqkgPu/5nHLg0cXCscXoozRrP51DRT3j9QNl99AP53T2Q=
"""))

##file activate_this.py
ACTIVATE_THIS = zlib.decompress(base64.b64decode(b"""
eJx1UsGOnDAMvecrIlYriDRlKvU20h5aaY+teuilGo1QALO4CwlKAjP8fe1QGGalRoLEefbzs+Mk
Sb7NcvRo3iTcoGqwgyy06As+HWSNVciKaBTFywYoJWc7yit2ndBVwEkHkIzKCV0YdQdmkvShs6YH
E3IhfjFaaSNLoHxQy2sLJrL0ow98JQmEG/rAYn7OobVGogngBgf0P0hjgwgt7HOUaI5DdBVJkggR
3HwSktaqWcCtgiHIH7qHV+esW2CnkRJ+9R5cQGsikkWEV/J7leVGs9TV4TvcO5QOOrTHYI+xeCjY
JR/m9GPDHv2oSZunUokS2A/WBelnvx6tF6LUJO2FjjlH5zU6Q+Kz/9m69LxvSZVSwiOlGnT1rt/A
77j+WDQZ8x9k2mFJetOle88+lc8sJJ/AeerI+fTlQigTfVqJUiXoKaaC3AqmI+KOnivjMLbvBVFU
1JDruuadNGcPmkgiBTnQXUGUDd6IK9JEQ9yPdM96xZP8bieeMRqTuqbxIbbey2DjVUNzRs1rosFS
TsLAdS/0fBGNdTGKhuqD7mUmsFlgGjN2eSj1tM3GnjfXwwCmzjhMbR4rLZXXk+Z/6Hp7Pn2+kJ49
jfgLHgI4Jg==
"""))

if __name__ == '__main__':
    main()

## TODO:
## Copy python.exe.manifest
## Monkeypatch distutils.sysconfig
