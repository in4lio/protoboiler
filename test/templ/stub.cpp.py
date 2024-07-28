# -*- coding: f -*-

'''
stub.cpp.py

This template demonstrates the capability to generate C++ code directly
from a .proto file.
'''

from logging import debug, info, warning, error
from protoboiler import IR
from pathlib import Path

#   -----------------------------------
#   Boiling .cpp from .proto
#   -----------------------------------

FIELD_TYPE = {
    'DOUBLE':   'double',
    'FLOAT':    'float',
    'INT64':    'int64_t',
    'UINT64':   'uint64_t',
    'INT32':    'int32_t',
    'FIXED64':  'uint64_t',
    'FIXED32':  'uint32_t',
    'BOOL':     'bool',
    'STRING':   'std::string',
    'BYTES':    'string',
    'UINT32':   'uint32_t',
    'SFIXED32': 'int32_t',
    'SFIXED64': 'int64_t',
    'SINT32':   'int32_t',
    'SINT64':   'int64_t',
}

#   ---------------------------------------------------------------------------
def usr_to_id(usr: str) -> str:
    return usr.replace('.', '::')

#   ---------------------------------------------------------------------------
def look_type(field):
    cpp_type = FIELD_TYPE.get(field['type'], usr_to_id(field['type']))
    return f'Repeated<{cpp_type}>*' if field['label'] == 'REPEATED' else cpp_type

#   ---------------------------------------------------------------------------
def look_input_type(node):
    input_type = usr_to_id(node['input'])
    if node['client_streaming']:
        return f'StreamReader<{input_type}>*'
    else:
        return f'const {input_type}*'

#   ---------------------------------------------------------------------------
def look_output_type(node):
    output_type = usr_to_id(node['output'])
    if node['server_streaming']:
        return f'StreamWriter<{output_type}>*'
    else:
        return f'{output_type}*'

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
    for enum in decl:
        leading_comment_of(enum, sh)
        f'''
enum class {enum['name']} {{
''' > sh
        trailing_comment_of(enum)
        for value in enum['value']:
            leading_comment_of(value, sh)
            f'''
    {value['name']} = {value['number']},
''' > sh
            trailing_comment_of(value)
        f'''
}};

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
{look_type(field)} {field['name']};
''' > sh
        trailing_comment_of(field)

#   ---------------------------------------------------------------------------
'''
Boiling a message declaration list.
'''
def message_list(decl, sh = ''):
    for message in decl:
        leading_comment_of(message, sh)
        f'''
struct {message['name']} {{
''' > sh
        trailing_comment_of(message)
        enum_list(IR.node_iter(message['decl'], 'ENUM'), sh + '    ')
        message_list(IR.node_iter(message['decl'], 'MESSAGE'), sh + '    ')
        message_field_list(message['field'], sh + '    ')
        f'''
}};

''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a service declaration list.
'''
def service_list(decl, sh = ''):
    for service in decl:
        leading_comment_of(service, sh)
        f'''
class {service['name']} {{
''' > sh
        trailing_comment_of(service)
        for method in IR.node_iter(service['decl']):
            f'''
    void {method['name']}({look_input_type(method)} input, {look_output_type(method)} output);
''' > sh
        f'''
}};

''' > sh

#   ---------------------------------------------------------------------------
'''
Boiling a .proto file.
'''
def proto_file(node):
    namespace = usr_to_id(node['package'])
    f'''
namespace {namespace} {{
'''
    file_decl = node['decl']
    enum_list(IR.node_iter(file_decl, 'ENUM'), '    ')
    message_list(IR.node_iter(file_decl, 'MESSAGE'), '    ')
    service_list(IR.node_iter(file_decl, 'SERVICE'), '    ')
    f'''
}} // {namespace}

'''

#   -----------------------------------
#   Code generation
#   -----------------------------------

def boiling(json_filename: str, _):
    IR.open(json_filename)

    templ = Path(__file__)
    info('Generating code using "%s"', templ.name)

    f'''
// DO NOT EDIT, the file generated from "{templ.name}"

#include <cstdint>
#include <string>

template <class T>
class Repeated {{
}};

template <class T>
class StreamWriter {{
}};

template <class T>
class StreamReader {{
}};

'''
    for file in IR.node_iter(IR.decl, 'FILE'):
        proto_file(file)
