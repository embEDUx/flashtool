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
    Function to handle user input with limited input possibilities.

    :param question: Output for user prompt
    :param info: short info for user
    :param check: List with valid user input
    :return: user input string
    '''

    if check:
        combined = create_regex_allowed(check)
        user_input = input(u'{0:s} [{1:s}]\n{2:s}: '.format(question, combined.replace('^', '').replace('$', ''), info))
        while not re.match(combined, user_input):
            user_input = input(u'{0:s} [{1:s}]\n{2:s}: '.format(question, combined.replace('^', '').replace('$', ''), info))
    else:
        user_input = input(u'{0:s}\n{1:s}: '.format(question, info))

    return user_input

def user_select(question, lower, upper):
    '''
    Helper function to ask the user for a selection in a numeric range.

    :param question: Output for user prompt
    :param info: short info for user
    :param check: List with valid user input
    :return: user input string
    '''

    combined = create_regex_allowed(map(lambda i: str(i), range(lower, upper)))
    user_input = input(u'{0:s} [{1}-{2}]: '.format(question, lower, upper-1))
    while not re.match(combined, user_input):
        user_input = input(u'{0:s} [{1}-{2}]: '.format(question, lower, upper-1))

    return user_input

def create_regex_allowed(chk):
    '''
    Creates a regex to check an input matching several keywords.

    :param chk: List with keywords which are allowed
    :return: string in regex notation
    '''
    return "(^" + "$)|(^".join(chk) + "$)"


def get_size_block_dev(dev_name, partition=None):
    '''
    Function to determine the size of a partition or a whole block device.

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
    '''
    Function which checks if access permission are provided for the user.
    If not the user will be informed which Groups have access writes to the file
    and quits the program.
    :param file: file to check
    :return: None
    '''
    file_stat = os.stat(file)
    gr = [file_stat.st_uid, file_stat.st_gid]
    file_groups = [grp.getgrgid(g).gr_name for g in gr]
    current_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]

    if any([group in current_groups for group in file_groups]):
        pass
    else:
        print(Fore.YELLOW + 'Permissions are needed for this operation. Groups: {}'.format(', '.join(file_groups)))
        exit()


import signal
def os_call(command, timeout=None, allow_user_interrupt=True):
    '''
    Call shell-command with timeout. Can also block user interrupts
    if wanted

    :param command: Command as list, suitable for the subprocess Popen call
    :param timeout: time in seconds
    :param allow_user_interrupt: flag if user interrupt is allowed
    :return: None
    '''

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

    process.wait()

    if not allow_user_interrupt:
        signal.signal(signal.SIGINT, s)

    if process.returncode != 0:
        raise SubprocessCallException('"{}" COMMAND FAILED:'.format(' '.join(command)), err)
    else:
        if out:
            for line in out:
                print(Fore.GREEN + '    {}'.format(line))

def untar(tar, target):
    '''
    Unpack a tarball to a target location using tarfile. The
    progress of the unpack procedure will be shown.

    :param tar: tarball file
    :param target: target location
    :return: None
    '''
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
        tarfile.open()
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
    '''
    Helper to get the current size of the terminal the Flashtool was
    called.

    :return: list with width and height
    '''
    import os
    return os.popen('stty size', 'r').read().split()

