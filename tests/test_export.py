"""Tests for visage.export.exporter."""

import json
import os
import tempfile

from visage.export.exporter import export_csv, export_json, export_log


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


class TestExportJson:
    def test_writes_json_file(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # file should not exist yet
        try:
            result = export_json({"cpu": 50.0, "mem": 2048}, path)
            assert str(result) == path
            with open(path) as f:
                data = json.load(f)
            assert data["cpu"] == 50.0
            assert data["mem"] == 2048
            assert "timestamp" in data
        finally:
            _cleanup(path)

    def test_handles_non_serializable_with_default(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)
        try:
            result = export_json({"obj": b"bytes_data"}, path)
            assert str(result) == path
            with open(path) as f:
                data = json.load(f)
            assert data["obj"] == "b'bytes_data'"
        finally:
            _cleanup(path)


class TestExportCsv:
    def test_writes_csv_with_header(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        os.unlink(path)
        try:
            rows = [{"name": "cpu", "value": 50}, {"name": "mem", "value": 70}]
            result = export_csv(rows, path)
            assert str(result) == path
            with open(path) as f:
                content = f.read()
            assert "name,value" in content
            assert "cpu,50" in content
            assert "mem,70" in content
        finally:
            _cleanup(path)

    def test_appends_to_existing_file(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        with open(path, "w") as f:
            f.write("name,value\n")
        try:
            rows = [{"name": "disk", "value": 80}]
            export_csv(rows, path, fieldnames=["name", "value"])
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert lines[1].strip() == "disk,80"
        finally:
            _cleanup(path)

    def test_empty_rows_no_crash(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        os.unlink(path)
        try:
            result = export_csv([], path)
            assert str(result) == path
        finally:
            _cleanup(path)


class TestExportLog:
    def test_appends_timestamped_line(self):
        fd, path = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        os.unlink(path)
        try:
            export_log("hello world", path)
            with open(path) as f:
                line = f.read().strip()
            assert "hello world" in line
            assert line.startswith("[")
        finally:
            _cleanup(path)

    def test_appends_to_existing_log(self):
        fd, path = tempfile.mkstemp(suffix=".log")
        os.close(fd)
        with open(path, "w") as f:
            f.write("existing\n")
        try:
            export_log("line2", path)
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert "line2" in lines[1]
        finally:
            _cleanup(path)
