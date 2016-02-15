import unittest
from sismic import io
from sismic.interpreter import Interpreter
from sismic.stories import Story, Pause, Event
from sismic.testing import teststory_from_trace
from sismic.testing.tester import ExecutionWatcher


class StoryFromTraceTests(unittest.TestCase):
    def test_simple(self):
        with open('tests/yaml/simple.yaml') as f:
            sc = io.import_from_yaml(f)
        interpreter = Interpreter(sc)

        trace = Story([Pause(2), Event('goto s2'), Pause(3)]).tell(interpreter)
        story = teststory_from_trace(trace)

        expected = Story([
            Event('started'),
            Pause(2),
            Event('step'),
            Event('entered', entered_state='root'),
            Event('entered', entered_state='s1'),
            Event('step'),
            Event('consumed', consumed_event=Event('goto s2')),
            Event('exited', exited_state='s1'),
            Event('processed', source_state='s1', target_state='s2', consumed_event=Event('goto s2')),
            Event('entered', entered_state='s2'),
            Event('step'),
            Event('exited', exited_state='s2'),
            Event('processed', source_state='s2', target_state='s3', consumed_event=None),
            Event('entered', entered_state='s3'),
            Event('stopped')
        ])
        for a, b in zip(story, expected):
            self.assertEqual(a, b)
            if isinstance(a, Event):
                self.assertEqual(a.data.items(), b.data.items())
            else:
                self.assertEqual(a.duration, b.duration)


class ElevatorStoryTests(unittest.TestCase):
    def setUp(self):
        with open('docs/examples/elevator.yaml') as f:
            sc = io.import_from_yaml(f)
        self.tested = Interpreter(sc)

    def test_7th_floor_never_reached(self):
        story = Story([Event('floorSelected', floor=8)])
        trace = story.tell(self.tested)

        test_story = teststory_from_trace(trace)

        with open('docs/examples/tester_elevator_7th_floor_never_reached.yaml') as f:
            tester = Interpreter(io.import_from_yaml(f))
        test_story.tell(tester)
        self.assertTrue(tester.final)

    def test_7th_floor_never_reached_fails(self):
        story = Story([Event('floorSelected', floor=4), Pause(2), Event('floorSelected', floor=7)])
        trace = story.tell(self.tested)

        test_story = teststory_from_trace(trace)

        with open('docs/examples/tester_elevator_7th_floor_never_reached.yaml') as f:
            tester = Interpreter(io.import_from_yaml(f))
        test_story.tell(tester)
        self.assertFalse(tester.final)

    def test_elevator_moves_after_10s(self):
        stories = [
            Story([Event('floorSelected', floor=4)]),
            Story([Event('floorSelected', floor=0)]),
            Story([Event('floorSelected', floor=4), Pause(10)]),
            Story([Event('floorSelected', floor=0), Pause(10)]),
            Story([Event('floorSelected', floor=4), Pause(9)]),
            Story([Event('floorSelected', floor=0), Pause(9)]),
        ]

        for story in stories:
            with self.subTest(story=story):
                # Reopen because we need to reset it
                with open('docs/examples/elevator.yaml') as f:
                    sc = io.import_from_yaml(f)
                tested = Interpreter(sc)

                test_story = teststory_from_trace(story.tell(tested))

                with open('docs/examples/tester_elevator_moves_after_10s.yaml') as f:
                    tester = Interpreter(io.import_from_yaml(f))
                test_story.tell(tester)
                self.assertTrue(tester.final)


class WatchElevatorTests(unittest.TestCase):
    def setUp(self):
        with open('docs/examples/elevator.yaml') as f:
            sc = io.import_from_yaml(f)
        self.tested = Interpreter(sc)
        self.watcher = ExecutionWatcher(self.tested)

    def test_7th_floor_never_reached(self):
        with open('docs/examples/tester_elevator_7th_floor_never_reached.yaml') as f:
            tester_sc = io.import_from_yaml(f)

        tester = self.watcher.watch_with(tester_sc)
        self.watcher.start()

        # Send elevator to 4th
        self.tested.queue(Event('floorSelected', floor=4)).execute()
        self.watcher.stop()
        self.assertTrue(tester.final)

    def test_7th_floor_never_reached_fails(self):
        with open('docs/examples/tester_elevator_7th_floor_never_reached.yaml') as f:
            tester_sc = io.import_from_yaml(f)

        tester = self.watcher.watch_with(tester_sc)
        self.watcher.start()

        # Send elevator to 7th
        self.tested.queue(Event('floorSelected', floor=7)).execute()
        self.watcher.stop()
        self.assertFalse(tester.final)

    def test_destination_reached(self):
        with open('docs/examples/tester_elevator_destination_reached.yaml') as f:
            tester_statechart = io.import_from_yaml(f)

        # Create the interpreter and the watcher
        watcher = ExecutionWatcher(self.tested)

        # Add the tester and start watching
        tester = watcher.watch_with(tester_statechart)
        watcher.start()

        # Send the elevator to 4th
        self.tested.queue(Event('floorSelected', floor=4)).execute(max_steps=2)
        self.assertEqual(tester.context['destinations'], [4])

        self.tested.execute()
        self.assertEqual(tester.context['destinations'], [])

        # Stop watching. The tester must be in a final state
        watcher.stop()

        self.assertTrue(tester.final)