#!/usr/bin/env python3

from grpc_tools import protoc
from pathlib import Path

import argparse

def launcher(config_file, proto_dir, output_dir):
    proto_list = (str(proto) for proto in Path(proto_dir).rglob('*.proto'))
    protoc.main((
        '',
        f'-I={proto_dir}',
        f'--protoboiler_out=config={config_file}:{output_dir}',
        *proto_list
    ))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    parser.add_argument('proto_dir', type=str)
    parser.add_argument('output_dir', type=str)
    args = parser.parse_args()
    launcher(args.config_file, args.proto_dir, args.output_dir)
