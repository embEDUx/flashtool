__author__ = 'mahieke'

from embedux_flashtool.setup.recipe import Recipe

class ProductsConfig(Recipe):
    attr = ['Uboot', 'Linux_Boot', 'Linux_Root', 'Linux_Config', 'Rootfs', 'Misc_Boot', 'Misc_Root']

    def __init__(self, attributes):
        self.check_attributes(attributes)

        # set attributes specified in attr with corresponding objects
        new_attributes = {}
        for k,v in attributes.items():
            if v:
                new_attributes[k] = eval(k)(v)

        self.check_attributes(new_attributes)

        Recipe.__init__(self, new_attributes)


class Uboot(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Linux_Boot(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Linux_Root(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Linux_Config(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Rootfs(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Misc_Boot(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


class Misc_Root(Recipe):
    attr = ['module', 'device']

    def __init__(self, attributes):
        self.check_attributes(attributes)
        Recipe.__init__(self, attributes)


__entry__ = ProductsConfig