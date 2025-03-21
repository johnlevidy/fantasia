## TODO / Hygiene

function renaming around  compute_dag_metrics, etc.. 
enforce sentinel / milestones have 0 estimatse
Maybe we need something like "problematic node" or some way to indicate there's a notification for a particular node
factor out start / end sanity checking

Store dates internally in "business day" space to avoid all these calls to busday functions; convert back to calendar
dates after all the work is done.

Support vacation schedules using tasks to model time off; if the scheduler finds out that somebody's been allocated
to a task as well as a vacation task we can flag that directly.

## Notification Features
6. Filtering on the type of the notification
7. Item that's started when prereq isn't done?

## UI Features
1. Indicate in some way an item hasn't started yet but should have ( add notification for this as well )
5. Clearly indicate which items are complete ( requires agreeing on schema on status with the spreadsheet )

# Scheduling
[x] Deal with overconstrained results
[x] Deal with multiple people
[x] Deal with teams / selection from a group
[ ] "If a deadline is set, then dont do a makespan optimization, otherwise try to"
[x] invariant enforcement
[ ] Need to figure out how to unscrew the whole mapping to dense space and back
[ ] Clean up the way providing team lists works. Undo the way it had been done basically -- metadata is fine it just needs to get placed on assignee_pools
[ ] audit all the different assignee fields are done on Task
[ ] IMPORTANT: dates, people, and tasks should all get densely assigned on ingest and used consistently throughout -- just turned back into names for user
