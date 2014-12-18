__author__ = 'mahieke'

from embedux_flashtool.setup.prepare.recipe import Recipe

class ComponentsConfig(Recipe):
    attr = ['Uboot', 'Linux', 'Rootfs', 'Misc']

    def __init__(self, attributes, rec):
        self.check_attributes(attributes)

        # set attributes specified in attr with corresponding objects
        new_attributes = {}
        for k,v in attributes.iteritems():
            new_attributes[k] = eval(k)(v)

        self.check_attributes(new_attributes)

        Recipe.__init__(self, new_attributes)


class Linux(Recipe):
    attr = ['module', 'kernel_dest', 'modules_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Uboot(Recipe):
    attr = ['module', 'uboot_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)

class Rootfs(Recipe):
    attr = ['module', 'rootfs_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)

class Misc(Recipe):
    attr = ['module', 'boot_dest', 'root_dest']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


__entry__ = ComponentsConfig