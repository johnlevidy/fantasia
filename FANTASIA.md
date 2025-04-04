# Fantasia

## What is fantasia?

Fantasia is a tool to assist tech leads, PMs, and managers of all levels plan their projects and provide: 

1. **Project DAG visualization** -- this aids both individual contributors and senior management in understanding the flow of the project, as well as giving a more intuitive way of reasoning about slack and item delays. 
2. **Project Planning** -- fantasia uses google's ortools / SAT solver to automatically plan the project. *This is foremost intended strictly to assist managers in understanding the impact of different assignment decisions, but is in no way a replacement for careful project planning in a way that aligns with people's interests, skillsets, and ambitions.*	

It was developed out of a need to address some specific questions:

* An IC wondering how much "slack" an item has -- how much time before their work is on the critical path.
* Senior management and business stakeholders wondering how a reprioritization might impact final project delivery.
* Middle management needing to come up with delivery dates and assignments in incredibly complex projects with multiple external team dependencies. 
* Other engineering partners wanting to plan their work and understand at what point they ought to free up sources to join in on a project.
* ICs wanting visibility into the way the larger project comes together; its goals, commitments, and complexities.

And many more!

## The Idealized Setting

The idealized setting of a software project involves a bunch of individual work items with:

1. Estimates
2. Dependencies and Prerequisites

For each of these items, the managers job at the outset of a project is to estimate the total work involved and how many people would be reasonable to assign to it ( or consider unavailable for other work ). It's clear that creating an optimal schedule subject to assignment constraints is NP-Hard ( specifically, the extended flexible job shop scheduling problem ). And so this exercise quickly devolves into unscientific "buffers", "multipliers", or heuristics like dividing the total estimated work by the total work available. With enough experience, managers are actually very good at this! That said, it's incredibly brittle to change -- how does the heuristic respond to a question from the business like "can we pull XYZ off to work on something else for 2 months"? This is the space projects tend to accumulate delays.

## Specifics of Fantasia

### The Solver

I spent a lot of time researching and attempting to implement cutting-edge "Extended Flexible Job Shop Scheduling" algorithms, but: 

1. They weren't responsive to change because they are designed for cases where no assignments or dates for any items exist and they perform a one-shot solve. 
2. They were very slow, even for small toy examples.

Google's ortools provides:

1. A generalizable constraint framework that extends nicely to a conception of assignments and dates as simply additional constraints on the optimization.
2. A very fast solution.

### The Workflow

The workflow is admittedly a bit janky. You have to format the data in a tsv or csv formatted in a particular way. Fundamentally it's because in my primary use case, security considerations prevent Google's spreadsheet tool from talking directly to the backend. The lowest-friction way to enable data to move back and forth is by having the user copy and paste it back and forth. 

## Basic Usage

1. First, follow the [README](README.md) to set up the web server / back end. 

2. Try copying [This spreadsheet](https://docs.google.com/spreadsheets/d/1PelOKB_MJB4ZMWDPYD_TPvOwPBruQ6Xvqb6xOSxf_nI/edit?gid=369183059#gid=369183059) into the website.

3. You should see a DAG with a makespan of 29. The visualization is pannable and zoomable. To incorporate the content of this plan back into the spreadsheet, click "Copy Plan" in the top right and copy it at the first cell under the header.

4. This is the core work loop with fantasia. *You provide constraints only on start date, end date, and assignee*. Fantasia will minimize project delivery subject to those constraints. You can provide as many or few of those as you want. 

### Real-Life Work Loop

1. Use a completely unconstrained project view to understand the theoretical minimum delivery time ( this often involves assigning different people to similar work themes, irrespective of career ambitions or expertise ).
2. Use team designations to create subgroups on expertise and work theme; begin to constrain assignments to particular teams, see how it moves out the delivery date.
3. Continue to solidify assignments and dates until a date is arrived at.

As issues arise and people need to be reprioritized, all assignments and dates of theirs ( and others in their dependency path ) need to be cleared. Unfortunately, there is not currently an easy way to do this, but it's an easy feature to add! Once that's done ( today by hand ) you can assign them to a placeholder and rerun the project.

## Features, Notes, Idiosyncracies

### Scheduling Notes
1. The most important thing to keep in mind is that Fantasia is fundamentally nothing more than a constraint solver. **If you overconstrain the problem such that no solutions exist, the best thing Fantasia can do is move the start date backward and try again. It will attempt to do this for up to 6 months**.
2. There are many cases where it might not be intuitive why a project is overconstrained and the start date has to roll back, but some I have run into:
  - You incorporated some project assignments for a subset of the project without blowing out those assignees other assignments later in the project. They may have strictly overlapping dates and that will appear to the optimizer as unsolvable. **Again, today the only constraint it will relax and iterate on is the start date**. 
  - You have an item with an end date long in the past.
  - You have an item with a start date after an end date.
  - I have not run into any cases ( yet ) where the optimizer was wrong, it was always an issue with the input data, but they can be difficult to spot. There is a ton of work to do on better error handling / feedback to users on cases that are easy-to-catch.

### Spreadsheet Features
1. Team assignments -- as in the provided example, assignees can be grouped into teams as an alias. All people are expected to be present at least once in a team but ( today ) not repeated.
2. Assignee time proportions -- Within a team, a user can be designated with syntax "Mike:.5" -- this means Mike is assignable but constrain his total time spent over the duration of the project ( makespan ) to 50% of the makespan.
3. Multiple assignments -- You can indicate a single item is assigned full time to multiple people "Mike, John".

There is no current way to express the parallelizability or duty cycle of an item, but it's a feature that should be added. For now, you can make some dummy user to capture these. It can be implemented by splitting the work item into a linear chain of 1 day items, similar to the process of task splitting across user.

### DAG View Features ( TODO )
1. 




