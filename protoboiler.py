#!/usr/bin/env python3

import os
import sys
import json

#   ---------------------------------------------------------------------------
__app__ = os.path.basename(__file__)
__version__ = '0.01'

#   -----------------------------------
#   Logging
#   -----------------------------------

import logging
from logging import debug, info, warning, error, critical, log

LOGGING_FORMAT = '* %(levelname)s * %(message)s'
LOGGING_FILE = __app__ + '.log'

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
def main(argv):
    request = plugin.CodeGeneratorRequest.FromString(sys.stdin.buffer.read())
    response = plugin.CodeGeneratorResponse()
    info(argv)
    boiling(request, response)
    sys.stdout.buffer.write(response.SerializeToString())

#   ---------------------------------------------------------------------------
if __name__ == '__main__':
    main(sys.argv)
