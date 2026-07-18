# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`protoboiler` is a Protocol Buffers compiler (`protoc`) plugin that generates boilerplate code from .proto definitions using user-written Python template scripts. All plugin logic lives in a single module: `protoboiler/__init__.py`, exposed as the `protoc-gen-protoboiler` console script (entry point: `main`).

## Commands

```shell
uv sync                          # install dependencies (Python >=3.11)

uv run pytest                    # run the test suite
uv run pytest -k golden          # run a single test by name
UPDATE_GOLDENS=1 uv run pytest   # regenerate tests/golden/ after an intended change

uv run mypy protoboiler tests    # type check (must stay clean, CI enforces it)

./boiling-sample.sh              # regenerate sample/generated/ from sample/proto/
```

The golden test (`tests/test_plugin.py`) runs the plugin as a subprocess on `sample/` and compares the outputs and the IR with `tests/golden/`. It uses the `protoc` bundled into `grpcio-tools` (dev dependency), so no system `protoc` is needed. After any deliberate change to generated output or the IR format, rerun with `UPDATE_GOLDENS=1` and commit the golden diff.

Note: `sample/generated/` and `sample/build/` are NOT tracked by git (their `.gitignore` files contain `*`); the tracked reference outputs live in `tests/golden/`.

Two launchers exist: `launcher` (bash, invokes system `protoc` with `--protoboiler_out=config=<file>:<dir>`) and `launcher.py` (Python, uses `grpc_tools.protoc`); `boiling-sample.sh` uses `launcher.py`.

CI (`.github/workflows/ci.yml`) runs mypy and pytest on Python 3.11–3.14.

## Architecture

The plugin runs as a protoc pipeline in two phases (`main()` in `protoboiler/__init__.py`):

1. **Chopping** (`chopping()`): reads a `CodeGeneratorRequest` from stdin, walks each proto file's descriptors (`walk_file` → `walk_handle` dispatch table → `walk_enum`/`walk_message`/`walk_service`/`walk_method` and leaf `get_*` functions) and builds an intermediate representation (IR). Source comments are attached via `SourceCodeInfo` path lookup. The IR plus the config is serialized to a JSON file (`IR_FILE`).

2. **Boiling** (`boiling()`): for each entry in the config's `TEMPLATE_LIST`, imports the template script as a module, redirects its stdout into a buffer, and calls its `boiling(json_filename, proto_filename)` function. The captured stdout becomes the generated file's content in the `CodeGeneratorResponse`.

### IR structure

The IR JSON has three keys: `pool` (a dict mapping USRs — dotted qualified names like `.package.Message.Field` — to declaration nodes with a `kind` of FILE/ENUM/MESSAGE/SERVICE/METHOD), `decl` (top-level USR list), and `config`. Template scripts consume it through the `IR` class (`IR.open`, `IR.node_iter`/`IR.usr_iter` with kind filters, `IR.lookup`).

### Config files

Config files are Python scripts exec'd by `Config.from_file`; only keys present in `CONFIG_POOL` (`LOGGING_FILE`, `LOGGING_LEVEL`, `TEMPLATE_LIST`, `IR_FILE`) or prefixed with `MY_` are kept. All relative paths in the config resolve against the config file's directory (`PATH`).

### Template scripts

Templates (see `sample/templ/`) use the `f-codec` codec (`# -*- coding: f -*-` header) which wraps bare f-string literals in `print()`, so templates read as inline code generation. Naming convention: `<name>.<ext>.py` produces `<name>.<ext>`; when a template is paired with a specific proto file in `TEMPLATE_LIST`, the output is `<proto stem>.<ext>`.
