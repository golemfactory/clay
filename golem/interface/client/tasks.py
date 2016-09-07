from golem.interface.command import doc, group, identifier, CommandGroup


@group(help="Task management commands")
class Tasks(CommandGroup):

    @doc("Show task details")
    @identifier('task_id', optional=True)
    def show(self, task_id):
        pass
        # if not task_id:
        #     return self.client.get_tasks()
        # return self.client.get_task(task_id)

    @doc("Restart task")
    @identifier('task_id')
    def restart(self, task_id):
        return self.client.restart_task(task_id)

    @doc("Abort task")
    @identifier('task_id')
    def abort(self, task_id):
        return self.client.abort_task(task_id)

    @doc("Delete task")
    @identifier('task_id', deletes=True)
    def delete(self, task_id):
        return self.client.delete_task(task_id)

    @doc("Pause task")
    @identifier('task_id')
    def pause(self, task_id):
        return self.client.pause_task(task_id)

    @doc("Resume task")
    @identifier('task_id')
    def resume(self, task_id):
        return self.client.resume_task(task_id)
