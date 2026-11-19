"""Reject forced/partial stops, and distinguish a stopped server from its shell."""
import io
import subprocess
import unittest
from unittest.mock import Mock

from scripts.acceptance_process import application_pid,release_idle_wrapper,wait_for_shutdown


class AcceptanceProcessTests(unittest.TestCase):
    def test_closed_port_and_completed_log_do_not_accept_a_live_application(self):
        with self.assertRaisesRegex(RuntimeError,'not verified'):
            wait_for_shutdown(lambda:dict(application_exited=False,port_closed=True,shutdown_log_complete=True),timeout=0)

    def test_an_exited_application_with_no_clean_shutdown_log_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'not verified'):
            wait_for_shutdown(lambda:dict(application_exited=True,port_closed=True,shutdown_log_complete=False),timeout=0)

    def test_blocked_shell_can_close_only_after_all_application_evidence(self):
        states=iter([dict(application_exited=False,port_closed=False,shutdown_log_complete=False),
                     dict(application_exited=True,port_closed=True,shutdown_log_complete=True)])
        evidence=wait_for_shutdown(lambda:next(states),timeout=1,poll=0)
        process=Mock(pid=1234,stdin=io.BytesIO())
        process.poll.return_value=None
        process.wait.side_effect=[subprocess.TimeoutExpired('owned cmd',3),0]
        result=release_idle_wrapper(process,application_verified_stopped=all(evidence.values()))
        self.assertIn('after_verified_application_exit',result)
        process.terminate.assert_called_once()
        process.kill.assert_not_called()

    def test_wrapper_cannot_be_closed_to_turn_a_live_application_into_a_pass(self):
        process=Mock()
        with self.assertRaisesRegex(RuntimeError,'Refusing'):
            release_idle_wrapper(process,application_verified_stopped=False)
        process.terminate.assert_not_called()
        self.assertEqual(application_pid('Started server process [101]\nStarted server process [202]'),202)
        with self.assertRaisesRegex(RuntimeError,'missing'):
            application_pid('Application shutdown complete.')
