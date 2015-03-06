__author__ = 'mahieke'
from colorama import Fore

def get_products_by_recipe_user_input(recipe, actions, builds, platform, auto):
    '''

    :param recipe:
    :param actions:
    :param builds:
    :param platform:
    :param auto
    :return:
    '''
    yaml_info = {}
    load_cfg = {}

    build_info = builds.get_builds_info()

    # extract information for loading products to platform
    for product_name, values in recipe.load:

        prod = product_name.lower().split('_')
        product = prod[0]

        if product in actions:
            name = ''
            if len(prod) == 1:
                name = product
            elif len(prod) == 2:
                name = prod[1]

            reg_name = actions[product]
            content = {}

            if yaml_info.get(product):
                yaml_info[product].update({
                    name: values
                })
            else:
                yaml_info.update({
                    product : {
                        'r_name': reg_name,
                        name: values
                    }
                })

    load_order = ['rootfs', 'uboot', 'linux', 'misc']
    for product in load_order:
        if product not in yaml_info.keys():
            continue

        value = yaml_info[product]
        file_info = builds.get_build_info(build_info, [product], platform)
        file_types = [i for i in value.keys() if i != 'r_name']

        a = max(len(product),len(reg_name),len(', '.join(file_types)))

        print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))
        for s in [('product',product), ('reg_name', reg_name), ('file_types', ', '.join(file_types))]:
            st = '   | {:12}'.format(s[0] + ':') + '{:<' + str(a) + '} |'
            print(Fore.YELLOW + st.format(s[1]))

        print(Fore.YELLOW + '   +-{}-+'.format('-'*(12+a)))

        files = builds.get_files_path(file_info, reg_name, [(product, file_types)], auto)[0][1]

        load_cfg[product] = []
        for f_type, file in files:
            load_cfg[product].append({
                'f_type': f_type,
                'yaml': value[f_type],
                'file': file,
                'size': int(builds.get_file_size(file))
            })
        print('')

    return load_cfg

import crypt
import getpass
import subprocess
import os

def set_root_password(path_to_rootfs):
    path = '{}/etc/shadow'.format(path_to_rootfs.rstrip('/'))
    if not os.path.exists(path):
        raise FileNotFoundError('Could not find {}'.format(path))

    print('')
    print('Please set a root password for the system or press enter for default password [default \'toor\']:')
    pw = getpass.getpass()

    if pw == '':
        pw = 'toor'

    subprocess.call(['sed', '-i', '1d', path])
    salt_size = 16
    salt = os.urandom(salt_size).decode("ISO-8859-1").replace('\n', '').replace('\r', '')
    salt_string = '$6${}$'.format(salt)
    encrypted_pw = crypt.crypt(pw, salt_string)
    shadow_string = 'root:{}:10770:0:::::\n'.format(encrypted_pw)

    with open(path, 'a') as shadow:
        shadow.write(shadow_string)

