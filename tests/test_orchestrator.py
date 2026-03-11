"""Tests for orchestrator heartbeat throttling."""
import threading
from unittest.mock import MagicMock, patch

from src.orchestrator import TabWorker


def _make_worker() -> TabWorker:
    transport = MagicMock()
    transport.poll_tab.return_value = None
    transport.initialize_tab_if_needed.return_value = None
    bridge = MagicMock()
    stop_event = threading.Event()
    return TabWorker("test-tab", transport, bridge, stop_event)


def _counting_poll(worker, max_polls):
    """Return a poll_tab side_effect that stops after max_polls iterations."""
    poll_count = 0

    def side_effect(*_args, **_kwargs):
        nonlocal poll_count
        poll_count += 1
        if poll_count >= max_polls:
            worker._stop_event.set()
        return None

    return side_effect


class TestHeartbeatThrottling:
    def test_heartbeat_called_on_first_poll(self):
        worker = _make_worker()
        worker._transport.poll_tab.side_effect = _counting_poll(worker, 1)

        with patch("src.orchestrator.time.sleep"):
            worker.run()

        worker._transport.write_heartbeat.assert_called_once_with("test-tab")

    def test_heartbeat_not_called_within_throttle_window(self):
        worker = _make_worker()
        worker._transport.poll_tab.side_effect = _counting_poll(worker, 2)

        current_time = [100.0]

        def fake_monotonic():
            return current_time[0]

        def advance_on_poll(*_args, **_kwargs):
            pass

        original_side_effect = worker._transport.poll_tab.side_effect

        def poll_with_time_advance(*args, **kwargs):
            result = original_side_effect(*args, **kwargs)
            # Advance 5s between polls (within 30s window).
            current_time[0] += 5.0
            return result

        worker._transport.poll_tab.side_effect = poll_with_time_advance

        with patch("src.orchestrator.time.sleep"):
            with patch("src.orchestrator.time.monotonic", side_effect=fake_monotonic):
                worker.run()

        assert worker._transport.write_heartbeat.call_count == 1

    def test_heartbeat_called_after_throttle_window(self):
        worker = _make_worker()
        worker._transport.poll_tab.side_effect = _counting_poll(worker, 2)

        current_time = [100.0]

        def fake_monotonic():
            return current_time[0]

        original_side_effect = worker._transport.poll_tab.side_effect

        def poll_with_time_advance(*args, **kwargs):
            result = original_side_effect(*args, **kwargs)
            # Advance 31s between polls (past 30s window).
            current_time[0] += 31.0
            return result

        worker._transport.poll_tab.side_effect = poll_with_time_advance

        with patch("src.orchestrator.time.sleep"):
            with patch("src.orchestrator.time.monotonic", side_effect=fake_monotonic):
                worker.run()

        assert worker._transport.write_heartbeat.call_count == 2
