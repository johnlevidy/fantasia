import unittest
from .dateutil import busdays_offset
from .types import *
from .app import build_graph_and_schedule
import networkx as nx
import datetime

today = datetime.datetime.now().date()

class SchedulerTest(unittest.TestCase):
    def test_basic_single_person_assignment(self):
        tasks = [
                InputTask("Task1", "", False, ['All'], [], False, 3, None, None, Status.NotStarted, 0),
                InputTask("Task2", "", False, ['All'], [], False, 2, None, None, Status.NotStarted, 1),
                InputTask("Task3", "", False, ['All'], [], False, 4, None, None, Status.NotStarted, 2),
                ]
        metadata = Metadata()
        metadata.people_allocations = {Person("Alice"): 1}
        metadata.teams = {'All': Team('All', [Person("Alice")])}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(9, makespan)

    def test_basic_multi_person_parallel_work(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], [], False, 3, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], [], False, 2, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], [], False, 4, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1
        }
        metadata.teams = {
            'All': Team('All', [Person("Alice"), Person("Bob")])
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(5, makespan)  # Max(3+2, 4)

    def test_simple_dependencies(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], [], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], ["Task1"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], ["Task2"], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {Person("Alice"): 1}
        metadata.teams = {'All': Team('All', [Person("Alice")])}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(6, makespan)  # 2 + 3 + 1
    
    def test_pre_assigned_tasks(self):
        tasks = [
            InputTask("Task1", "", True, ["Alice"], [], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", True, ["Bob"], [], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", True, ["Alice"], [], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1
        }
        metadata.teams = {}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(3, makespan)  # Max(2+1, 3)

    def test_multi_person_task(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], ["Task2"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", True, ["Alice", "Bob"], ["Task3"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], [], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1,
        }
        metadata.teams = {
            'All': Team('All', [Person("Alice"), Person("Bob"), Person("Charlie")])
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(6, makespan)

    def test_assignee_pool_restriction(self):
        tasks = [
            InputTask("Task1", "", False, ["Pool1"], [], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["Pool2"], [], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["Pool3"], [], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1,
        }
        metadata.teams = {
            "Pool1": Team("Pool1", [Person("Alice"), Person("Bob")]),
            "Pool2": Team("Pool2", [Person("Bob"), Person("Charlie")]),
            "Pool3": Team("Pool3", [Person("Alice")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(3, makespan)

    def test_latest_end_constraint_feasible(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], [], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], [], False, 3, None, busdays_offset(today, 2), Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], [], False, 1, None, busdays_offset(today, 3), Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {Person("Alice"): 1}
        metadata.teams = {'All': Team('All', [Person("Alice")])}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(5, offset)
        self.assertEqual(6, makespan)

    def test_infeasible_due_to_dependencies_and_latest_end(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], ["Task2"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], [], False, 3, None, busdays_offset(today, 4), Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], [], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {Person("Alice"): 1}
        metadata.teams = {'All': Team('All', [Person("Alice")])}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [], step=1)
        self.assertEqual(offset, 1)
        self.assertEqual(6, makespan)

    def test_complex_dependency_chain(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], ["Task2", "Task3"], False, 1, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], ["Task4"], False, 2, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], ["Task4"], False, 3, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ['All'], ["Task5"], False, 2, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ['All'], [], False, 1, None, None, Status.NotStarted, 4),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
        }
        metadata.teams = {
            'All': Team('All', [Person("Alice"), Person("Bob")])
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(7, makespan)  # 1 → 3 → 4 → 5 = 1 + 3 + 2 + 1

    def test_multiple_multi_person_tasks(self):
        tasks = [
            InputTask("Task1", "", True, ["Alice", "Bob"], ["Task3"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", True, ["Bob", "Charlie"], [], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", True, ["Alice", "Charlie"], [], False, 1, None, None, Status.NotStarted, 2),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1,
        }
        metadata.teams = {}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(6, makespan)

    def test_mixed_single_and_multi_person_tasks(self):
        tasks = [
            InputTask("Task1", "", True, ["Alice"], ["Task4"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", True, ["Bob", "Charlie"], ["Task3"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], [], False, 1, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", True, ["Alice", "Bob"], [], False, 2, None, None, Status.NotStarted, 3),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1,
        }
        metadata.teams = {'All': Team('All', [Person("Alice"), Person("Bob"), Person("Charlie")])}

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(5, makespan)

    def test_large_team_with_specialized_skills(self):
        tasks = [
            InputTask("Task1", "", False, ["Team1"], ["Task2", "Task4"], False, 5, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["Team2"], ["Task3"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["Team2"], ["Task7"], False, 4, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ["Team3"], ["Task5"], False, 6, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ["Team3"], ["Task7"], False, 5, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["Team4"], ["Task7"], False, 4, None, None, Status.NotStarted, 5),
            InputTask("Task7", "", False, ["Team5"], ["Task8"], False, 3, None, None, Status.NotStarted, 6),
            InputTask("Task8", "", False, ["Team6"], [], False, 2, None, None, Status.NotStarted, 7),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person(p): 1 for p in ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace", "Heidi", "Ivan"]
        }
        metadata.teams = {
            "Team1": Team("Team1", [Person("Alice"), Person("Dave")]),
            "Team2": Team("Team2", [Person("Bob"), Person("Eve")]),
            "Team3": Team("Team3", [Person("Charlie"), Person("Frank")]),
            "Team4": Team("Team4", [Person("Dave"), Person("Grace")]),
            "Team5": Team("Team5", [Person("Eve"), Person("Heidi")]),
            "Team6": Team("Team6", [Person("Frank"), Person("Ivan")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(21, makespan)

    def test_resource_contention_with_tight_deadlines(self):
        tasks = [
            InputTask("Task1", "", False, ["T1"], ["Task3"], False, 4, None, busdays_offset(today, 5), Status.NotStarted, 0),
            InputTask("Task2", "", False, ["T2"], ["Task4"], False, 3, None, busdays_offset(today, 8), Status.NotStarted, 1),
            InputTask("Task3", "", False, ["T3"], ["Task5"], False, 5, None, busdays_offset(today, 10), Status.NotStarted, 2),
            InputTask("Task4", "", False, ["T1"], [], False, 2, None, busdays_offset(today, 12), Status.NotStarted, 3),
            InputTask("Task5", "", False, ["T2"], [], False, 3, None, busdays_offset(today, 15), Status.NotStarted, 4),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1
        }
        metadata.teams = {
            "T1": Team("T1", [Person("Alice"), Person("Bob")]),
            "T2": Team("T2", [Person("Bob"), Person("Charlie")]),
            "T3": Team("T3", [Person("Alice"), Person("Charlie")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(12, makespan)

    def test_complex_multi_person_collaboration(self):
        tasks = [
            InputTask("Task1", "", True, ["Alice", "Bob", "Charlie"], ["Task2"], False, 4, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", True, ["Alice", "Dave"], ["Task3", "Task4"], False, 2, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["T1"], ["Task5"], False, 5, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ["T2"], ["Task5"], False, 6, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", True, ["Alice", "Bob", "Charlie", "Dave"], ["Task6"], False, 3, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["T3"], ["Task7"], False, 4, None, None, Status.NotStarted, 5),
            InputTask("Task7", "", False, ["T4"], [], False, 3, None, None, Status.NotStarted, 6),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person(p): 1 for p in ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace"]
        }
        metadata.teams = {
            "T1": Team("T1", [Person("Bob"), Person("Eve"), Person("Frank")]),
            "T2": Team("T2", [Person("Charlie"), Person("Dave"), Person("Grace")]),
            "T3": Team("T3", [Person("Eve"), Person("Frank"), Person("Grace")]),
            "T4": Team("T4", [Person("Alice"), Person("Eve"), Person("Grace")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(22, makespan)

    def test_highly_parallel_work_with_limited_resources(self):
        tasks = [
            InputTask("Task1", "", False, ["T1"], [], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["T2"], [], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["T3"], [], False, 4, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ["T4"], [], False, 2, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ["T5"], [], False, 3, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["T6"], [], False, 1, None, None, Status.NotStarted, 5),
            InputTask("Task7", "", False, ["T7"], [], False, 2, None, None, Status.NotStarted, 6),
            InputTask("Task8", "", False, ["T8"], [], False, 3, None, None, Status.NotStarted, 7),
            InputTask("Task9", "", False, ["T9"], [], False, 4, None, None, Status.NotStarted, 8),
            InputTask("Task10", "", False, ["T10"], [], False, 2, None, None, Status.NotStarted, 9),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person(p): 1 for p in ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"]
        }
        metadata.teams = {
            "T1": Team("T1", [Person("Alice"), Person("Bob")]),
            "T2": Team("T2", [Person("Bob"), Person("Charlie")]),
            "T3": Team("T3", [Person("Charlie"), Person("Dave")]),
            "T4": Team("T4", [Person("Dave"), Person("Alice")]),
            "T5": Team("T5", [Person("Alice"), Person("Eve")]),
            "T6": Team("T6", [Person("Bob"), Person("Eve")]),
            "T7": Team("T7", [Person("Charlie"), Person("Frank")]),
            "T8": Team("T8", [Person("Dave"), Person("Frank")]),
            "T9": Team("T9", [Person("Eve"), Person("Alice")]),
            "T10": Team("T10", [Person("Frank"), Person("Bob")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(5, makespan)

    def test_diamond_dependencies_with_variable_resources(self):
        tasks = [
            InputTask("Task1", "", True, ["Alice"], ["Task2", "Task4", "Task6"], False, 1, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["T1"], ["Task3"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["T1"], ["Task7"], False, 2, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ["T2"], ["Task5"], False, 2, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ["T2"], ["Task7"], False, 4, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["T3"], ["Task7"], False, 5, None, None, Status.NotStarted, 5),
            InputTask("Task7", "", True, ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank", "Grace"], [], False, 2, None, None, Status.NotStarted, 6),
        ]
        
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
            Person("Charlie"): 1,
            Person("Dave"): 1,
            Person("Eve"): 1,
            Person("Frank"): 1,
            Person("Grace"): 1,
        }
        metadata.teams = {
            "T1": Team("T1", [Person("Bob"), Person("Charlie")]),
            "T2": Team("T2", [Person("Dave"), Person("Eve")]),
            "T3": Team("T3", [Person("Frank"), Person("Grace")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(9, makespan)

    def test_staggered_deadlines_with_resource_sharing(self):
        tasks = [
            InputTask("Task1", "", False, ["T1"], ["Task2"], False, 3, None, busdays_offset(today, 5), Status.NotStarted, 0),
            InputTask("Task2", "", False, ["T2"], ["Task3"], False, 4, None, busdays_offset(today, 10), Status.NotStarted, 1),
            InputTask("Task3", "", False, ["T3"], ["Task10"], False, 2, None, busdays_offset(today, 12), Status.NotStarted, 2),

            InputTask("Task4", "", False, ["T1"], ["Task5"], False, 2, None, busdays_offset(today, 7), Status.NotStarted, 3),
            InputTask("Task5", "", False, ["T2"], ["Task6"], False, 5, None, busdays_offset(today, 13), Status.NotStarted, 4),
            InputTask("Task6", "", False, ["T3"], ["Task10"], False, 3, None, busdays_offset(today, 16), Status.NotStarted, 5),

            InputTask("Task7", "", False, ["T1"], ["Task8"], False, 4, None, busdays_offset(today, 9), Status.NotStarted, 6),
            InputTask("Task8", "", False, ["T2"], ["Task9"], False, 3, None, busdays_offset(today, 15), Status.NotStarted, 7),
            InputTask("Task9", "", False, ["T3"], ["Task10"], False, 2, None, busdays_offset(today, 18), Status.NotStarted, 8),

            InputTask("Task10", "", True, ["Alice", "Charlie", "Eve"], [], False, 3, None, busdays_offset(today, 20), Status.NotStarted, 9),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person(p): 1 for p in ["Alice", "Bob", "Charlie", "Dave", "Eve", "Frank"]
        }
        metadata.teams = {
            "T1": Team("T1", [Person("Alice"), Person("Bob")]),
            "T2": Team("T2", [Person("Charlie"), Person("Dave")]),
            "T3": Team("T3", [Person("Eve"), Person("Frank")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(15, makespan)

    def test_mixed_constraints_with_bottleneck_resources(self):
        tasks = [
            InputTask("Task1", "", True, ["Expert"], ["Task2", "Task3"], False, 3, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["Design"], ["Task4", "Task5"], False, 4, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["Design"], ["Task6"], False, 3, None, None, Status.NotStarted, 2),

            InputTask("Task4", "", False, ["Dev"], ["Task7"], False, 5, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ["Dev"], ["Task8"], False, 4, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["Dev"], ["Task9"], False, 6, None, None, Status.NotStarted, 5),

            InputTask("Task7", "", False, ["QA"], ["Task10"], False, 2, None, None, Status.NotStarted, 6),
            InputTask("Task8", "", False, ["QA"], ["Task10"], False, 3, None, None, Status.NotStarted, 7),
            InputTask("Task9", "", False, ["QA"], ["Task10"], False, 2, None, None, Status.NotStarted, 8),

            InputTask("Task10", "", True, ["DevOps"], [], False, 1, None, None, Status.NotStarted, 9),
        ]
        metadata = Metadata()
        metadata.people_allocations = {
            Person(p): 1 for p in ["Expert", "Designer1", "Designer2", "Dev1", "Dev2", "Dev3", "QA1", "QA2", "DevOps"]
        }
        metadata.teams = {
            "Design": Team("Design", [Person("Designer1"), Person("Designer2")]),
            "Dev": Team("Dev", [Person("Dev1"), Person("Dev2"), Person("Dev3")]),
            "QA": Team("QA", [Person("QA1"), Person("QA2")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(17, makespan)

    def test_sparse_dependencies_with_specialized_skills(self):
        tasks = [
            InputTask("Task1", "", False, ["Frontend"], ["Task4"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ["Backend"], ["Task5"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ["DB"], ["Task6"], False, 4, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ["Frontend"], ["Task7"], False, 1, None, None, Status.NotStarted, 3),
            InputTask("Task5", "", False, ["Backend"], ["Task8"], False, 3, None, None, Status.NotStarted, 4),
            InputTask("Task6", "", False, ["DB"], ["Task9"], False, 2, None, None, Status.NotStarted, 5),
            InputTask("Task7", "", False, ["Frontend"], ["Task10"], False, 3, None, None, Status.NotStarted, 6),
            InputTask("Task8", "", False, ["Backend"], ["Task10"], False, 2, None, None, Status.NotStarted, 7),
            InputTask("Task9", "", False, ["DB"], ["Task10"], False, 1, None, None, Status.NotStarted, 8),
            InputTask("Task10", "", False, ["All"], [], False, 4, None, None, Status.NotStarted, 9),
        ]

        metadata = Metadata()
        metadata.people_allocations = {
            Person("Frontend1"): 1,
            Person("Frontend2"): 1,
            Person("Backend1"): 1,
            Person("Backend2"): 1,
            Person("DB1"): 1
        }
        metadata.teams = {
            "Frontend": Team("Frontend", [Person("Frontend1"), Person("Frontend2")]),
            "Backend": Team("Backend", [Person("Backend1"), Person("Backend2")]),
            "DB": Team("DB", [Person("DB1")]),
            "All": Team("All", [Person("Frontend1"), Person("Frontend2"), Person("Backend1"), Person("Backend2"), Person("DB1")]),
        }

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        self.assertEqual(0, offset)
        self.assertEqual(12, makespan)

    def test_cyclic_graph_detection(self):
        tasks = [
            InputTask("Task1", "", False, ['All'], ["Task2"], False, 2, None, None, Status.NotStarted, 0),
            InputTask("Task2", "", False, ['All'], ["Task3"], False, 3, None, None, Status.NotStarted, 1),
            InputTask("Task3", "", False, ['All'], ["Task4"], False, 1, None, None, Status.NotStarted, 2),
            InputTask("Task4", "", False, ['All'], ["Task1"], False, 4, None, None, Status.NotStarted, 3),  # Creates cycle
        ]

        metadata = Metadata()
        metadata.people_allocations = {
            Person("Alice"): 1,
            Person("Bob"): 1,
        }
        metadata.teams = {
            "All": Team("All", [Person("Alice"), Person("Bob")])
        }

        with self.assertRaisesRegex(Exception, "Cycle detected in graph.*"):
            build_graph_and_schedule(tasks, metadata, [])

    def test_csv_based_parallel_task_graph(self):
        tasks = [
            InputTask("BigTask", "BigTask", True, ["Lewis"], [], True, 7, None, None, Status.InProgress, 0),
            InputTask("TaskA", "TaskA", True, ["John"], ["TaskB"], False, 3, None, None, Status.InProgress, 1),
            InputTask("TaskB", "TaskB", True, ["Lewis"], ["TaskC"], False, 1, None, None, Status.NotStarted, 2),
            InputTask("TaskC", "TaskC", True, ["Jack"], ["Done"], False, 4, None, None, Status.NotStarted, 3),
            InputTask("Done", "Done", False, [], [], False, 0, None, None, Status.NotStarted, 4),
        ]
    
        metadata = Metadata()
        metadata.people_allocations = {
            Person("Lewis"): 1,
            Person("John"): 1,
            Person("Jack"): 1,
        }
        metadata.teams = {
            "All": Team("All", [Person("Lewis"), Person("John"), Person("Jack")])
        }
    
        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        
        self.assertEqual(0, offset)
        self.assertEqual(8, makespan)

        # Try making it false
        tasks = [
            InputTask("BigTask", "BigTask", True, ["Lewis"], [], False, 7, None, None, Status.InProgress, 0),
            InputTask("TaskA", "TaskA", True, ["John"], ["TaskB"], False, 3, None, None, Status.InProgress, 1),
            InputTask("TaskB", "TaskB", True, ["Lewis"], ["TaskC"], False, 1, None, None, Status.NotStarted, 2),
            InputTask("TaskC", "TaskC", True, ["Jack"], ["Done"], False, 4, None, None, Status.NotStarted, 3),
            InputTask("Done", "Done", False, [], [], False, 0, None, None, Status.NotStarted, 4),
        ]

        _, makespan, offset = build_graph_and_schedule(tasks, metadata, [])
        
        self.assertEqual(0, offset)
        # Its 11 without parallelism
        self.assertEqual(11, makespan)

