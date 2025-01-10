## TODO / Hygiene

1. backend/csv_parser.py:30:        # TODO: enforce invariants on data presence more generally ( json included )
"What columns do we know we need" needs to be enforced before dot and graph starts accessing them
2. backend/app.py:12:# TODO: Get rid of any throws, swallow and append to error_string, then return 

## Features

1. Indicate in some way an item hasn't started yet but should have ( add notification for this as well )
2. Make items that come N days after the furthest out in progress completion date smaller or less visible
3. Notify if an estimate doesn't make sense given start / end
4. Notify if start > end
5. Clearly indicate which items are complete ( requires agreeing on schema on status with the spreadsheet )
6. Filtering on the type of the notification
