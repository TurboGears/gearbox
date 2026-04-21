import configparser
import os
from logging.config import fileConfig


def setup_logging(config_uri, fileConfig=fileConfig):
    """
    Set up logging via the logging module's fileConfig function with the
    filename specified via ``config_uri`` (a string in the form
    ``filename#sectionname``).

    Config parser defaults are specified for the special ``__file__``
    and ``here`` variables, similar to PasteDeploy config loading.
    """
    path, _ = _getpathsec(config_uri, None)
    parser = configparser.ConfigParser()
    parser.read([path])
    if parser.has_section("loggers"):
        config_file = os.path.abspath(path)
        config_options = dict(__file__=config_file, here=os.path.dirname(config_file))

        fileConfig(config_file, config_options, disable_existing_loggers=False)


def _getpathsec(config_uri, name):
    if "#" in config_uri:
        path, section = config_uri.split("#", 1)
    else:
        path, section = config_uri, "main"
    if name:
        section = name
    return path, section
