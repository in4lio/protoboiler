# -*- coding: f -*-

import sys
if len(sys.argv) != 2:
    print('ERROR: Required parameter (ir.json) is missing!', file=sys.stderr)
    sys.exit(2)

from logging import debug, info, warning, error
from protoboiler import IR

ir = IR.open(sys.argv[1])

#   -----------------------------------
#   Code generation
#   -----------------------------------

info('Generate code from template: %s', __file__)

f'''
// Hello world!

'''
