from tabulate import tabulate

from golem.interface.command import doc, group, command, Argument, CommandHelper, CommandResult


@group(help="Task management commands")
class Tasks(object):

    client = None

    task_table_headers = ['name', 'id', 'status', '% completed']
    subtask_table_headers = ['node', 'id', 'time left', 'status', '% completed']

    id_req = Argument('id', help="Task identifier")
    id_opt = Argument.extend(id_req, optional=True)

    sort_task = Argument(
        '--sort',
        choices=['id', 'name', 'status', 'completion'],
        optional=True,
        help="Sort tasks"
    )

    @command(arguments=(id_opt, sort_task), help="Show task details")
    def show(self, id, sort):
        deferred = Tasks.client.get_tasks(id)
        task = CommandHelper.wait_for(deferred)

        return task

    @command(argument=id_opt, help="Show sub-tasks")
    def subtasks(self, id, sort):
        values = []

        deferred = Tasks.client.get_tasks(id)
        task = CommandHelper.wait_for(deferred)

        if task:
            subtasks = task.subtasks_given
            for subtask_id, subtask in subtasks.iteritems():
                values.append([
                    '-',
                    subtask_id,
                    '-',
                    subtask['status'],
                    '-'
                ])
            values = CommandResult.sort(Tasks.subtask_table_headers, values, sort)

        return CommandResult.to_tabular(Tasks.subtask_table_headers, values)

    @command(argument=id_req, help="Restart a task")
    def restart(self, id):
        deferred = Tasks.client.restart_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Abort a task")
    def abort(self, id):
        deferred = Tasks.client.abort_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Delete a task")
    def delete(self, id):
        deferred = Tasks.client.delete_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Pause a task")
    def pause(self, id):
        deferred = Tasks.client.pause_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Resume a task")
    def resume(self, id):
        deferred = Tasks.client.resume_task(id)
        return CommandHelper.wait_for(deferred)

    @doc("Show statistics for tasks")
    def stats(self):
        deferred = Tasks.client.get_task_stats()
        return CommandHelper.wait_for(deferred)
