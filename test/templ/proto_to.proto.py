# -*- coding: f -*-

import sys
if len(sys.argv) != 2:
    print('ERROR: Required parameter (ir.json) is missing!', file=sys.stderr)
    sys.exit(2)

from logging import debug, info, warning, error
from protoboiler import IR
from pathlib import Path

ir = IR.open(sys.argv[1])

#   -----------------------------------
#   Proto file generation functionality
#   -----------------------------------

FIELD_LABEL = {
    'OPTIONAL': '',
    'REPEATED': 'repeated ',
    'REQUIRED': 'required ',
}

FIELD_TYPE = {
    'DOUBLE':   'double',
    'FLOAT':    'float',
    'INT64':    'int64',
    'UINT64':   'uint64',
    'INT32':    'int32',
    'FIXED64':  'fixed64',
    'FIXED32':  'fixed32',
    'BOOL':     'bool',
    'STRING':   'string',
    'GROUP':    'group',
    'MESSAGE':  'message',
    'BYTES':    'bytes',
    'UINT32':   'uint32',
    'ENUM':     'enum',
    'SFIXED32': 'sfixed32',
    'SFIXED64': 'sfixed64',
    'SINT32':   'sint32',
    'SINT64':   'sint64',
}

#   ---------------------------------------------------------------------------
def look_stream(stream: bool):
    return 'stream ' if stream else ''

#   ---------------------------------------------------------------------------
def look_label(label: str):
    return FIELD_LABEL.get(label, '')

#   ---------------------------------------------------------------------------
def look_type(field_type: str):
    return FIELD_TYPE.get(field_type, field_type)

#   ---------------------------------------------------------------------------
'''
Generate a generic option list.
'''
def option_list(options, sh = ''):
    for opt in options:
        f'''
option {opt} = "{options[opt]}";
''' > sh

#   ---------------------------------------------------------------------------
'''
Generate a leading comment.
'''
def leading_comment_of(node, sh = ''):
    if 'leading_comments' in node:
        comment = '//'.join(node['leading_comments'].splitlines(True)).rstrip()
        f'''
//{comment}
''' > sh

#   ---------------------------------------------------------------------------
'''
Generate a trailing comment.
'''
def trailing_comment_of(node):
    if 'trailing_comments' in node:
        comment = ' '.join(node['trailing_comments'].splitlines(True)).rstrip()
        f''' //{comment}
'''

#   ---------------------------------------------------------------------------
'''
Generate a service declaration list.
'''
def service_list(decl, sh = ''):
    for service in decl:
        leading_comment_of(service, sh)
        f'''
service {service['name']} {{
''' > sh
        trailing_comment_of(service)
        for method in IR.node_iter(service['decl']):
            f'''
    rpc {method['name']}({look_stream(method['client_streaming'])}{method['input']}) returns ({look_stream(method['server_streaming'])}{method['output']}) {{
''' > sh
            # -- method options
            option_list(method['options'], sh='    ')
            f'''
    }}
''' > sh
        f'''
}}

''' > sh

#   ---------------------------------------------------------------------------
'''
Generate a enum declaration list.
'''
def enum_list(decl, sh = ''):
    for enum in decl:
        leading_comment_of(enum, sh)
        f'''
enum {enum['name']} {{
''' > sh
        trailing_comment_of(enum)
        for value in enum['value']:
            leading_comment_of(value, sh)
            f'''
    {value['name']} = {value['number']};
''' > sh
            trailing_comment_of(value)
        f'''
}}

''' > sh

#   ---------------------------------------------------------------------------
'''
Generate a message field declaration list.
'''
def message_field_list(decl, sh = ''):
    for field in decl:
        leading_comment_of(field, sh)
        if field['type'] == 'ONEOF':
            f'''
oneof {field['name']} {{
''' > sh
            message_field_list(field['field'], sh + '    ')
            f'''
}}
''' > sh
        else:
            f'''
{look_label(field['label'])}{look_type(field['type'])} {field['name']} = {field['number']};
''' > sh
        trailing_comment_of(field)

#   ---------------------------------------------------------------------------
'''
Generate a message declaration list.
'''
def message_list(decl, sh = ''):
    for message in decl:
        leading_comment_of(message, sh)
        f'''
message {message['name']} {{
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
Generate a proto file.
'''
def proto_file(filename: str):
    for file in IR.node_iter(IR.decl, 'FILE', IR.if_field('name', filename)):
        f'''
syntax = "proto3";
'''
        option_list(file['options'])
        f'''
package {file['package']};
'''
        file_decl = file['decl']
        service_list(IR.node_iter(file_decl, 'SERVICE'))
        enum_list(IR.node_iter(file_decl, 'ENUM'))
        message_list(IR.node_iter(file_decl, 'MESSAGE'))

#   -----------------------------------
#   Code generation
#   -----------------------------------

# -- the template file
templ = Path(__file__)
# -- the proto file
proto = 'test.proto'

info('Generating code from a template: "%s"', templ.name)

f'''
// DO NOT EDIT, the file generated from "{templ.name}"

'''

proto_file(proto)
