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
