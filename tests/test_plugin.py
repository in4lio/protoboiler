'''
Tests of the protoboiler plugin.

The plugin is executed the same way `protoc` does it: as a subprocess reading
a serialized CodeGeneratorRequest from stdin and writing a CodeGeneratorResponse
to stdout. The request is built from a descriptor set compiled with the
`protoc` bundled into `grpc_tools`, so no system `protoc` is required.

The golden test runs the "sample/" code generation and compares the results
with the reference files in "tests/golden/". To regenerate the reference files
after an intended change, run:

    UPDATE_GOLDENS=1 pytest
'''

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from grpc_tools import protoc as grpc_protoc

# mypy: disable-error-code="import-untyped"
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.compiler import plugin_pb2 as plugin

ROOT = Path(__file__).parent.parent
SAMPLE = ROOT / 'sample'
GOLDEN = Path(__file__).parent / 'golden'
UPDATE_GOLDENS = os.environ.get('UPDATE_GOLDENS') == '1'

#   ---------------------------------------------------------------------------
def compile_descriptor_set(proto_dir: Path, tmp_path: Path) -> FileDescriptorSet:
    out = tmp_path / 'descriptor_set.pb'
    proto_list = sorted(str(proto) for proto in proto_dir.rglob('*.proto'))
    code = grpc_protoc.main([
        'protoc',
        f'-I{proto_dir}',
        f'--descriptor_set_out={out}',
        '--include_source_info',
        '--include_imports',
        *proto_list,
    ])
    assert code == 0, f'protoc failed on {proto_list}'
    return FileDescriptorSet.FromString(out.read_bytes())

#   ---------------------------------------------------------------------------
def run_plugin(proto_dir: Path, config_file: Path, tmp_path: Path
, parameter: str = '') -> plugin.CodeGeneratorResponse:
    descriptor_set = compile_descriptor_set(proto_dir, tmp_path)
    request = plugin.CodeGeneratorRequest()
    request.proto_file.extend(descriptor_set.file)
    request.file_to_generate.extend(file.name for file in descriptor_set.file)
    request.parameter = f'config={config_file}' + (f',{parameter}' if parameter else '')

    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run(
        [sys.executable, '-c', 'from protoboiler import main; main()'],
        input=request.SerializeToString(), capture_output=True, env=env, check=True,
    )
    return plugin.CodeGeneratorResponse.FromString(result.stdout)

#   ---------------------------------------------------------------------------
def load_ir(config_dir: Path, ir_file: str) -> dict:
    with open(config_dir / ir_file, encoding='utf-8') as f:
        return json.load(f)

#   -----------------------------------
#   Golden test on "sample/"
#   -----------------------------------

def test_sample_golden(tmp_path):
    work = tmp_path / 'work'
    shutil.copytree(SAMPLE / 'templ', work / 'templ', ignore=shutil.ignore_patterns('__pycache__'))
    (work / 'build').mkdir()
    config_file = work / 'sample.config'
    config_file.write_text((SAMPLE / 'sample.config').read_text())

#   -- `my_opt` is accessed by "sample/sample.config"
    response = run_plugin(SAMPLE / 'proto', config_file, tmp_path, 'my_opt=hello')
    assert not response.error

    generated = { file.name: file.content for file in response.file }
#   -- the IR is compared without the "config" section, its paths depend on `tmp_path`
    ir = load_ir(work, 'build/sample_ir.json')
    generated['sample_ir.json'] = json.dumps(
        { 'pool': ir['pool'], 'decl': ir['decl'] }, indent=4) + '\n'

    if UPDATE_GOLDENS:
        shutil.rmtree(GOLDEN, ignore_errors=True)
        GOLDEN.mkdir()
        for name, content in generated.items():
            (GOLDEN / name).write_text(content)

    assert set(generated) == { golden.name for golden in GOLDEN.iterdir() }
    for name, content in generated.items():
        assert content == (GOLDEN / name).read_text(), f'"{name}" differs from the golden file'

#   -----------------------------------
#   Regression tests
#   -----------------------------------

LIST_FILES_TEMPL = '''
from protoboiler import IR

def boiling(json_filename, proto_filename):
    IR.open(json_filename)
    for node, usr in IR.node_iter(IR.decl, 'FILE'):
        print(usr, node['name'], *IR.usr_iter(node['decl']))
'''

#   ---------------------------------------------------------------------------
def make_config(work: Path, template_list: str) -> Path:
    config_file = work / 'test.config'
    config_file.write_text(
        f'TEMPLATE_LIST = {template_list}\n'
        "IR_FILE = 'ir.json'\n"
        "LOGGING_FILE = 'test.log'\n"
    )
    return config_file

#   ---------------------------------------------------------------------------
'''
Files of the same package must not collide in the IR.
'''
def test_same_package_files(tmp_path):
    proto_dir = tmp_path / 'proto'
    proto_dir.mkdir()
    (proto_dir / 'a.proto').write_text(
        'syntax = "proto3";\npackage common;\nmessage Alpha { int32 x = 1; }\n')
    (proto_dir / 'b.proto').write_text(
        'syntax = "proto3";\npackage common;\nimport "a.proto";\n'
        'message Beta { common.Alpha a = 1; }\n')
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'list.txt.py').write_text(LIST_FILES_TEMPL)

    response = run_plugin(proto_dir, make_config(work, "('list.txt.py', )"), tmp_path)
    assert not response.error

    ir = load_ir(work, 'ir.json')
    assert ir['decl'] == ['.a.proto', '.b.proto']
    assert ir['pool']['.a.proto']['decl'] == ['.common.Alpha']
    assert ir['pool']['.b.proto']['decl'] == ['.common.Beta']
#   -- a type reference resolves to the declaration USR
    assert ir['pool']['.common.Beta']['field'][0]['type'] == '.common.Alpha'
    assert response.file[0].content == (
        '.a.proto a.proto .common.Alpha\n'
        '.b.proto b.proto .common.Beta\n'
    )

#   ---------------------------------------------------------------------------
'''
Type references of a file without a package must resolve in the IR.
'''
def test_file_without_package(tmp_path):
    proto_dir = tmp_path / 'proto'
    proto_dir.mkdir()
    (proto_dir / 'nopkg.proto').write_text(
        'syntax = "proto3";\n'
        'message Solo { Inner i = 1; }\nmessage Inner { int32 x = 1; }\n')
    work = tmp_path / 'work'
    work.mkdir()

    response = run_plugin(proto_dir, make_config(work, '()'), tmp_path)
    assert not response.error

    ir = load_ir(work, 'ir.json')
    assert ir['decl'] == ['.nopkg.proto']
    assert ir['pool']['.Solo']['field'][0]['type'] == '.Inner'
    assert '.Inner' in ir['pool']

#   ---------------------------------------------------------------------------
'''
A failing template must be reported via `response.error`.
'''
def test_template_error(tmp_path):
    proto_dir = tmp_path / 'proto'
    proto_dir.mkdir()
    (proto_dir / 'a.proto').write_text('syntax = "proto3";\npackage common;\n')
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'broken.txt.py').write_text(
        'def boiling(json_filename, proto_filename):\n'
        "    raise RuntimeError('boom from template')\n")

    response = run_plugin(proto_dir, make_config(work, "('broken.txt.py', )"), tmp_path)
    assert 'boom from template' in response.error
    assert not response.file
