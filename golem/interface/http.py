# For future use

# Differences in API vs CLI:
#
# - id positioning
#       tasks show deadbeef -> GET /tasks/deadbeef
# - identifier modifiers, e.g.
#       tasks delete deadbeef -> DELETE /tasks/deadbeef
#       tasks pause deadbeef -> POST /tasks/deadbeef/pause
# - for file names: content (POST data) as argument
