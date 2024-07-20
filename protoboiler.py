#!/usr/bin/env python3

import sys
import json
import typing
from pathlib import Path

#   ---------------------------------------------------------------------------
__version__ = '0.02'
__author__ = 'in4lio@gmail.com'

__app__ = Path(__file__).stem

#   -----------------------------------
#   Logging
#   -----------------------------------

import logging
from logging import debug, info, warning, error, critical

LOGGING_FORMAT = '* %(levelname)s * %(message)s'

#   ---------------------------------------------------------------------------
def init_logging(level, fn, mode = 'a'):
    logging.basicConfig(handlers=[logging.FileHandler(fn, mode)], format=LOGGING_FORMAT
    , level=level)

#   -----------------------------------
#   Config
#   -----------------------------------

'''
All available configuration parameters with default values.
'''
CONFIG_POOL = {
    'LOGGING_LEVEL': logging.INFO,
    'LOGGING_FILE': Path(__app__).with_suffix('.log'),
    'IR_FILE': 'ir.json',
#   -- a config file directory
    'PATH': '',
}

#   ---------------------------------------------------------------------------
class Config(dict):

#   -----------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(CONFIG_POOL)
        args_dict = dict(*args, **kwargs)
        args_dict['PATH'] = Path()
        self.from_dict(args_dict)

#   -----------------------------------
    def from_dict(self, data):
        self.update({ key: data[key] for key in CONFIG_POOL if key in data })
        self['PATH'] = Path(self['PATH'])
        for key in self:
            setattr(self, key, self[key])

#   -----------------------------------
    def from_file(self, filename: str):
        context: dict = {}
        with open(filename, 'rb') as f:
            code = compile(f.read(), filename, 'exec')
        exec(code, context)
        context['PATH'] = Path(filename).parent
        self.from_dict(context)

config = Config()

#   -----------------------------------
#   Command line options
#   -----------------------------------

class Opt(dict):

#   -----------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self

#   -----------------------------------
    def from_dict(self, data: dict):
        self.update(data)
        self.__dict__ = self

#   -----------------------------------
    def parse(self, parameter: str):
        self.from_dict(dict(i.split('=') for i in parameter.split(',')))

opt = Opt()

#   -----------------------------------
#   Proto Buffer
#   -----------------------------------
# mypy: disable-error-code="import-untyped"

from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import (
    FileDescriptorProto, ServiceDescriptorProto, MethodDescriptorProto, DescriptorProto,
    FieldDescriptorProto, EnumDescriptorProto, EnumValueDescriptorProto, SourceCodeInfo,
)
from google.protobuf.message import Message

#   -----------------------------------
#   Intermediate representation (IR)
#   -----------------------------------

class IR:
    pool: dict = {}
    decl: list = []

#   -----------------------------------
    '''
    Load IR and global configuration from a JSON file.
    '''
    @staticmethod
    def open(filename: str):
        with open(filename, encoding='utf-8') as f:
            content = json.load(f)

        IR.pool = content['pool']
        IR.decl = content['decl']

#       -- also loading global setting
        config.from_dict(content['config'])
        init_logging(config.LOGGING_LEVEL, config.PATH / config.LOGGING_FILE, 'a')  # type: ignore[attr-defined]

#   -----------------------------------
    '''
    Serialize IR and global configuration into a JSON formatted string.
    '''
    @staticmethod
    def dumps() -> str:
        return json.dumps({ 'pool': IR.pool, 'decl': IR.decl, 'config': config.__dict__ }
        , indent=4, cls=JSONEncoder)

#   ---------------------------------------------------------------------------
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)

        return super().default(o)

#   -----------------------------------
#   Translator
#   -----------------------------------

PROTO_FILE: FileDescriptorProto | None = None

def search_location(path: list[int]) -> SourceCodeInfo.Location | None:
    if PROTO_FILE is None:
        return None

    for loc in PROTO_FILE.source_code_info.location:
        if list(loc.path) == path:
            return loc

    return None

#   ---------------------------------------------------------------------------
def set_decl_comments(decl, path: list[int]):
    loc = search_location(path)
    if loc:
        if loc.HasField('leading_comments'):
            decl['leading_comments'] = loc.leading_comments
        if loc.HasField("trailing_comments"):
            decl['trailing_comments'] = loc.trailing_comments

#   ---------------------------------------------------------------------------
def get_enum_value(desc: EnumValueDescriptorProto, scope: list, parent: str, path: list[int]):
    data = { 'name:': desc.name, 'number': desc.number }
    set_decl_comments(data, path)
    scope.append(data)

#   ---------------------------------------------------------------------------
def walk_enum(desc: EnumDescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name

    value: list = []
    walk_list(desc.value, value, usr, path.copy(), walk_handle['enum_value'])

    data = { 'kind': 'ENUM', 'name': desc.name, 'value': value }
    set_decl_comments(data, path)
    IR.pool[usr] = data
    decl.append(usr)

#   ---------------------------------------------------------------------------
def get_field(desc: FieldDescriptorProto, scope: list, parent: str, path: list[int]):
    data = {
        'name': desc.name,
        'type': desc.type_name or FieldDescriptorProto.Type.Name(desc.type).removeprefix('TYPE_'),
        'number': desc.number,
        'label': FieldDescriptorProto.Label.Name(desc.label).removeprefix('LABEL_'),
        'proto3_optional': desc.proto3_optional
    }
    set_decl_comments(data, path)
    scope.append(data)

#   ---------------------------------------------------------------------------
def walk_message(desc: DescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name
    nested: list = []
    walk_list(desc.enum_type, nested, usr, path.copy(), walk_handle['nested_enum'])
    walk_list(desc.nested_type, nested, usr, path.copy(), walk_handle['nested_message'])

    root: list = []
    oneof_decl = [{ 'name': val.name, 'type': 'ONEOF', 'field': []} for val in desc.oneof_decl ]
    for i, field in enumerate(desc.field):
        scope = oneof_decl[field.oneof_index]['field'] if field.HasField('oneof_index') else root
        walk_handle['field']['func'](field, scope, parent
        , path + [walk_handle['field']['number'], i])
    root.extend(oneof_decl)

    data = { 'kind': 'MESSAGE', 'name': desc.name, 'decl': nested, 'field': root }
    set_decl_comments(data, path)
    IR.pool[usr] = data
    decl.append(usr)

#   ---------------------------------------------------------------------------
def walk_method(desc: MethodDescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name
    data = {
        'kind': 'METHOD',
        'name': desc.name,
        'input': desc.input_type,
        'output': desc.output_type,
        'server_streaming': desc.server_streaming,
        'client_streaming': desc.client_streaming,
        'options': get_options(desc.options)
    }
    set_decl_comments(data, path)
    IR.pool[usr] = data
    decl.append(usr)

#   ---------------------------------------------------------------------------
def walk_service(desc: ServiceDescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name
    method: list = []
    walk_list(desc.method, method, usr, path.copy(), walk_handle['method'])
    data = { 'kind': 'SERVICE', 'name': desc.name, 'method': method }
    set_decl_comments(data, path)
    IR.pool[usr] = data
    decl.append(usr)

#   ---------------------------------------------------------------------------
walk_handle: dict = {
    'enum':           { 'func': walk_enum,      'number': FileDescriptorProto.ENUM_TYPE_FIELD_NUMBER },
    'nested_enum':    { 'func': walk_enum,      'number': DescriptorProto.ENUM_TYPE_FIELD_NUMBER },
    'message':        { 'func': walk_message,   'number': FileDescriptorProto.MESSAGE_TYPE_FIELD_NUMBER },
    'nested_message': { 'func': walk_message,   'number': DescriptorProto.NESTED_TYPE_FIELD_NUMBER },
    'service':        { 'func': walk_service,   'number': FileDescriptorProto.SERVICE_FIELD_NUMBER },
    'method':         { 'func': walk_method,    'number': ServiceDescriptorProto.METHOD_FIELD_NUMBER },
    'enum_value':     { 'func': get_enum_value, 'number': EnumDescriptorProto.VALUE_FIELD_NUMBER },
    'field':          { 'func': get_field,      'number': DescriptorProto.FIELD_FIELD_NUMBER },
}

#   ---------------------------------------------------------------------------
def walk_list(data: list, decl: list, parent: str, path: list[int], handle: dict):
    for i, desc in enumerate(data):
        debug('\ntype: %s\n%s', desc.__class__.__name__, desc)
        handle['func'](desc, decl, parent, path + [handle['number'], i])

#   ---------------------------------------------------------------------------
def get_options(options: Message | None) -> dict:
    if not options:
        return {}

    return { desc.name: value for desc, value in options.ListFields() }

#   ---------------------------------------------------------------------------
def walk_file(proto_file: FileDescriptorProto, parent: str):
    info('Process %s', proto_file.name)

    usr = parent + '.' + (proto_file.package or proto_file.name)
    decl: list = []
    walk_list(proto_file.enum_type, decl, usr, [], walk_handle['enum'])
    walk_list(proto_file.message_type, decl, usr, [], walk_handle['message'])
    walk_list(proto_file.service, decl, usr, [], walk_handle['service'])
    IR.pool[usr] = {
        'kind': 'FILE',
        'name': proto_file.name,
        'package': proto_file.package,
        'decl': decl,
        'options': get_options(proto_file.options),
        'dependency': list(proto_file.dependency)
    }
    IR.decl.append(usr)

#   ---------------------------------------------------------------------------
def boiling(request: plugin.CodeGeneratorRequest, response: plugin.CodeGeneratorResponse):
    global PROTO_FILE

    for proto_file in request.proto_file:
        PROTO_FILE = proto_file
        walk_file(proto_file, '')

    ir_file = response.file.add()
    ir_file.name = config.IR_FILE  # type: ignore[attr-defined]
    info('Create %s', ir_file.name)
    ir_file.content = IR.dumps()

#   ---------------------------------------------------------------------------
def main():
    request = plugin.CodeGeneratorRequest.FromString(sys.stdin.buffer.read())
    response = plugin.CodeGeneratorResponse()
    response.supported_features |= plugin.CodeGeneratorResponse.FEATURE_PROTO3_OPTIONAL

    opt.parse(request.parameter)
#   -- we expect to receive a "config" file name via request parameters
    if opt.config:
        config.from_file(opt.config)
    init_logging(config.LOGGING_LEVEL, config.PATH / config.LOGGING_FILE, 'w')
    info(opt)
    info(config)

    boiling(request, response)

    sys.stdout.buffer.write(response.SerializeToString())

#   ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()
