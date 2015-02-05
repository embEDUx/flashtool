from __future__ import unicode_literals
__author__ = 'mahieke'

import re
import sys
import logging as log
import subprocess, datetime, os, time, signal
import shutil
from colorama import Fore
from os.path import abspath, realpath, join as joinpath

class TimeoutException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        s = self.message
        return s

class SubprocessCallException(Exception):
    def __init__(self, message, err):
        self.message = message
        self.err = err

    def __str__(self):
        s = self.message
        for line in self.err:
            s += '\n   {}'.format(str(line))

        return s

def user_prompt(question, info, check=None):
    '''

    :param question: Output for user prompt
    :param info: short info for user
    :param check: List with valid user input
    :return: user input string
    '''

    if check:
        combined = create_regex_allowed(check)
        user_input = get_input(u'{0:s} [{1:s}]\n{2:s}: '.format(question, combined.replace('^', '').replace('$', ''), info))
        while not re.match(combined, user_input):
            user_input = get_input(u'{0:s} [{1:s}]\n{2:s}: '.format(question, combined.replace('^', '').replace('$', ''), info))
    else:
        user_input = get_input(u'{0:s}\n{1:s}: '.format(question, info))

    return user_input


def user_select(question, lower, upper):
    '''

    :param question: Output for user prompt
    :param info: short info for user
    :param check: List with valid user input
    :return: user input string
    '''

    combined = create_regex_allowed(map(lambda i: str(i), range(lower, upper)))
    user_input = get_input(u'{0:s} [{1}-{2}]: '.format(question, lower, upper-1))
    while not re.match(combined, user_input):
        user_input = get_input(u'{0:s} [{1}-{2}]: '.format(question, lower, upper-1))

    return user_input


def create_regex_allowed(chk):
    return "(^" + "$)|(^".join(chk) + "$)"


# input compatibility for python2 to python3
def get_input(prompt):
    if sys.hexversion > 0x03000000:
        log.debug('USING input() FUNCTION (PYTHON>3.0)')
        return input(prompt)
    else:
        log.debug('USING raw_input() FUNCTION (PYTHON<=3.0)')
        return raw_input(prompt)


import os
# compatibility function: shutil.which() does not exist in version
def shutil_which(cmd, mode=os.F_OK | os.X_OK, path=None):
    if sys.hexversion >= 0x03030000:
        log.debug('USING shutil.which() FUNCTION (PYTHON>=3.3)')
        return shutil.which(cmd, mode, path)
    else:
        # Copied from: https://hg.python.org/cpython/file/6860263c05b3/Lib/shutil.py#l1068
        log.debug('USING OWN which() IMPLEMENTATION (PYTHON<3.3)')
        # Check that a given file can be accessed with the correct mode.
        # Additionally check that `file` is not a directory, as on Windows
        # directories pass the os.access check.
        def _access_check(fn, mode):
            return (os.path.exists(fn) and os.access(fn, mode)
                    and not os.path.isdir(fn))

        # If we're given a path with a directory part, look it up directly rather
        # than referring to PATH directories. This includes checking relative to the
        # current directory, e.g. ./script
        if os.path.dirname(cmd):
            if _access_check(cmd, mode):
                return cmd
            return None

        if path is None:
            path = os.environ.get("PATH", os.defpath)
        if not path:
            return None
        path = path.split(os.pathsep)

        if sys.platform == "win32":
            # The current directory takes precedence on Windows.
            if not os.curdir in path:
                path.insert(0, os.curdir)

            # PATHEXT is necessary to check on Windows.
            pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
            # See if the given file matches any of the expected path extensions.
            # This will allow us to short circuit when given "python.exe".
            # If it does match, only test that one, otherwise we have to try
            # others.
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                files = [cmd]
            else:
                files = [cmd + ext for ext in pathext]
        else:
            # On other platforms you don't have things like PATHEXT to tell you
            # what file suffixes are executable, so just pass on cmd as-is.
            files = [cmd]

        seen = set()
        for dir in path:
            normdir = os.path.normcase(dir)
            if not normdir in seen:
                seen.add(normdir)
                for thefile in files:
                    name = os.path.join(dir, thefile)
                    if _access_check(name, mode):
                        return name
        return None


def get_size_block_dev(dev_name, partition=None):
    '''

    :param dev_name: Disk name of block setup
    :param partition:  Partition of disk
    :return: Size of disk/partition
    '''
    BLOCK_SIZE_BYTES = 0
    blocks = 0

    sys_path = '/sys/block/{}/'.format(dev_name)

    block_size_path = sys_path + 'queue/physical_block_size'
    if partition:
        size_path = sys_path + '{}/size'.format(partition)
    else:
        size_path = sys_path + 'size'

    try:
        BLOCK_SIZE_BYTES = int(open(block_size_path).read())
        blocks = int(open(size_path).read())
        log.debug('INFO FROM: {})'.format(size_path))
        log.debug('{} HAS {} BLOCKS (BLOCK SIZE: {})'.format(dev_name, blocks, BLOCK_SIZE_BYTES))
    except Exception as e:
        log.debug('CAN\'T DETERMINE SIZE OF BLOCK DEVICE {}, EXCEPTION MESSAGE: {}'.format(dev_name, e))

    return blocks * BLOCK_SIZE_BYTES


import os, grp
def check_permissions(file):
    file_stat = os.stat(file)
    gr = [file_stat.st_uid, file_stat.st_gid]
    file_groups = [grp.getgrgid(g).gr_name for g in gr]
    current_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]

    if any([group in current_groups for group in file_groups]):
        return
    else:
        print(Fore.YELLOW + 'Permissions are needed for this operation. Groups: {}'.format(', '.join(file_groups)))
        exit()


import signal
def os_call(command, timeout=None, allow_user_interrupt=True):
    """call shell-command and either return its output or kill it
    if it doesn't normally exit within timeout seconds and raise exception"""

    def warn(a, b):
        print(Fore.RED + '   Interrupting this procedure is restricted!')

    if not allow_user_interrupt:
        s = signal.signal(signal.SIGINT, warn)

    start = datetime.datetime.now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if timeout:
        while process.poll() is None:
            time.sleep(0.2)
            now = datetime.datetime.now()
            if (now - start).seconds > timeout:
                os.kill(process.pid, signal.SIGKILL)
                os.waitpid(-1, os.WNOHANG)
                raise TimeoutException('"{}" COMMAND TIMED OUT'.format(' '.join(command)))

    out = process.stdout.readlines()
    err = process.stderr.readlines()

    if not allow_user_interrupt:
        signal.signal(signal.SIGINT, s)

    process.wait()

    if process.returncode != 0:
        raise SubprocessCallException('"{}" COMMAND FAILED:'.format(' '.join(command)), err)
    else:
        if out:
            for line in out:
                print(Fore.GREEN + '    {}'.format(line))

    return

def untar(tar, target):
    import tarfile

    class tracker():
        def __init__(self, members):
            self.count = 0
            self.members = members

            self.resolved = lambda x: realpath(abspath(x))

        def badpath(self, path, base):
            # joinpath will ignore base if path is absolute
            return not self.resolved(joinpath(base,path)).startswith(base)

        def track_progress(self):
            base = self.resolved(".")
            print('   untar file: [{:10}]'.format(' '*10), end='\r')
            for member in self.members:
                if self.badpath(member.name, base):
                    print(Fore.YELLOW + '   BAD PATH DETECTED. {}'.format(member.name))
                    continue

                # this will be the current file being extracted
                self.count += 1
                if self.count % 200 == 0:
                    print('   untar file: [{:10}]'.format(' '*10), end='\r')
                    self.count = 0
                elif self.count % 20 == 0:
                    amount = int(self.count / 20)
                    if amount == 0:
                        load = '>'
                    elif amount == 1:
                        load = '>>'
                    elif amount == 2:
                        load = '>>>'
                    else:
                        load = '{}>>>'.format(' '*amount)[:9]

                    print('   untar file: [{:10}]'.format(load), end='\r')

                yield member

    try:
        tarball = tarfile.open(tar, 'r')
    except Exception as e:
        print(Fore.RED + '   {}'.format(str(e)))

    try:
        tarball.extractall(path=target, members=tracker(tarball).track_progress())
        print('   untar file: [>>>>>>>>>>]', end='\r')
        print('\n')
    except KeyboardInterrupt as e:
        print('\n')
        print(Fore.RED + '   User aborted extracting tarball.')
        raise

    except Exception as e:
        print('\n')
        print(Fore.RED + '   Extracting tarball failed:')
        raise

    finally:
        tarball.close()


def get_terminal_size():
    import os
    return os.popen('stty size', 'r').read().split()

