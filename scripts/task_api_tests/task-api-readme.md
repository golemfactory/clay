# Running a task on Task-Api

Task-API has been enabled on testnet since the 0.22.0 release.
For this first release there is no GUI implementation yet, so this guide will use the CLI only.
When you create a task with CLI it will not show up in GUI

## Short summary:

- Create new task-api JSON file
- Run the file using the cli

## Prepare a JSON

Here is an example of a new task-api JSON file.

```JSON
{
    "golem": {
        "app_id": "daec55c08c9de7b71bf4ec3eb759c83b",
        "name": "",
        "resources": ["/absolute/path/to/resources/file.blend"],
        "max_price_per_hour": "1_000_000_000_000_000_000",
        "max_subtasks": 1,
        "task_timeout": 600,
        "subtask_timeout": 590,
        "output_directory": "/absolute/path/to/output/"
    },
    "app": {
        "resources": ["file.blend"],
        "resolution": [320, 240],
        "frames": "1",
        "format": "PNG",
        "compositing": "False"
    }
}
```
### golem

The golem block of the JSON is meant for the input Golem needs, these are the same for all apps
```
...
    "golem": {
        "app_id": "daec55c08c9de7b71bf4ec3eb759c83b",
        "name": "",
        "resources": ["/absolute/path/to/resources/file.blend"],
        "max_price_per_hour": "1_000_000_000_000_000_000",
        "max_subtasks": 1,
        "task_timeout": 600,
        "subtask_timeout": 590,
        "output_directory": "/absolute/path/to/output/"
    },
...
```

#### golem.app_id

App id is the unique identifier of the app including its version.
You can get the build in app_id's with the command `golemcli ...` (TBD)
`daec55c08c9de7b71bf4ec3eb759c83b` is `golemfactory/blenderapp:0.7.2` the only available option at the time.

#### golem.name

Name of the task in the GUI, not related to task-api. Allowed to be empty. Will not be used in this first release, GUI does not show tasks

#### golem.resources

List of absolute paths to the files required for running this task

#### golem.max_price_per_hour

Max price to pay for the computation per hour, always passed as string ( in "").
The golem token has 18 digits, so for 1 GNT add 18 zero's.

#### golem.max_subtasks

Amount of subtasks to split the task into.

#### golem.task_timeout

Task timeout in seconds, 600 is 10 minutes.

#### golem.subtask_timeout

Subtask timeout in seconds, 600 is 10 minutes.

### app

The app block contains app specific input parameters, these are different per app.
TODO: Move this to app specific readme.md

```
...
    "app": {
        "resources": ["file.blend"],
        "resolution": [320, 240],
        "frames": "1",
        "format": "PNG",
        "compositing": "False"
    }
...
```

#### app.resources

A relative list of the resources, currently only one level.
TO FIX: allow folders and generate the list by default based on golem.resources

#### app.resolution

Resolution of the blender render in pixels

#### app.frames

Frames to select during the blender render

#### app.format

Output format for the blender render ( PNG, JPEG or EXR )

#### app.compositing

Use compositing for the blender render?

## Run a task-api task

To run a task-api task you use the same command as the old ones.

```
golemcli tasks create ./task_api_json_file.json
```

Then you can use `golemcli tasks show` to list the task
We also implemented `golemcli tasks abort`, `.. delete` and `.. restart_subtask`
Other commands are not supported yet, they will be added soon

To help debug the task-api computation there are extra logs stored in your `logs/app_name/` folder.
Please provide the generated logs next to the regular logs when creating issues.
