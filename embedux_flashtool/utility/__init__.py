__author__ = 'mahieke'

import re
import sys

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


def create_regex_allowed(chk):
    if isinstance(chk, str) or isinstance(chk, list):
        return "(^" + "$)|(^".join(chk) + "$)"


# input compatibility for python2 to python3
def get_input(prompt):
    if sys.hexversion > 0x03000000:
        return input(prompt)
    else:
        return raw_input(prompt)


import os
# compatibility function: shutil.which() does not exist in version
def shutil_which(cmd, mode=os.F_OK | os.X_OK, path=None):
    if sys.hexversion > 0x03030000:
        import shutil
        return shutil.which(cmd, mode, path)
    else:
        # Copied from: https://hg.python.org/cpython/file/6860263c05b3/Lib/shutil.py#l1068
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


def get_size_block_dev(dev_name):
    BLOCK_SIZE_BYTES = 512
    try:
        BLOCK_SIZE_BYTES = int(open('/sys/block/{}/queue/physical_block_size'.format(dev_name)).read())
        blocks = int(open('/sys/block/{}/size'.format(dev_name)).read())
    except:
        blocks = 0

    return blocks * BLOCK_SIZE_BYTES