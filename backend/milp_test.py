import unittest
import networkx as nx
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from backend.types import Metadata, Task

from .milp_solve import milp_schedule_graph

@dataclass
class TestScenario:
    tasks: List[Dict]  # Dictionary of task properties
    dependencies: List[Tuple[str, str]]  # (from_task_name, to_task_name)
    people: List[str]
    expected_makespan: Optional[int] = None
    expected_infeasible: bool = False

def create_metadata_from_scenario(scenario):
    m = Metadata()
    m.teams['All'] = scenario.people
    m.people = scenario.people
    # Make special team names from the specs
    for spec in scenario.tasks:
        if 'assignee_pool' in spec:
            m.teams[':'.join(spec['assignee_pool'])] = spec['assignee_pool']
    return m

# Create a list of tasks from the task specification
def create_tasks_from_specs(task_specs):
    tasks = {}
    for spec in task_specs:
        task = Task(spec['name'])
        task.estimate = spec['estimate']
        if 'assigned' in spec:
            task.user_assigned = spec['assigned']
        if 'latest_end' in spec:
            task.end_date = spec['latest_end']
        if 'assignee_pool' in spec:
            # Assume metadata constructed this way
            task.user_assigned = [':'.join(spec['assignee_pool'])]
        tasks[task.name] = task
    
    return tasks

# Build a graph from the test scenario, necessary for input into solver
def build_test_graph(scenario: TestScenario):
    G = nx.DiGraph()
    
    tasks = create_tasks_from_specs(scenario.tasks)
    metadata = create_metadata_from_scenario(scenario)

    for task in tasks.values():
        G.add_node(task)

    for from_name, to_name in scenario.dependencies:
        from_task = tasks[from_name]
        to_task = tasks[to_name]
        G.add_edge(from_task, to_task)

    return G, metadata

def verify_results(test_case, scenario, results, makespan):
    if scenario.expected_infeasible:
        test_case.assertEqual(len(results), 0, f"Expected infeasible scenario but got results: {results}")
        return
   
    # Check makespan if specified
    if scenario.expected_makespan is not None and results:
        test_case.assertEqual(makespan, scenario.expected_makespan)
 
    # Here we can polynomially validate the whole of the plan:
    # 1. No person has overlapping tasks in time
    # 2. Assignments and pools are respected
    task_names_assigned = set()
    task_completion_times = {}  # Track when each task completes
    person_schedule = {}  # Track each person's schedule
    
    for assignment in results:
        # Extract task name from the assignment
        task_idx = assignment.task
        task_name = assignment.task_name
        person_name = assignment.person_name 
        start_time = assignment.start
        end_time = assignment.end
        
        # Record task assignment
        if task_name not in task_names_assigned:
            task_names_assigned.add(task_name)
        
        # Record task completion time
        task_completion_times[task_name] = max(end_time, task_completion_times.get(task_name, 0))
        
        # Check for resource conflicts
        if person_name not in person_schedule:
            person_schedule[person_name] = []
        
        # Check for overlapping assignments for this person
        for existing_start, existing_end, existing_task in person_schedule[person_name]:
            if not (end_time <= existing_start or start_time >= existing_end):
                test_case.fail(f"Resource conflict: {person_name} assigned to both {task_name} ({start_time}-{end_time}) and {existing_task} ({existing_start}-{existing_end})")
        person_schedule[person_name].append((start_time, end_time, task_name))
    
    # Check all tasks are assigned
    all_task_names = {spec['name'] for spec in scenario.tasks}
    test_case.assertEqual(task_names_assigned, all_task_names, f"Not all tasks assigned. Missing: {all_task_names - task_names_assigned}")
    
    # Check dependencies
    for dep_from, dep_to in scenario.dependencies:
        if dep_from in task_completion_times and dep_to in task_completion_times:
            # Find the start time of the dependent task
            dep_to_start_time = min([assignment.start for assignment in results 
                                    if 'Task' + str(assignment.task + 1) == dep_to])
            
            # Get the completion time of the prerequisite task
            dep_from_end_time = task_completion_times[dep_from]
            
            # Verify dependency constraint
            test_case.assertLessEqual(
                dep_from_end_time, dep_to_start_time,
                f"Dependency violation: {dep_to} starts at {dep_to_start_time} before {dep_from} completes at {dep_from_end_time}"
            )
    
    # Check that tasks with assignee_pool are assigned to eligible people
    for i, task_spec in enumerate(scenario.tasks):
        task_name = task_spec['name']
        
        # Check assignee_pool constraint if it exists
        if 'assignee_pool' in task_spec:
            eligible_people = task_spec['assignee_pool']
            for assignment in results:
                if assignment.task_name == task_name:
                    person_name = assignment.person_name
                    test_case.assertIn(
                        person_name, eligible_people,
                        f"Task {task_name} assigned to {person_name} who is not in the assignee_pool {eligible_people}"
                    )
        
        # Check fixed assignments if they exist
        # Check that all required people are assigned to the task
        if 'assigned' in task_spec:
            assigned_people = task_spec['assigned']
            test_case.assertEqual(set(task_spec['assigned']), set(assigned_people))
    
    # Check latest_end constraints
    for i, task_spec in enumerate(scenario.tasks):
        task_name = task_spec['name']
        
        if 'latest_end' in task_spec:
            latest_end = task_spec['latest_end']
            actual_end = task_completion_times.get(task_name, 0)
            
            test_case.assertLessEqual(
                actual_end, latest_end,
                f"Task {task_name} completes at {actual_end} which is after its latest_end constraint of {latest_end}"
            )

# Test scenarios
class TestScheduler(unittest.TestCase):
    def run_scenario(self, scenario):
        G, metadata = build_test_graph(scenario)
        results, ms = milp_schedule_graph(G, metadata)
        verify_results(self, scenario, results, ms)

    def test_basic_single_person_assignment(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 3},
                {"name": "Task2", "estimate": 2},
                {"name": "Task3", "estimate": 4}
            ],
            dependencies=[],
            people=["Alice"],
            expected_makespan=9  # 3 + 2 + 4
        )
        self.run_scenario(scenario)

    
    def test_basic_multi_person_parallel_work(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 3},
                {"name": "Task2", "estimate": 2},
                {"name": "Task3", "estimate": 4}
            ],
            dependencies=[],
            people=["Alice", "Bob"],
            expected_makespan=5  # Max(3+2, 4) assuming optimal distribution
        )
        self.run_scenario(scenario)

    
    def test_simple_dependencies(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2},
                {"name": "Task2", "estimate": 3},
                {"name": "Task3", "estimate": 1}
            ],
            dependencies=[("Task1", "Task2"), ("Task2", "Task3")],  # 1 -> 2 -> 3
            people=["Alice"],
            expected_makespan=6  # 2 + 3 + 1
        )
        self.run_scenario(scenario)

    
    def test_pre_assigned_tasks(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assigned": ["Alice"]},
                {"name": "Task2", "estimate": 3, "assigned": ["Bob"]},
                {"name": "Task3", "estimate": 1, "assigned": ["Alice"]}
            ],
            dependencies=[],
            people=["Alice", "Bob"],
            expected_makespan=3  # Max(2+1, 3)
        )
        self.run_scenario(scenario)

    
    def test_multi_person_task(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2},
                {"name": "Task2", "estimate": 3, "assigned": ["Alice", "Bob"]},
                {"name": "Task3", "estimate": 1}
            ],
            dependencies=[("Task1", "Task2"), ("Task2", "Task3")],
            people=["Alice", "Bob", "Charlie"],
            expected_makespan=6  # 2 + 3 + 1
        )
        self.run_scenario(scenario)

    
    def test_assignee_pool_restriction(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assignee_pool": ["Alice", "Bob"]},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Bob", "Charlie"]},
                {"name": "Task3", "estimate": 1, "assignee_pool": ["Alice"]}
            ],
            dependencies=[],
            people=["Alice", "Bob", "Charlie"],
            expected_makespan=3  # Optimal assignment: 1->Alice, 2->Bob, 3->Alice (in parallel)
        )
        self.run_scenario(scenario)

    
    def test_latest_end_constraint(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2},
                {"name": "Task2", "estimate": 3, "latest_end": 2},
                {"name": "Task3", "estimate": 1}
            ],
            dependencies=[],
            people=["Alice"],
            expected_infeasible=True  # Cannot complete 2 (3 units) by time 3 if we start at 0
        )
        self.run_scenario(scenario)

    def test_infeasible_due_to_dependencies_and_latest_end(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2},
                {"name": "Task2", "estimate": 3, "latest_end": 4},  # Cannot complete 2+3 by time 4
                {"name": "Task3", "estimate": 1}
            ],
            dependencies=[("Task1", "Task2")],  # Task1 must complete before Task2 can start
            people=["Alice"],
            expected_infeasible=True
        )
        self.run_scenario(scenario)

    def test_complex_dependency_chain(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 1},
                {"name": "Task2", "estimate": 2},
                {"name": "Task3", "estimate": 3},
                {"name": "Task4", "estimate": 2},
                {"name": "Task5", "estimate": 1}
            ],
            dependencies=[("Task1", "Task2"), ("Task1", "Task3"), 
                         ("Task2", "Task4"), ("Task3", "Task4"), 
                         ("Task4", "Task5")],
            people=["Alice", "Bob"],
            expected_makespan=7  # Critical path: 1->3->4->5 = 1+3+2+1
        )
        self.run_scenario(scenario)


    def test_multiple_multi_person_tasks(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assigned": ["Alice", "Bob"]},
                {"name": "Task2", "estimate": 3, "assigned": ["Bob", "Charlie"]},
                {"name": "Task3", "estimate": 1, "assigned": ["Alice", "Charlie"]}
            ],
            dependencies=[("Task1", "Task3")],
            people=["Alice", "Bob", "Charlie"],
            expected_makespan=6  # 1->3 = 2+1, and 2 can be done in parallel with 1
        )
        self.run_scenario(scenario)

    
    def test_mixed_single_and_multi_person_tasks(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assigned": ["Alice"]},
                {"name": "Task2", "estimate": 3, "assigned": ["Bob", "Charlie"]},
                {"name": "Task3", "estimate": 1},
                {"name": "Task4", "estimate": 2, "assigned": ["Alice", "Bob"]}
            ],
            dependencies=[("Task1", "Task4"), ("Task2", "Task3")],
            people=["Alice", "Bob", "Charlie"],
            expected_makespan=5  # Critical path: 1->4 = 2+2, and 2->3 = 3+1
        )
        self.run_scenario(scenario)

    def test_large_team_with_specialized_skills(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 5, "assignee_pool": ["Alice", "Dave"]},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Bob", "Eve"]},
                {"name": "Task3", "estimate": 4, "assignee_pool": ["Bob", "Eve"]},
                {"name": "Task4", "estimate": 6, "assignee_pool": ["Charlie", "Frank"]},
                {"name": "Task5", "estimate": 5, "assignee_pool": ["Charlie", "Frank"]},
                {"name": "Task6", "estimate": 4, "assignee_pool": ["Dave", "Grace"]},
                {"name": "Task7", "estimate": 3, "assignee_pool": ["Eve", "Heidi"]},
                {"name": "Task8", "estimate": 2, "assignee_pool": ["Frank", "Ivan"]}
            ],
            dependencies=[
                ("Task1", "Task2"), ("Task1", "Task4"), 
                ("Task2", "Task3"), ("Task4", "Task5"),
                ("Task3", "Task7"), ("Task5", "Task7"),
                ("Task6", "Task7"), ("Task7", "Task8")
            ],
            people=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace", "Heidi", "Ivan"],
            expected_makespan=21  # Critical path: Task1->Task4->Task5->Task7->Task8 = 5+6+5+3+2
        )
        self.run_scenario(scenario)

    
    def test_resource_contention_with_tight_deadlines(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 4, "assignee_pool": ["Alice", "Bob"], "latest_end": 5},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Bob", "Charlie"], "latest_end": 8},
                {"name": "Task3", "estimate": 5, "assignee_pool": ["Alice", "Charlie"], "latest_end": 10},
                {"name": "Task4", "estimate": 2, "assignee_pool": ["Alice", "Bob"], "latest_end": 12},
                {"name": "Task5", "estimate": 3, "assignee_pool": ["Bob", "Charlie"], "latest_end": 15}
            ],
            dependencies=[("Task1", "Task3"), ("Task2", "Task4"), ("Task3", "Task5")],
            people=["Alice", "Bob", "Charlie"],
            expected_makespan=12  # Optimal assignment respecting latest_end constraints
        )
        self.run_scenario(scenario)

    
    def test_complex_multi_person_collaboration(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 4, "assigned": ["Alice", "Bob", "Charlie"]},
                {"name": "Task2", "estimate": 2, "assigned": ["Alice", "Dave"]},
                {"name": "Task3", "estimate": 5, "assignee_pool": ["Bob", "Eve", "Frank"]},
                {"name": "Task4", "estimate": 6, "assignee_pool": ["Charlie", "Dave", "Grace"]},
                {"name": "Task5", "estimate": 3, "assigned": ["Alice", "Bob", "Charlie", "Dave"]},
                {"name": "Task6", "estimate": 4, "assignee_pool": ["Eve", "Frank", "Grace"]},
                {"name": "Task7", "estimate": 3, "assignee_pool": ["Alice", "Eve", "Grace"]}
            ],
            dependencies=[
                ("Task1", "Task2"), 
                ("Task2", "Task3"), ("Task2", "Task4"),
                ("Task3", "Task5"), ("Task4", "Task5"),
                ("Task5", "Task6"), ("Task6", "Task7")
            ],
            people=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace"],
            expected_makespan=22  # Task1->Task2->Task4->Task5->Task6->Task7
        )
        self.run_scenario(scenario)

    
    def test_highly_parallel_work_with_limited_resources(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assignee_pool": ["Alice", "Bob"]},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Bob", "Charlie"]},
                {"name": "Task3", "estimate": 4, "assignee_pool": ["Charlie", "Dave"]},
                {"name": "Task4", "estimate": 2, "assignee_pool": ["Dave", "Alice"]},
                {"name": "Task5", "estimate": 3, "assignee_pool": ["Alice", "Eve"]},
                {"name": "Task6", "estimate": 1, "assignee_pool": ["Bob", "Eve"]},
                {"name": "Task7", "estimate": 2, "assignee_pool": ["Charlie", "Frank"]},
                {"name": "Task8", "estimate": 3, "assignee_pool": ["Dave", "Frank"]},
                {"name": "Task9", "estimate": 4, "assignee_pool": ["Eve", "Alice"]},
                {"name": "Task10", "estimate": 2, "assignee_pool": ["Frank", "Bob"]}
            ],
            dependencies=[],  # No dependencies - all tasks can be parallelized
            people=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"],
            expected_makespan=5  # Optimal assignment allows completion in 5 time units
        )
        self.run_scenario(scenario)

    
    def test_diamond_dependencies_with_variable_resources(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 1, "assigned": ["Alice"]},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Bob", "Charlie"]},
                {"name": "Task3", "estimate": 2, "assignee_pool": ["Bob", "Charlie"]},
                {"name": "Task4", "estimate": 2, "assignee_pool": ["Dave", "Eve"]},
                {"name": "Task5", "estimate": 4, "assignee_pool": ["Dave", "Eve"]},
                {"name": "Task6", "estimate": 5, "assignee_pool": ["Frank", "Grace"]},
                {"name": "Task7", "estimate": 2, "assigned": ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace"]}
            ],
            dependencies=[
                ("Task1", "Task2"), ("Task1", "Task4"), ("Task1", "Task6"),
                ("Task2", "Task3"), ("Task4", "Task5"),
                ("Task3", "Task7"), ("Task5", "Task7"), ("Task6", "Task7")
            ],
            people=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace"],
            expected_makespan=9  # Critical path: Task1->Task6->Task7 = 1+5+2
        )
        self.run_scenario(scenario)

    
    def test_staggered_deadlines_with_resource_sharing(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 3, "assignee_pool": ["Alice", "Bob"], "latest_end": 5},
                {"name": "Task2", "estimate": 4, "assignee_pool": ["Charlie", "Dave"], "latest_end": 10},
                {"name": "Task3", "estimate": 2, "assignee_pool": ["Eve", "Frank"], "latest_end": 12},
                
                {"name": "Task4", "estimate": 2, "assignee_pool": ["Alice", "Bob"], "latest_end": 7},
                {"name": "Task5", "estimate": 5, "assignee_pool": ["Charlie", "Dave"], "latest_end": 13},
                {"name": "Task6", "estimate": 3, "assignee_pool": ["Eve", "Frank"], "latest_end": 16},
                
                {"name": "Task7", "estimate": 4, "assignee_pool": ["Alice", "Bob"], "latest_end": 9},
                {"name": "Task8", "estimate": 3, "assignee_pool": ["Charlie", "Dave"], "latest_end": 15},
                {"name": "Task9", "estimate": 2, "assignee_pool": ["Eve", "Frank"], "latest_end": 18},
                
                {"name": "Task10", "estimate": 3, "assigned": ["Alice", "Charlie", "Eve"], "latest_end": 20}
            ],
            dependencies=[
                ("Task1", "Task2"), ("Task2", "Task3"),
                ("Task4", "Task5"), ("Task5", "Task6"),
                ("Task7", "Task8"), ("Task8", "Task9"),
                ("Task3", "Task10"), ("Task6", "Task10"), ("Task9", "Task10")
            ],
            people=["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"],
            expected_makespan=15  # Respecting all latest_end constraints
        )
        self.run_scenario(scenario)

    
    def test_mixed_constraints_with_bottleneck_resources(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 3, "assigned": ["Expert"]},
                {"name": "Task2", "estimate": 4, "assignee_pool": ["Designer1", "Designer2"]},
                {"name": "Task3", "estimate": 3, "assignee_pool": ["Designer1", "Designer2"]},
                {"name": "Task4", "estimate": 5, "assignee_pool": ["Dev1", "Dev2", "Dev3"]},
                {"name": "Task5", "estimate": 4, "assignee_pool": ["Dev1", "Dev2", "Dev3"]},
                {"name": "Task6", "estimate": 6, "assignee_pool": ["Dev1", "Dev2", "Dev3"]},
                {"name": "Task7", "estimate": 2, "assignee_pool": ["QA1", "QA2"]},
                {"name": "Task8", "estimate": 3, "assignee_pool": ["QA1", "QA2"]},
                {"name": "Task9", "estimate": 2, "assignee_pool": ["QA1", "QA2"]},
                {"name": "Task10", "estimate": 1, "assigned": ["DevOps"]}
            ],
            dependencies=[
                ("Task1", "Task2"), ("Task1", "Task3"),
                ("Task2", "Task4"), ("Task2", "Task5"),
                ("Task3", "Task6"),
                ("Task4", "Task7"), ("Task5", "Task8"), ("Task6", "Task9"),
                ("Task7", "Task10"), ("Task8", "Task10"), ("Task9", "Task10")
            ],
            people=["Expert", "Designer1", "Designer2", "Dev1", "Dev2", "Dev3", "QA1", "QA2", "DevOps"],
            expected_makespan=17  # Critical path considering resource constraints
        )
        self.run_scenario(scenario)

    
    def test_sparse_dependencies_with_specialized_skills(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2, "assignee_pool": ["Frontend1", "Frontend2"]},
                {"name": "Task2", "estimate": 3, "assignee_pool": ["Backend1", "Backend2"]},
                {"name": "Task3", "estimate": 4, "assignee_pool": ["DB1"]},
                {"name": "Task4", "estimate": 1, "assignee_pool": ["Frontend1", "Frontend2"]},
                {"name": "Task5", "estimate": 3, "assignee_pool": ["Backend1", "Backend2"]},
                {"name": "Task6", "estimate": 2, "assignee_pool": ["DB1"]},
                {"name": "Task7", "estimate": 3, "assignee_pool": ["Frontend1"]},
                {"name": "Task8", "estimate": 2, "assignee_pool": ["Backend2"]},
                {"name": "Task9", "estimate": 1, "assignee_pool": ["DB1"]},
                {"name": "Task10", "estimate": 4, "assignee_pool": ["Frontend1", "Frontend2", "Backend1", "Backend2", "DB1"]}
            ],
            dependencies=[
                ("Task1", "Task4"), ("Task2", "Task5"), ("Task3", "Task6"),
                ("Task4", "Task7"), ("Task5", "Task8"), ("Task6", "Task9"),
                ("Task7", "Task10"), ("Task8", "Task10"), ("Task9", "Task10")
            ],
            people=["Frontend1", "Frontend2", "Backend1", "Backend2", "DB1"],
            expected_makespan=12  # Critical path with specialized resource constraints
        )
        self.run_scenario(scenario)


    def test_cyclic_graph_detection(self):
        scenario = TestScenario(
            tasks=[
                {"name": "Task1", "estimate": 2},
                {"name": "Task2", "estimate": 3},
                {"name": "Task3", "estimate": 1},
                {"name": "Task4", "estimate": 4}
            ],
            dependencies=[
                ("Task1", "Task2"), 
                ("Task2", "Task3"), 
                ("Task3", "Task4"),
                ("Task4", "Task1")  # This creates a cycle: 1->2->3->4->1
            ],
            people=["Alice", "Bob"],
            expected_infeasible=True  # Should detect cyclic dependency
        )
        self.run_scenario(scenario)

if __name__ == "__main__":
    unittest.main()
