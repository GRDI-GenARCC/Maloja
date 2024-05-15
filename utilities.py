import yaml
import logging
import re
import random
import string
from yaml import CLoader, CDumper
# only works when CLOADER (amazon's cloudformation yaml loader) is provided


def load_file(file_location, isBinary=''):
    try:
        if isBinary == 'b':
            file = open(file_location, 'rb')
        else:
            file = open(file_location, 'r')
    except FileNotFoundError:
        logging.debug("File not found.")

    return file.read()


def write_file(file_location, contents, isBinary=''):
    if isBinary == 'b':
        file = open(file_location, 'wb')
    else:
        file = open(file_location, 'w')

    try:
        file.write(contents)
    except PermissionError:
        logging.debug("Insufficient Permissions to write to file.")

    return 0


def import_config():
    file_location = "amzn.yaml"

    config_contents = load_file(file_location)
    config = yaml.load(config_contents, Loader=CLoader)

    # Apply initial changes to config
    config["pipeline"]["jobDefinition"] = append_UUID(config["pipeline"]["jobDefinition"])
    return config


def enforce_cidr(address):
    if (re.search(r"^([0-9]{1,3}\.){3}[0-9]{1,3}$", address)):
        return f"{address}/32"
    else:
        return address


def windows_to_linux_line_end(file_location):
    WINDOWS_LINE_END = b'\r\n'
    UNIX_LINE_END = b'\n'

    content = load_file(file_location, isBinary='b')
    content = content.replace(WINDOWS_LINE_END, UNIX_LINE_END)
    writeFile(file_location, content, isBinary='b')


def append_UUID(text):
    import uuid

    # UUID4 is used because version 1 is not anonymous. Version 2, and 5 are using MD5 and SHA-1 respectively. 4 is just random
    randomText = str(uuid.uuid4())
    return f'{text}-{randomText}'
