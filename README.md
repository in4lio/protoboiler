# Proto Boiler Plugin

Protocol Buffers compiler plugin allows you quickly generate boilerplate code
from your Google Protocol Buffer (proto) definitions using template scripts on
Python.

The plugin creates a JSON file with intermediate representation (IR) of your
proto definitions and then runs template scripts on Python to generate code.


## Intermediate representation (IR)

The plugin provides methods to easily navigate through specific proto
definitions in the intermediate representation. For example, to iterate through
all services, you can write the following:

```python
# for each .proto file
for file, _ in IR.node_iter(IR.decl, 'FILE'):
    # for each service
    for service, _ in IR.node_iter(file['decl'], 'SERVICE'):
        print('service:', service['name'])
        # for each method
        for method, _ in IR.node_iter(service['decl']):
            print('  method:', method['name'])
            print('    input:', method['input'])
            print('      streaming:', method['client_streaming'])
            print('    output:', method['output'])
            print('      streaming:', method['server_streaming'])
```


## Template script on Python

The script should implement the function that takes an IR filename and
optional a .proto file name parameters:

```python
def boiling(json_filename: str, proto_filename: str | None)
```

The plugin calls the `boiling()` function to generate code. The `json_filename`
file contains an intermediate representation of all processed .proto files.
The additional parameter `proto_filename` can be used to filter the data and
generate code only for the file specified in the `TEMPLATE_LIST` parameter
of the configuration file.

The script should output the result code into the `stdout` stream, for that
[`f-codec`](https://github.com/in4lio/f-codec), that wraps lonesome f-strings
in `print()` can be used. Or you can involve any other output method, such as
the standard `print()` function.

Example templates for generating .cpp, .swift and .proto source code can be
found in ["sample/templ/"](sample/templ/).

You can test code generation using the ["sample/"](sample/) templates and
proto files by running:

```shell
./boiling-sample.sh
```


## Configuration file

A configuration file (in Python) can contain the following parameters:

- `LOGGING_FILE`: a filename for logging, `str`
- `LOGGING_LEVEL`: a logging level, `int`
- `TEMPLATE_LIST`: a list of template files, with optionally specifying
  a .proto file, `list[templ | tuple[templ, proto]]`
    - `templ`: a file mask, like "*.*.py"
    - `proto`: a name of the specific .proto file that will be provided to
      the template's `boiling()` function.
- `IR_FILE`: a filename for saving IR, `str`

Custom configuration parameters must be prefixed with `MY_`.

## How to install the package

```shell
python3 -m venv ./venv

source ./venv/bin/activate

python3 -m pip install protoboiler

deactivate
```


## How to use the plugin

To generate code, invoke `protoc` and provide a configuration file (optional)
to the plugin using the `protoboiler_out` parameter:

```shell
source ./venv/bin/activate

protoc -I$proto_dir --protoboiler_out=config=$config_file:$output_dir $proto_dir/*.proto

deactivate
```


## Getting started

Given you have a proto file "logging.proto":

```protobuf
syntax = "proto3";

package logging;

enum Level {
  NOTSET = 0;
  DEBUG = 10;
  INFO = 20;
  WARNING = 30;
  ERROR = 40;
  CRITICAL = 50;
}
```
and a template file "logging.cpp.py" that use [`f-codec`](https://github.com/in4lio/f-codec)
to output the generated code into `stdout`:

```python
# -*- coding: f -*-

from protoboiler import IR

def boiling(json_filename: str, _):
    IR.open(json_filename)

    f'''
// Generated file.
'''
    for file, _ in IR.node_iter(IR.decl, 'FILE'):
        for enum, _ in IR.node_iter(file['decl'], 'ENUM'):
            f'''
enum class {enum['name']} {{
'''
            for value in enum['value']:
                f'''
    {value['name']} = {value['number']},
'''
            f'''
}};

'''
```

Running the following command:

```shell
protoc -I. --protoboiler_out=. ./logging.proto
```
you will generate "logging.cpp":

```c++
// Generated file.
enum class Level {
    NOTSET = 0,
    DEBUG = 10,
    INFO = 20,
    WARNING = 30,
    ERROR = 40,
    CRITICAL = 50,
};
```


## Development

Given that you have cloned this repository and installed `poetry`, you can
install the plugin dependencies:

```shell
cd protoboiler/

poetry install
```

Now you are ready to run the plugin without installing the package.
The `launcher` script is included in the repository for your convenience:

```shell
poetry run ./launcher $config_file $proto_dir $output_dir
```
