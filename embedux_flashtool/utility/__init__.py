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