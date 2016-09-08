from golem.interface.command import doc, group, identifier


@group(help="Task management commands")
class Tasks(object):

    client = None

    @doc("Show task details")
    @identifier('task_id', optional=True)
    def show(self, task_id):
        return Tasks.client.get_tasks(task_id)

    @doc("Restart task")
    @identifier('task_id')
    def restart(self, task_id):
        return Tasks.client.restart_task(task_id)

    @doc("Abort task")
    @identifier('task_id')
    def abort(self, task_id):
        return Tasks.client.abort_task(task_id)

    @doc("Delete task")
    @identifier('task_id', deletes=True)
    def delete(self, task_id):
        return Tasks.client.delete_task(task_id)

    @doc("Pause task")
    @identifier('task_id')
    def pause(self, task_id):
        return Tasks.client.pause_task(task_id)

    @doc("Resume task")
    @identifier('task_id')
    def resume(self, task_id):
        return Tasks.client.resume_task(task_id)
