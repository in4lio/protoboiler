# -*- coding: f -*-

'''
stub.swift.py

This template demonstrates the capability to generate Swift code directly
from a .proto file.
'''

from logging import debug, info, warning, error
from pathlib import Path
from protoboiler import IR

#   -----------------------------------
#   Boiling .swift from .proto
#   -----------------------------------

FIELD_TYPE = {
    'DOUBLE':   'Double',
    'FLOAT':    'Float',
    'INT64':    'Int64',
    'UINT64':   'UInt64',
    'INT32':    'Int32',
    'FIXED64':  'UInt64',
    'FIXED32':  'UInt32',
    'BOOL':     'Bool',
    'STRING':   'String',
    'BYTES':    'Data',
    'UINT32':   'UInt32',
    'SFIXED32': 'Int32',
    'SFIXED64': 'Int64',
    'SINT32':   'Int32',
    'SINT64':   'Int64',
}

#   ---------------------------------------------------------------------------
'''
Make an identifier:
'.package.top_decl.inner_decl' -> 'package_top_decl.inner_decl'
'''
def usr_to_id(usr: str) -> str:
    result = usr.removeprefix('.')
    for package, prefix in package_list:
        if result.startswith(package + '.'):
            result = prefix + '_' + result.removeprefix(package + '.')
            break

    return result

#   ---------------------------------------------------------------------------
def snake_to_lower_camel(name: str) -> str:
    head, *tail = name.split('_')
    return head.lower() + ''.join(x.title() for x in tail)

#   ---------------------------------------------------------------------------
def look_type(field):
    swift_type = FIELD_TYPE.get(field['type'], usr_to_id(field['type']))
    return f'[{swift_type}]' if field['label'] == 'REPEATED' else swift_type

#   ---------------------------------------------------------------------------
def look_input_type(node):
    input_type = usr_to_id(node['input'])
    if node['client_streaming']:
        return f'AsyncThrowingStream<{input_type}, Error>'
    else:
        return input_type

#   ---------------------------------------------------------------------------
def look_output_type(node):
    output_type = usr_to_id(node['output'])
    if node['server_streaming']:
        return f'-> AsyncThrowingStream<{output_type}, Error>'
    else:
        return f'async throws -> {output_type}'

#   ---------------------------------------------------------------------------
'''
The packages represented in the generated file and their corresponding
identifier prefixes: ('package.v1', 'Package_v1').
'''
package_list: list[str, str] = []

def create_package_list():
    global package_list

    for file, _ in IR.node_iter(IR.decl, 'FILE'):
        package_list.append((file['package'], file['package'].replace('.', '_').title()))

#   ---------------------------------------------------------------------------
'''
Boiling a leading comment.
'''
def leading_comment_of(node, sh = ''):
    if 'leading_comments' in node:
        comment = '//'.join(node['leading_comments'].splitlines(True)).rstrip()
        f'''
//{comment}
''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a trailing comment.
'''
def trailing_comment_of(node):
    if 'trailing_comments' in node:
        comment = ' '.join(node['trailing_comments'].splitlines(True)).rstrip()
        f''' //{comment}
'''

#   ---------------------------------------------------------------------------
'''
Boiling a enum declaration list.
'''
def enum_list(decl, sh = ''):
    for enum, usr in decl:
        name = usr_to_id(usr).rpartition('.')[2]
        leading_comment_of(enum, sh)
        f'''
public enum {name}: Int {{
''' > sh
        trailing_comment_of(enum)
        for value in enum['value']:
            leading_comment_of(value, sh + '    ')
            f'''
    case {snake_to_lower_camel(value['name'])} = {value['number']}
''' > sh
            trailing_comment_of(value)
        f'''
}}

''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a message field declaration list.
'''
def message_field_list(decl, sh = ''):
    for field in decl:
        leading_comment_of(field, sh)
        if field['type'] == 'ONEOF':
            message_field_list(field['field'], sh)
        else:
            f'''
var {field['name']}: {look_type(field)}{'?' if field['proto3_optional'] else ''}
''' > sh
        trailing_comment_of(field)

#   ---------------------------------------------------------------------------
'''
Boiling a message declaration list.
'''
def message_list(decl, sh = ''):
    for message, usr in decl:
        name = usr_to_id(usr).rpartition('.')[2]
        leading_comment_of(message, sh)
        f'''
public struct {name} {{
''' > sh
        trailing_comment_of(message)
        enum_list(IR.node_iter(message['decl'], 'ENUM'), sh + '    ')
        message_list(IR.node_iter(message['decl'], 'MESSAGE'), sh + '    ')
        message_field_list(message['field'], sh + '    ')
        f'''
}}

''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a service declaration list.
'''
def service_list(decl, sh = ''):
    for service, usr in decl:
        name = usr_to_id(usr).rpartition('.')[2]
        leading_comment_of(service, sh)
        f'''
protocol {name} {{
''' > sh
        trailing_comment_of(service)
        for method, _ in IR.node_iter(service['decl']):
            f'''
    func {method['name']}(request: {look_input_type(method)}) {look_output_type(method)}
''' > sh
        f'''
}}

''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a .proto file.
'''
def proto_file(node, usr):
    f'''
//
// {node['package']}
//

'''
    file_decl = node['decl']
    enum_list(IR.node_iter(file_decl, 'ENUM'))
    message_list(IR.node_iter(file_decl, 'MESSAGE'))
    service_list(IR.node_iter(file_decl, 'SERVICE'))

#   -----------------------------------
#   Code generation
#   -----------------------------------

def boiling(json_filename: str, _):
    IR.open(json_filename)

    templ = Path(__file__)
    info('Generating code using "%s"', templ.name)

    create_package_list()

    f'''
// DO NOT EDIT.
// swift-format-ignore-file
//
// Generated by the protoboiler plugin for the protocol buffer compiler.
// Source: {templ.name}

'''
    for file, usr in IR.node_iter(IR.decl, 'FILE'):
        proto_file(file, usr)
