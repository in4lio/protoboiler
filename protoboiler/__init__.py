'''
Protocol Buffers compiler plugin to quickly generate boilerplate code
from your Google Protocol Buffer (proto) definitions.
'''

import sys
import json
from pathlib import Path
from typing import Iterator

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
    'LOGGING_FILE': 'protoboiler.log',
    'IR_FILE': 'ir.json',
    'TEMPLATE_LIST': ('*.*.py', ),
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
        if parameter:
            self.from_dict(dict(i.split('=') for i in parameter.split(',')))
        else:
            self.config = None

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
        init_logging(config.LOGGING_LEVEL, config.PATH / config.LOGGING_FILE, 'a')

#   -----------------------------------
    '''
    Serialize IR and global configuration into a JSON file.
    '''
    @staticmethod
    def dump(f):
        return json.dump({ 'pool': IR.pool, 'decl': IR.decl, 'config': config.__dict__ }, f
        , indent=4, cls=JSONEncoder)

#   -----------------------------------
    '''
    Iterate over filtered declaration USRs.
    Filter types:
        str - a declaration kind
        container[str] - a container with declaration kinds
        callable - a callable filter
    '''
    @staticmethod
    def usr_iter(decl, *filter_list) -> Iterator[str]:
        if filter_list:
            return (usr for usr in decl if all(
                IR.if_kind(filter, usr)
                    if isinstance(filter, str) else
                IR.if_kind_in(filter, usr)
                    if isinstance(filter, set) else
                filter(usr)
                for filter in filter_list
            ))

        return iter(decl)

#   -----------------------------------
    '''
    Iterate over filtered declaration node and USR pairs.
    '''
    @staticmethod
    def node_iter(decl, *filter_list) -> Iterator[tuple[dict, str]]:
        return ((IR.lookup(usr), usr) for usr in IR.usr_iter(decl, *filter_list))

#   -----------------------------------
    @staticmethod
    def lookup(usr: str) -> dict:
        if usr in IR.pool:
            return IR.pool[usr]

        critical('USR (%s) is not found', usr)
        sys.exit()

#   -----------------------------------
    @staticmethod
    def if_kind(value, usr = None):
        func = lambda usr: IR.lookup(usr)['kind'] == value
        return func if usr is None else func(usr)

#   -----------------------------------
    @staticmethod
    def if_kind_in(pool, usr = None):
        func = lambda usr: IR.lookup(usr)['kind'] in pool
        return func if usr is None else func(usr)

#   -----------------------------------
    @staticmethod
    def if_field_eq(field, value, usr = None):
        func = lambda usr: IR.lookup(usr)[field] == value
        return func if usr is None else func(usr)

#   ---------------------------------------------------------------------------
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)

        return super().default(o)

#   -----------------------------------
#   Translator to IR
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
def set_comments(node: dict, path: list[int]):
    loc = search_location(path)
    if loc:
        if loc.HasField('leading_comments'):
            node['leading_comments'] = loc.leading_comments
        if loc.HasField("trailing_comments"):
            node['trailing_comments'] = loc.trailing_comments

#   ---------------------------------------------------------------------------
def get_enum_value(desc: EnumValueDescriptorProto, scope: list, parent: str, path: list[int]):
    data = { 'name': desc.name, 'number': desc.number }
    set_comments(data, path)
    scope.append(data)

#   ---------------------------------------------------------------------------
def walk_enum(desc: EnumDescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name

    value: list = []
    walk_list(desc.value, value, usr, path.copy(), walk_handle['enum_value'])

    data = { 'kind': 'ENUM', 'name': desc.name, 'value': value }
    set_comments(data, path)
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
    set_comments(data, path)
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
    set_comments(data, path)
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
    set_comments(data, path)
    IR.pool[usr] = data
    decl.append(usr)

#   ---------------------------------------------------------------------------
def walk_service(desc: ServiceDescriptorProto, decl: list, parent: str, path: list[int]):
    usr = parent + '.' + desc.name
    method: list = []
    walk_list(desc.method, method, usr, path.copy(), walk_handle['method'])
    data = { 'kind': 'SERVICE', 'name': desc.name, 'decl': method }
    set_comments(data, path)
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
#   -- TODO: save option type
    if not options:
        return {}

    return { desc.name: value for desc, value in options.ListFields() }

#   ---------------------------------------------------------------------------
def walk_file(proto_file: FileDescriptorProto, parent: str):
    info('Chopping "%s"', proto_file.name)

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
def chopping(request: plugin.CodeGeneratorRequest):
    global PROTO_FILE

    for proto_file in request.proto_file:
        PROTO_FILE = proto_file
        walk_file(proto_file, '')

    info('Saving "%s"', config.PATH / config.IR_FILE)
    with open(config.PATH / config.IR_FILE, 'w') as f:
        IR.dump(f)

#   -----------------------------------
#   Code generator
#   -----------------------------------

from importlib.util import spec_from_file_location, module_from_spec
import io
from contextlib import redirect_stdout

#   ---------------------------------------------------------------------------
def boiling(response: plugin.CodeGeneratorResponse):
    for item in config.TEMPLATE_LIST:
        if isinstance(item, str):
            templ_mask = item
            proto = None
        else:
            templ_mask, proto = item

        for templ in Path(config.PATH).glob(templ_mask):
            generated = response.file.add()
            if proto:
#               -- a .proto filename without extension with an inner extension of template
                generated.name = Path(proto).stem + Path(templ.stem).suffix
            else:
#               -- a template filename without outer extension
                generated.name = templ.stem
            info('Boiling "%s" to make "%s"', templ, generated.name)
            with io.StringIO() as buffer, redirect_stdout(buffer):
                spec = spec_from_file_location(generated.name, templ)
                if spec:
#                   -- add the template directory to `sys.path`` so you can import modules
                    parent = str(templ.parent.absolute())
                    if parent not in sys.path:
                        sys.path.append(parent)
#                   -- execute the template script
                    module = module_from_spec(spec)
                    sys.modules[generated.name] = module
                    spec.loader.exec_module(module)
                    module.boiling(config.PATH / config.IR_FILE, proto)
                    generated.content = buffer.getvalue()
                else:
                    error('Unable to import a template: "%s"', templ)

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
    info('Request parameters: %s', opt)
    info('Config: %s', config)

    chopping(request)
    boiling(response)

    info('Writing response')
    sys.stdout.buffer.write(response.SerializeToString())

#   ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()
