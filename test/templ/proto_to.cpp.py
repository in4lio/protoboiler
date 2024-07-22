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
#   Code generation
#   -----------------------------------

# -- the template file
templ = Path(__file__)
# -- the name of the correspondent proto-file
proto = templ.with_suffix('').with_suffix('').stem + '.proto'

info('Generating code from a template: "%s"', templ.name)

f'''
// Hello world!

'''

for file_node in IR.node_iter(IR.decl, 'FILE', IR.if_field('name', proto)):
    file_decl = file_node['decl']
    f'''
    File: {file_node['name']}
'''
    for usr in IR.usr_iter(file_decl, 'ENUM'):
        node = IR.lookup(usr)
        f'''
        Enum: {node['name']}
'''
    for node in IR.node_iter(file_decl, 'MESSAGE'):
        f'''
        Message: {node['name']}
'''
    for node in IR.node_iter(file_decl, 'SERVICE'):
        f'''
        Service: {node['name']}
'''
