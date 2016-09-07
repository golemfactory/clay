# keep in mind:
# - content (POST data), not filename, as argument
# - id positioning
#       tasks show deadbeef -> GET /tasks/deadbeef
# - identifier modifiers, e.g.
#       tasks delete deadbeef -> DELETE /tasks/deadbeef
#       tasks pause deadbeef -> POST /tasks/deadbeef/pause
