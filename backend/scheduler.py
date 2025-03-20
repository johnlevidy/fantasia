import networkx as nx
import numpy as np
import re

from datetime import datetime
from collections import defaultdict
from functools import partial

from .dateutil import busdays_offset, busdays_between
from .types import Task, Metadata

# Track the assignment of people to work on tasks on particular dates.
class TaskCalendar:
    def __init__(self):
        # Store assignments as {date:{person:[task_name]}}.
        self.cal = defaultdict(partial(defaultdict, list))

    def busy(self, person, date):
        return person in self.cal[date]

    def free_days(self, person, start_date, end_date):
        free = 0
        date = start_date
        while date < end_date:
            if not self.busy(person, date):
                free +=1
            date = busdays_offset(date, 1)
        return free

    def assign(self, person, task, date):
        self.cal[date][person].append(task)

    def add(self, other):
        for date, people in other.cal.items():
            for person, tasks in people.items():
                for task in tasks:
                    self.assign(person, task, date)

# Match the $TEAM(N) syntax.
team_regex = re.compile("([^(]+)\\(([0-9]+)\\)")

# Convert the "assigned" property on a task to a list of people who could
# work on the task. The list is of form [(N:int, people:[str])] where we 
# want to assign N of the people to the task.
def get_people(assigned, metadata):
    people = set() # ignore duplicates in the input.
    teams  = {}    # same.
    for name in assigned:
        # Team(N)?
        m = team_regex.fullmatch(name)
        if m is not None:
            team, n = m.group(1, 2)
            if not team in metadata.teams: raise Exception(f"Unknown team {team}")
            entry = (int(n), metadata.teams[team])
            if entry[0] < 1: raise Exception(f"Invalid team expression \"{name}\"")
            if entry[0] > len(entry[1]): entry = (len(entry[1]), entry[1]) 
            teams[team] = entry
            continue

        # Team or person.
        if name in metadata.teams:
            teams[name] = (1, metadata.teams[name])
            continue
        if name in metadata.people:
            people.add(name)
            continue

        raise Exception(f"Unknown name {name}")
    
    # For each person, if their team is also assigned, remove them from 
    # the team list.
    for p in people:
        team = metadata.people[p]
        if team in teams:
            entry = teams[team]
            entry = (entry[0] - 1, list(entry[1]))
            entry[1].remove(p)
            if entry[0] == 0: 
                del(teams[team]) # Nobody else left...
            else:
                teams[team] = entry

    # Build the output list.
    # If nobody's been assigned, assign Anon.
    output = []
    for p in people:         output.append((1, [p]))
    for p in teams.values(): output.append(p)
    if len(output) == 0:     output.append((1, [Metadata.ANON]))
    output.sort()
    return output

# A no-op scheduler.
def no_op_scheduler(G, task, backwards, metadata):
    pass

# A scheduler that just assigns people to the task without moving dates
# or worrying about conflicts.
class AssigningScheduler():
    def __init__(self):
        self.scheduled_tasks    = set()
        self.backwards_calendar = TaskCalendar()
        self.forwards_calendar  = TaskCalendar()

    def __call__(self, G, task, backwards, metadata):
        # Skip zero-duration and already-scheduled tasks.
        if task.estimate == 0 or task in self.scheduled_tasks: 
            return
        
        people = get_people(task.assigned, metadata)
        if backwards:
            self._schedule(people, self.backwards_calendar, task, backwards)
        else:
            self._schedule(people, self.forwards_calendar, task, backwards)

        self.scheduled_tasks.add(task)

    def _schedule(self, people, cal, task, backwards):
        date = busdays_offset(task.end_date, -1) if backwards else task.start_date
        step = -1 if backwards else 1
        for group in people:
            for i in range(group[0]):
                p = group[1][i]
                task.assignees.append(p)
                for d in range(task.estimate):
                    cal.assign(p, task, busdays_offset(date, d * step))

    def get_calendar(self):
        cal = TaskCalendar()
        cal.add(self.backwards_calendar)
        cal.add(self.forwards_calendar)
        return cal

# A scheduler that levels out a project to avoid overallocating people to
# tasks, using the rule that each person can only work on one task on
# any given day. The days don't need to be contiguous, though, if the task
# is oversized.
class GreedyLevelingScheduler(AssigningScheduler):
    def _schedule(self, people, cal, task, backwards):
        # Go through each group, and look for free days between the task start and end
        # date for each person. Record the people who have enough free days, and if we
        # meet the requirement for each group we've found a valid assignment. If not,
        # shift the task one day and try again.
        step = -1 if backwards else 1
        while True:
            free_days = []
            good      = []
            for group in people:
                free = [cal.free_days(person, task.start_date, task.end_date) for person in group[1]]
                free_days.append(free)
                good     .append(sum([1 if f >= task.estimate else 0 for f in free]) >= group[0])

            # If we have a good assignment, or the task has one non-generated date, save it.
            # Avoid already allocated days, unless the person doesn't have enough free in
            # which case just allocate from the task start or end date.
            if sum(good) == len(good) or not task.gen_start or not task.gen_end:
                initial_date = busdays_offset(task.end_date, -1) if backwards else task.start_date
                for i in range(len(people)): # i is the index of the person group
                    group = people[i]
                    free  = free_days[i]
                    order = list(reversed(np.argsort(free, kind='stable')))
                    for j in range(group[0]): # j is the index of the person in the person group
                        person = group[1][order[j]]
                        task.assignees.append(person)
                        if free[order[j]] < task.estimate:
                            # Not enough free days; allocate from the initial date.
                            for d in range(task.estimate):
                                cal.assign(person, task, busdays_offset(initial_date, d * step))
                        else:
                            # Just allocate the free days, it should work out.
                            days = task.estimate
                            d = 0
                            while days > 0:
                                date = busdays_offset(initial_date, d * step)
                                if not cal.busy(person, date):
                                    cal.assign(person, task, date)
                                    days -= 1
                                d += 1
                            
                return

            # Didn't work out this pass; shift the task start and end dates by one business day
            # and try again.
            task.start_date = busdays_offset(task.start_date, step)
            task.end_date   = busdays_offset(task.end_date,   step)

# Generic scheduler. Takes a function that'll attempt to schedule a task if it
# doesn't already have a fixed start or end date.
def schedule_graph(G, scheduler, metadata):
    # First, for tasks that have been assigned start or end dates, schedule them in.
    # At this point we're not going to adjust connected tasks (although the scheduler
    # could move the tasks themselves - in this case, push things into the future).
    for task in G.nodes:
        if task.start_date is not None and task.end_date is not None:
            scheduler(G, task, True, metadata)

    # Now, back propagate dates (so end dates can be based on start dates of successor tasks).
    #
    # TODO - I read some papers that suggest starting with the critical path, then
    # repeating with the original critical path deweighted.
    topo = list(nx.topological_sort(G))
    for task in reversed(topo):
        # If this task doesn't have an end date, use the metadata end date, if there
        # is one. If there isn't, we can't reason about its dates nor dates for 
        # ancestor tasks, so we'll skip it.
        if task.end_date is None:
            if metadata.end_date is None:
                continue
            task.end_date = metadata.end_date
            task.gen_end  = True

        # If it doesn't have a start date, set it now based on the estimate.
        # Note - this is done here since the end date could have been set from 
        # a successor task; this sets start date based on end date being set as
        # a consequence of the above logic as well as the below.
        if task.start_date is None:
            task.start_date = busdays_offset(task.end_date, -task.estimate)
            task.gen_start  = True

        # Run the task through the scheduler.
        scheduler(G, task, True, metadata)

        # Propagate dates through the graph. Tasks without an end date will be assigned one;
        # if the gen_end flag is already set on the task then the end date will be updated
        # to match the earliest start date of successor tasks.
        for pred in G.predecessors(task):
            max_pred_end_date = busdays_offset(task.start_date, -metadata.min_slack)
            if pred.end_date is None or (pred.gen_end and pred.end_date > max_pred_end_date):
                pred.end_date = max_pred_end_date
                pred.gen_end  = True

    # Forward propagate to fill in any remaining missing dates. Tasks without predecessors 
    # will default to today's date, since that's the earliest they _could_ start, at this point.
    # TODO should match the user's timezone.
    today = datetime.now().date()
    for task in topo:
        # If the task needs a start date, set it to today. Then set the end date if necessary.
        # We can be in this situation if a project has no end date, so the backwards
        # pass couldn't schedule tasks with no dates provided.
        if task.start_date is None:
            task.start_date = today
            task.gen_start  = True
        if task.end_date is None:
            task.end_date = busdays_offset(task.start_date, task.estimate)
            task.gen_end  = True

        # Schedule the task.
        scheduler(G, task, False, metadata)

        for succ in G.successors(task):
            min_succ_start_date = busdays_offset(task.end_date, metadata.min_slack)
            if succ.start_date is None or (succ.gen_start and succ.start_date < min_succ_start_date):
                succ.start_date = min_succ_start_date
                succ.gen_start  = True
