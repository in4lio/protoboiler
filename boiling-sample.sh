#!/bin/bash

config_file="sample/sample.config"
proto_dir="sample/proto"
output_dir="sample/generated"

uv run python3 launcher.py $config_file $proto_dir $output_dir
