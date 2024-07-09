#!/usr/bin/env python3

import sys
import json
from pathlib import Path

#   ---------------------------------------------------------------------------
__app__ = Path(__file__).stem
__version__ = '0.01'

#   -----------------------------------
#   Logging
#   -----------------------------------

import logging
from logging import debug, info, warning, error, critical, log

LOGGING_FORMAT = '* %(levelname)s * %(message)s'

#   ---------------------------------------------------------------------------
def init_logging(level, fn, mode = 'a'):
    logging.basicConfig(handlers=[logging.FileHandler(fn, mode)], format=LOGGING_FORMAT
    , level=level)

#   -----------------------------------
#   Config
#   -----------------------------------

# -- Configuration parameters with default values
CONFIG_POOL = {
    'LOGGING_LEVEL': logging.INFO,
    'LOGGING_FILE': Path(__app__).with_suffix('.log'),
}

#   ---------------------------------------------------------------------------
class Config(dict):

#   -----------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(CONFIG_POOL)
        args_dict = dict(*args, **kwargs)
        self.update({ key: args_dict[key] for key in CONFIG_POOL if key in args_dict })
        self.__dict__ = self

#   -----------------------------------
    def load_file(self, filename: str):
        context: dict = {}
        with open(filename, 'rb') as f:
            code = compile(f.read(), filename, 'exec')
        exec(code, context)
        self.update({ key: context[key] for key in CONFIG_POOL if key in context })
        self.__dict__ = self

config = Config()

#   -----------------------------------
#   Protobuf
#   -----------------------------------

from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import FileDescriptorProto, DescriptorProto, EnumDescriptorProto

#   ---------------------------------------------------------------------------
def boiling(request: plugin.CodeGeneratorRequest, response: plugin.CodeGeneratorResponse) -> None:
    for proto_file in request.proto_file:
        boiling_file(proto_file, response)

#   ---------------------------------------------------------------------------
def boiling_file(proto_file: FileDescriptorProto, response: plugin.CodeGeneratorResponse) -> None:
    info(f'Process: {proto_file.name}')

    # Create dict of options
    options = str(proto_file.options).strip().replace("\n", ", ").replace('"', "")
    options_dict = dict(item.split(": ") for item in options.split(", ") if options)

    # Create list of dependencies
    dependencies_list = list(proto_file.dependency)

    data = {
        "package": f"{proto_file.package}",
        "filename": f"{proto_file.name}",
        "dependencies": dependencies_list,
        "options": options_dict,
    }

    f = response.file.add()
    f.name = proto_file.name + ".dep.json"
    info(f"Create: {f.name}")
    f.content = json.dumps(data, indent=2)

#   ---------------------------------------------------------------------------
def main():
    request = plugin.CodeGeneratorRequest.FromString(sys.stdin.buffer.read())
    response = plugin.CodeGeneratorResponse()
    init_logging(config.LOGGING_LEVEL, config.LOGGING_FILE, 'w')
    info(request.parameter)
    boiling(request, response)
    sys.stdout.buffer.write(response.SerializeToString())

#   ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()
