#!/bin/bash

config_file="sample/sample.config"
proto_dir="sample/proto"
output_dir="sample/generated"

poetry run ./launcher $config_file $proto_dir $output_dir
