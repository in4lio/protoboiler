#!/bin/bash

proj="${1:-test}"

source ./venv/bin/activate

protoc -I$proj/proto --protoboiler_out=templ=$proj/templ:$proj/build \
--plugin=protoc-gen-protoboiler=protoboiler.py $projproto/$proj.proto

deactivate
