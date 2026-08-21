"""Tests for Pillar 5: Interactive Developer Diagnostics and Deep-Dive Modal."""

import os
from unittest.mock import MagicMock, mock_open, patch

from visage.collectors.diagnostics import _mask_sensitive, collect_process_diagnostics
from visage.widgets.processes import ProcessInspectModal


class TestProcessDiagnostics:
    def test_mask_sensitive_tokens(self):
        assert _mask_sensitive("API_TOKEN", "abcdef123456") == "abc...456"
        assert _mask_sensitive("MY_SECRET_KEY", "123456789") == "123...789"
        assert _mask_sensitive("PASSWORD", "short") == "********"
        assert _mask_sensitive("PATH", "/usr/bin:/bin") == "/usr/bin:/bin"
        assert _mask_sensitive("USER", "developer") == "developer"

    def test_collect_diagnostics_for_current_process(self):
        pid = os.getpid()
        diag = collect_process_diagnostics(pid)
        assert diag["available"] is True
        assert diag["pid"] == pid
        assert "memory" in diag
        assert "file_descriptors" in diag
        assert len(diag["file_descriptors"]) > 0
        assert "threads" in diag
        assert len(diag["threads"]) > 0

    def test_collect_diagnostics_nonexistent_pid(self):
        diag = collect_process_diagnostics(99999999)
        assert diag["available"] is False
        assert "not found" in diag.get("error", "").lower()

    def test_collect_diagnostics_mocked(self):
        sample_status = (
            "Name:\tpython_worker\n"
            "State:\tS (sleeping)\n"
            "PPid:\t100\n"
            "VmPeak:\t  500000 kB\n"
            "VmSize:\t  450000 kB\n"
            "VmRSS:\t   50000 kB\n"
            "Threads:\t4\n"
        )

        with patch("sys.platform", "linux"), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=sample_status)), \
             patch("os.listdir") as mock_listdir, \
             patch("os.readlink") as mock_readlink, \
             patch("visage.collectors.diagnostics.get_process_sockets", return_value=[
                 {"proto": "tcp", "local_addr": "127.0.0.1:8000", "remote_addr": "*:*", "state": "LISTEN", "inode": 5555}
             ]):

            mock_listdir.side_effect = [
                ["0", "1", "2", "3"],  # fd
                ["1001", "1002"],       # task
            ]
            mock_readlink.side_effect = [
                "/dev/pts/0",
                "socket:[5555]",
                "pipe:[6666]",
                "/tmp/app.log",
            ]

            diag = collect_process_diagnostics(1234)
            assert diag["available"] is True
            assert diag["name"] == "python_worker"
            assert diag["ppid"] == 100
            assert diag["memory"]["VmRSS"] == "50000 kB"
            assert diag["memory"]["VmSize"] == "450000 kB"
            assert len(diag["file_descriptors"]) == 4
            assert diag["file_descriptors"][1]["type"] == "Socket"
            assert diag["file_descriptors"][2]["type"] == "Pipe"
            assert diag["file_descriptors"][3]["type"] == "File"
            assert len(diag["sockets"]) == 1
            assert diag["sockets"][0]["local_addr"] == "127.0.0.1:8000"


class TestProcessInspectModal:
    def test_inspect_modal_tabs(self):
        diag_data = {
            "pid": 4321,
            "name": "my_daemon",
            "ppid": 1,
            "cmdline": ["my_daemon", "--port", "8080"],
            "memory": {"VmRSS": "32000 kB", "VmSize": "64000 kB"},
            "io": {"read_bytes": 10240, "write_bytes": 20480},
            "file_descriptors": [
                {"fd": "0", "type": "Device", "target": "/dev/null"},
                {"fd": "1", "type": "File", "target": "/tmp/out.log"},
            ],
            "sockets": [
                {"proto": "tcp", "local_addr": "0.0.0.0:8080", "remote_addr": "*:*", "state": "LISTEN", "tx_queue": 0, "rx_queue": 0}
            ],
            "threads": [
                {"tid": 4321, "name": "my_daemon", "state": "R"},
                {"tid": 4322, "name": "worker_1", "state": "S"},
            ],
            "environ": {"PORT": "8080", "API_KEY": "abc...123"},
        }

        with patch("visage.widgets.processes.collect_process_diagnostics", return_value=diag_data):
            modal = ProcessInspectModal(4321, "my_daemon")
            mock_content = MagicMock()
            modal._content = mock_content

            # Tab 1: Overview
            modal.action_tab_overview()
            assert modal.current_tab == 1
            mock_content.update.assert_called()

            # Tab 2: FDs
            modal.action_tab_fds()
            assert modal.current_tab == 2
            mock_content.update.assert_called()

            # Tab 3: Sockets
            modal.action_tab_sockets()
            assert modal.current_tab == 3
            mock_content.update.assert_called()

            # Tab 4: Threads
            modal.action_tab_threads()
            assert modal.current_tab == 4
            mock_content.update.assert_called()

            # Tab 5: Env
            modal.action_tab_env()
            assert modal.current_tab == 5
            mock_content.update.assert_called()
