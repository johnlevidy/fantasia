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
[x] Need to figure out how to unscrew the whole mapping to dense space and back
[ ] Clean up the way providing team lists works. Undo the way it had been done basically -- metadata is fine it just needs to get placed on assignee_pools
[ ] audit all the different assignee fields are done on Task
[ ] IMPORTANT: dates, people, and tasks should all get densely assigned on ingest and used consistently throughout -- just turned back into names for user
[ ] Metadata should know about all people or teams people or neither
[ ] Be able to refelct results back to the spreadsheet somehow
[ ] Show "what can be picked up list" from a toposort ( y ask )
[ ] make end ddate metadata work again
[ ] IMPORTANT: figure out what happens as project evolve and dates roll
[ ] deal with spaces in people's task lists, merge at end
[ ] Parallelizable tasks ( linear chain of one day tasks for items with estimate != end - start )
[ ] assign utilization % for people
[ ] Ability to "wipe out" someones assignment ( basically has to wipe all dates + assignments in their downstream dag )
