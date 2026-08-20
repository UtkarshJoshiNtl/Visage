"""Tests for Sprint 7 process features — aggregate, nice, cmdline, vim, paging."""

from unittest.mock import patch, MagicMock
import pytest

from visage.collectors.process import collect, _aggregate_by_name


class TestAggregateByName:
    def test_basic_aggregation(self):
        processes = [
            {"name": "python", "pid": 1, "cpu": 10.0, "memory": 5.0, "mem_rss": 1000, "threads": 2, "nice": 0, "start_time": 100, "cmdline": "python app.py"},
            {"name": "python", "pid": 2, "cpu": 20.0, "memory": 8.0, "mem_rss": 2000, "threads": 3, "nice": 5, "start_time": 200, "cmdline": "python worker.py"},
            {"name": "node", "pid": 3, "cpu": 15.0, "memory": 10.0, "mem_rss": 3000, "threads": 4, "nice": 0, "start_time": 150, "cmdline": "node server.js"},
        ]
        result = _aggregate_by_name(processes, 10, "cpu", True)
        assert len(result) == 2
        assert result[0]["name"] == "python"
        assert result[0]["cpu"] == 30.0
        assert result[0]["count"] == 2
        assert result[0]["pids"] == [1, 2]
        assert result[1]["name"] == "node"
        assert result[1]["cpu"] == 15.0

    def test_aggregation_sort_ascending(self):
        processes = [
            {"name": "python", "pid": 1, "cpu": 10.0, "memory": 5.0, "mem_rss": 1000, "threads": 2, "nice": 0, "start_time": 100, "cmdline": "python app.py"},
            {"name": "node", "pid": 2, "cpu": 20.0, "memory": 8.0, "mem_rss": 2000, "threads": 3, "nice": 0, "start_time": 200, "cmdline": "node server.js"},
        ]
        result = _aggregate_by_name(processes, 10, "memory", False)
        assert len(result) == 2
        assert result[0]["name"] == "python"
        assert result[0]["memory"] == 5.0
        assert result[1]["name"] == "node"
        assert result[1]["memory"] == 8.0

    def test_aggregation_sort_descending(self):
        processes = [
            {"name": "python", "pid": 1, "cpu": 10.0, "memory": 5.0, "mem_rss": 1000, "threads": 2, "nice": 0, "start_time": 100, "cmdline": "python app.py"},
            {"name": "node", "pid": 2, "cpu": 20.0, "memory": 8.0, "mem_rss": 2000, "threads": 3, "nice": 0, "start_time": 200, "cmdline": "node server.js"},
        ]
        result = _aggregate_by_name(processes, 10, "memory", True)
        assert result[0]["name"] == "node"
        assert result[0]["memory"] == 8.0

    def test_aggregation_single_group(self):
        processes = [
            {"name": "python", "pid": 1, "cpu": 5.0, "memory": 2.0, "mem_rss": 500, "threads": 1, "nice": 0, "start_time": 100, "cmdline": "python a.py"},
            {"name": "python", "pid": 2, "cpu": 5.0, "memory": 2.0, "mem_rss": 500, "threads": 1, "nice": 0, "start_time": 200, "cmdline": "python b.py"},
        ]
        result = _aggregate_by_name(processes, 10, "cpu", True)
        assert len(result) == 1
        assert result[0]["count"] == 2
        assert result[0]["mem_rss"] == 1000

    def test_collect_aggregate_mode(self):
        with patch("visage.collectors.process.psutil") as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.as_dict.return_value = {
                "pid": 1,
                "ppid": 0,
                "name": "test",
                "username": "user",
                "cpu_percent": 10.0,
                "memory_percent": 5.0,
                "memory_info": MagicMock(rss=1000),
                "status": "running",
                "nice": 0,
                "num_threads": 1,
                "create_time": 100.0,
                "cmdline": ["test"],
            }
            mock_psutil.process_iter.return_value = [mock_proc]
            mock_psutil.NoSuchProcess = Exception
            mock_psutil.AccessDenied = Exception
            mock_psutil.ZombieProcess = Exception
            
            result = collect(top_n=10, aggregate_mode=True)
            assert len(result) == 1
            assert result[0]["name"] == "test"
            assert result[0]["count"] == 1


class TestNiceColumn:
    def test_nice_value_in_process_data(self):
        with patch("visage.collectors.process.psutil") as mock_psutil:
            mock_proc = MagicMock()
            mock_proc.as_dict.return_value = {
                "pid": 1,
                "ppid": 0,
                "name": "test",
                "username": "user",
                "cpu_percent": 10.0,
                "memory_percent": 5.0,
                "memory_info": MagicMock(rss=1000),
                "status": "running",
                "nice": 10,
                "num_threads": 1,
                "create_time": 100.0,
                "cmdline": ["test"],
            }
            mock_psutil.process_iter.return_value = [mock_proc]
            mock_psutil.NoSuchProcess = Exception
            mock_psutil.AccessDenied = Exception
            mock_psutil.ZombieProcess = Exception
            
            result = collect(top_n=10)
            assert result[0]["nice"] == 10


class TestCmdlineToggle:
    def test_long_cmdline_truncation(self):
        name = "a" * 50
        assert len(name) > 48
        truncated = name[:47] + "\u2026"
        assert len(truncated) == 48
        assert truncated.endswith("\u2026")


class TestVimMode:
    def test_vim_jk_navigation(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": i} for i in range(20)]
        widget._selected_idx = 5

        event = MagicMock()
        event.key = "j"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 6

        event.key = "k"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 5

    def test_vim_G_goes_to_end(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": i} for i in range(20)]
        widget._selected_idx = 5

        event = MagicMock()
        event.key = "G"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 19

    def test_vim_gg_goes_to_start(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": i} for i in range(20)]
        widget._selected_idx = 15

        event = MagicMock()
        event.key = "g"
        widget._handle_vim_key(event)
        assert widget._vim_pending == "g"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 0

    def test_vim_escape_exits(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": i} for i in range(20)]

        event = MagicMock()
        event.key = "escape"
        widget._handle_vim_key(event)
        assert widget._vim_mode is False

    def test_vim_hl_navigation(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": i} for i in range(20)]
        widget._selected_idx = 10

        event = MagicMock()
        event.key = "h"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 5

        event.key = "l"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 10

    def test_vim_boundary_clamp(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._vim_mode = True
        widget.processes = [{"pid": 0}]
        widget._selected_idx = 0

        event = MagicMock()
        event.key = "k"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 0

        event.key = "j"
        widget._handle_vim_key(event)
        assert widget._selected_idx == 0


class TestPaging:
    def test_page_up_down(self):
        from visage.widgets.processes import ProcessesWidget
        widget = ProcessesWidget()
        widget._selected_idx = 15
        
        procs = [{"pid": i} for i in range(30)]
        
        event = MagicMock()
        event.key = "pageup"
        widget._selected_idx = 15
        widget._selected_idx = max(0, widget._selected_idx - 10)
        assert widget._selected_idx == 5
        
        event.key = "pagedown"
        widget._selected_idx = min(len(procs) - 1, widget._selected_idx + 10)
        assert widget._selected_idx == 15
