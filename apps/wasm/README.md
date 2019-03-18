WebAssembly Task
================

The WebAssembly task is capable of running arbitrary code compiled to
WebAssembly+JS on Golem. Under the hood, the task uses the proprietary
[WebAssembly Sandbox](https://github.com/golemfactory/sp-wasm).

## Task preparation

The following section describes steps necessary to prepare and create a WASM
task on Golem.

### Program compilation

First, you have to compile the code you want to run to WebAssembly+JavaScript.
Currently only programs compiled by *Emscripten* are supported. This is the most
popular WebAssembly compiler at the moment. Compiling C and C++ is pretty straightforward.
Rust is also possible because the Rust->WebAssembly compiler uses *Emscripten* internally,
but it might require some tweaking to set the flags mentioned below.

**IMPORTANT**: The following flags **have** to be used while compiling via
*Emscripten* (*emcc*):

* `-s BINARYEN_ASYNC_COMPILATION=0`
* `-s MEMFS_APPEND_TO_TYPED_ARRAYS=1`

If the program uses any substantial amount of memory, the following flags may also be useful:

* `-s ALLOW_MEMORY_GROWTH=1` 
* `-s TOTAL_MEMORY=1073741824` (or another number, though there are restrictions)

At the end, *emcc* produces two files - a JavaScript file and a WebAssembly file.

### Subtask division

The task is manually divided into subtasks. Each subtask runs the same program,
but gets (possibly) different input and execution arguments,
and produces (possibly) different output.

### Input/output

The compiled programs have to read their input from files and write their
output to files.

A directory has to be created for the program and its input. The JavaScript and WebAssembly
files produced by *Emscripten* have to be placed directly inside this directory. Then, 
for each subtask, a subdirectory named the same as the subtask has to be created inside the
input directory. Everything the program has to access for a particular subtask has
to be placed inside its input subdirectory.

Another directory has to be created for program output. The output files specified
in `output_file_paths` for each subtask will be copied to a subdirectory named the
same as the subtask inside the output directory.

The final (example) directory structure should look like this:
```
.
|-- input_dir
|   |-- program.js
|   |-- program.wasm
|   |-- subtask_a
|   |   |-- input_file_a_1
|   |   `-- input_file_a_2
|   `-- subtask_b
|       |-- input_file_b_1
|       `-- input_file_b_2
`-- output_dir
    |-- subtask_a
    |   |-- output_file_a_1
    |   `-- output_file_a_2
    `-- subtask_b
        |-- output_file_b_1
        `-- output_file_b_2
```

### Task JSON

To create the task, its JSON definition has to be created. The non-task-specific
fields that **have** to be present are:

* `type`: has to be `wasm`
* `name`
* `bid`
* `timeout`
* `subtask_timeout`
* `options`: defined below

#### Task options

The following options have to be specified for the WebAssembly task:

* `js_name`: The name of the JavaScript file produced by *Emscripten*. The file
should be inside the input directory (specified below).
* `wasm_name`: The name of the WebAssembly file produced by *Emscripten*. The 
file should be inside the input directory (specified below).
* `input_dir`: The path to the input directory containing the JavaScript and
WebAssembly program files and the input subdirectories for each subtask. For each
subtask, its input subdirectory will be mapped to `/` (which is also the *CWD*) inside
the program's virtual filesystem.
* `output_dir`: The path to the output directory where for each subtask, the output
files specified in `output_file_paths` will be copied to a subdirectory named the 
same as the subtask.
* `subtasks`: A dictionary containing the options for each subtask. The keys should
be the subtask names, the values should be dictionaries with fields specified below:
  * `exec_args`: The execution arguments that will be passed to the program for this
  subtask.
  * `output_file_paths`: The paths to the files the program is expected to produce
  for this subtask. Each file specified here will be copied from the program's
  virtual filesystem to the output subdirectory for this subtask. If any of the
  files are missing, the subtask will fail.
  
#### Example

An example WASM task JSON:
```json
{
    "type": "wasm", 
    "name": "wasm", 
    "bid":  1,
    "subtask_timeout": "00:10:00",
    "timeout": "00:10:00",
    "options": {
        "js_name": "test.js",
        "wasm_name": "test.wasm",
        "input_dir": "/home/user/test_in",
        "output_dir": "/home/user/test_out",
        "subtasks": {
            "subtask1": {
                "exec_args": ["arg1", "arg2"],
                "output_file_paths": ["out.txt"]
            },
            "subtask2": {
                "exec_args": ["arg3", "arg4"],
                "output_file_paths": ["out.txt"]
            }
        }
    }
}
```

### Creating the task
To create the task, run the following:
```bash
golemcli tasks create path/to/the/task_definition.json
```

## Further reading / problems / debugging

In case of any errors and need of debugging, it could be beneficial to debug the
internal sandbox directly. The project lives
[here](https://github.com/golemfactory/sp-wasm/). It has documentation and examples
that might also be useful while compiling programs via *Emscripten*.
