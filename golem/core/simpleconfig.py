import ConfigParser
import logging
import os
import shutil

logger = logging.getLogger(__name__)


class ConfigEntry(object):
    """ Simple config entry representation """

    def __init__(self, section, key, value):
        """ Create new config entry
        :param str section: section name
        :param str key: config entry name
        :param value: config entry value
        """
        self._key = key
        self._value = value
        self._section = section
        self._value_type = type(value)

    def section(self):
        """ Return config entry section """
        return self._section

    def key(self):
        """ Return config entry name """
        return self._key

    def value(self):
        """ Return config entry value """
        return self._value

    def set_key(self, k):
        self._key = k

    def set_value(self, v):
        self._value = v

    def set_value_from_str(self, val):
        """Change string to the value type and save it as a value
        :param str val: string to be converse to value
        """
        self.set_value(self._value_type(val))

    @classmethod
    def create_property(cls, section, key, value, other, prop_name):
        """Create new property: config entry with getter and setter method
           for this property in other object. Append this entry to property
           list in other object.
        :param str section: config entry section name
        :param str key: config entry name
        :param value: config entry value
        :param other: object instance for which new setter, getter and
                      property entry should be created
        :param str prop_name: property name
        :return:
        """
        property_ = ConfigEntry(section, key, value)

        getter_name = "get_{}".format(prop_name)
        setter_name = "set_{}".format(prop_name)

        def get_prop(_self):
            return getattr(_self, prop_name).value()

        def set_prop(_self, val):
            return getattr(_self, prop_name).set_value(val)

        def get_properties(_self):
            return getattr(_self, '_properties')

        setattr(other, prop_name, property_)
        setattr(other.__class__, getter_name, get_prop)
        setattr(other.__class__, setter_name, set_prop)

        if not hasattr(other, '_properties'):
            setattr(other, '_properties', [])

        if not hasattr(other.__class__, 'properties'):
            setattr(other.__class__, 'properties', get_properties)

        other._properties.append(property_)


class SimpleConfig(object):
    """ Simple configuration manager"""

    def __init__(self, node_config, cfg_file, refresh=False, keep_old=True):
        """Read existing configuration or create new one if it doesn't exist
           or refresh option is set to True.
        :param node_config: node specific configuration
        :param str cfg_file: configuration file name
        :param bool refresh: *Default: False*  if set to True, than
                             configuration for given node should be written
                             even if it already exists.
        """
        self._node_config = node_config

        logger_msg = "Reading config from file {}".format(cfg_file)

        try:
            write_config = True
            cfg = ConfigParser.ConfigParser()
            files = cfg.read(cfg_file)

            if files:
                if self._node_config.section() in cfg.sections():
                    if refresh:
                        cfg.remove_section(self._node_config.section())
                        cfg.add_section(self._node_config.section())
                    else:
                        self.__read_options(cfg)

                        if not keep_old:
                            self.__remove_old_options(cfg)
                else:
                    cfg.add_section(self._node_config.section())

                logger.info("{} ... successfully".format(logger_msg))
            else:
                logger.info("{} ... failed".format(logger_msg))
                cfg = self.__create_fresh_config()

            if write_config:
                logger.info(
                    "Writing %r's configuration to %r",
                    self.get_node_config().section(),
                    cfg_file
                )
                self.__write_config(cfg, cfg_file)
        except Exception as ex:
            logger.warning(
                "%r ... failed with an exception: %s",
                logger_msg,
                ex
            )
            # no additional try catch because this cannot fail (if it
            # fails then the program shouldn't start anyway)
            logger.info(
                "Failed to write configuration file."
                " Creating fresh config."
            )
            self.__write_config(self.__create_fresh_config(), cfg_file)

    def get_node_config(self):
        """ Return node specific configuration """
        return self._node_config

    def __create_fresh_config(self):
        cfg = ConfigParser.ConfigParser()
        cfg.add_section(self.get_node_config().section())
        return cfg

    def __write_config(self, cfg, cfg_file):
        self.__write_options(cfg)

        if os.path.exists(cfg_file):
            backup_file_name = "{}.bak".format(cfg_file)
            logger.info(
                "Creating backup configuration file %r",
                backup_file_name
            )
            shutil.copy(cfg_file, backup_file_name)
        elif not os.path.exists(os.path.dirname(cfg_file)):
            os.makedirs(os.path.dirname(cfg_file))

        with open(cfg_file, 'w') as f:
            cfg.write(f)

    @staticmethod
    def __read_option(cfg, property_):
        return cfg.get(property_.section(), property_.key())

    @staticmethod
    def __write_option(cfg, property_):
        return cfg.set(property_.section(), property_.key(), property_.value())

    def __read_options(self, cfg):
        for prop in self.get_node_config().properties():
            try:
                prop.set_value_from_str(self.__read_option(cfg, prop))
            except ConfigParser.NoOptionError:
                logger.info(
                    "Adding new config option: %r (%r)",
                    prop.key(),
                    prop.value()
                )

    def __write_options(self, cfg):
        for prop in self.get_node_config().properties():
            self.__write_option(cfg, prop)

    def __remove_old_options(self, cfg):
        props = [p.key() for p in self.get_node_config().properties()]
        for opt in cfg.options('Node'):
            if opt not in props:
                cfg.remove_option('Node', opt)
