# Requirements:

- make sure you reinstalled `requirements.txt`
- mongodb running on `localhost:27017`


# How to run locally

Set up two Golem nodes:


```sh
# First node listening on port 61000
python $GOLEM_DIR/golemapp.py --datadir=/home/$USER/datadir1 --password=node1 --accept-terms --rpc-address=localhost:61000
# Second node listening on port 61001
python $GOLEM_DIR/golemapp.py --datadir=/home/$USER/datadir2 --peer=localhost:40102 --rpc-address=localhost:61001
```


Prepare `task.json`: 

```json
{
  "name": "my_task",
  "workflow_path": "/home/user/golem/apps/fireworks/examples/workflows/basic.yaml",
  "resources": {
    "input_label_1": "/home/user/golem.log"
  },
  "type":"Fireworks",
  "timeout":"00:10:00",
  "subtask_timeout":"00:10:00",
  "estimated_memory": 2147483,
  "bid": 1,
  "subtasks_count": 1
}
```

| Key            | Description                                                     |
|----------------|-----------------------------------------------------------------|
| name           | Task name (user's choice)                                       |
| workflow_path  | Path to Workflow YAML description file                          |
| resources      | Key-value mapping file path to a label                          |
| subtasks_count | Number of tasks in Workflow (to be automated)                   |
| launchpad_path | Path to Launchpad YAML description file (optional)              |

After that run:

```sh
python $GOLEM_DIR/golemcli create task $GOLEM_DIR/apps/fireworks/examples/task.json`
```

Workflow `basic.yaml` will download specified resource file, count number of lines in it and then put it back to the database. 

Results will be available in local mongodb. Use script `workflows/get_basic_result.py` to retrieve the results. This depends on how firework `.yaml` labels result files, but the default in `workflows/basic.yaml` is just `result` (that is the identifier used by a script to retrieve result for this specific workflow, it's not generic). It can be difficult to investigate file content directly from mongodb as result files are compressed. 

# How it works

Files put into `resources` are uploaded to the Launchpad (default is `localhost:27017`) using `AddFilesTask` type of firework. Now the algorithm takes the given Workflow and starts looking for providers. Workflow is computed according to `links` specified in YAML description. Each provider found on the network is assigned a single Firework ID that is the next available Firework in the Workflow. This way each provider computes one Firework per subtask assigned. 

# Limitations

User can not utilize `_files_in` and `_files_out` to share files different machines (or different fireworks) because workers do not share any filesystem in golem. 

Each time user creates a task the launchpad (mongodb) and the filepad (files stored in mongodb) are wiped out. This has to do with labels duplication and will be fixed in the future.

Launching arbitrary code in provider's container is not secure (in this branch docker has been configured to allow internet access in the container).

# TODO

- Error handling (FIZZLED firework case, what to do when a firework has failed/timed out)
- Tests
