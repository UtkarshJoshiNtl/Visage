"""Tests for Pillar 2: eBPF Socket-Level Network Attribution & Socket Inode Tracking."""

from unittest.mock import MagicMock, mock_open, patch

from visage.collectors.network import (
    _hex_to_ip_port,
    collect_per_process,
    get_process_socket_inodes,
    get_process_sockets,
    parse_socket_tables,
)
from visage.tracing.tracer import EbpfNetTracer, get_ebpf_net_tracer


class TestNetworkSocketParsing:
    def test_hex_to_ip_port_ipv4(self):
        # 0100007F:0050 -> 127.0.0.1:80
        ip, port = _hex_to_ip_port("0100007F:0050")
        assert ip == "127.0.0.1"
        assert port == 80

        # 00000000:1F90 -> 0.0.0.0:8080
        ip, port = _hex_to_ip_port("00000000:1F90")
        assert ip == "0.0.0.0"
        assert port == 8080

    def test_hex_to_ip_port_invalid(self):
        ip, port = _hex_to_ip_port("invalid")
        assert ip == "?"
        assert port == 0

    def test_parse_socket_tables(self):
        sample_proc_net_tcp = (
            "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
            "   0: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 123456 1 0000000000000000 100 0 0 10 0\n"
            "   1: 0100007F:1F90 0100007F:A123 01 00000010:00000020 00:00000000 00000000  1000        0 123457 1 0000000000000000 100 0 0 10 0\n"
        )

        with patch("sys.platform", "linux"), \
             patch("builtins.open", mock_open(read_data=sample_proc_net_tcp)):
            sockets = parse_socket_tables()
            assert 123456 in sockets
            s0 = sockets[123456]
            assert s0["local_addr"] == "127.0.0.1:8080"
            assert s0["remote_addr"] == "*:*"
            assert s0["state"] == "LISTEN"

            assert 123457 in sockets
            s1 = sockets[123457]
            assert s1["local_addr"] == "127.0.0.1:8080"
            assert s1["remote_addr"] == "127.0.0.1:41251"
            assert s1["state"] == "ESTABLISHED"
            assert s1["tx_queue"] == 16
            assert s1["rx_queue"] == 32

    def test_get_process_socket_inodes(self):
        with patch("sys.platform", "linux"), \
             patch("os.listdir", return_value=["0", "1", "2", "3"]), \
             patch("os.readlink") as mock_readlink:
            mock_readlink.side_effect = [
                "/dev/null",
                "socket:[123456]",
                "/var/log/app.log",
                "socket:[123457]",
            ]
            inodes = get_process_socket_inodes(9999)
            assert inodes == [123456, 123457]

    def test_get_process_sockets(self):
        with patch("visage.collectors.network.get_process_socket_inodes", return_value=[123456]), \
             patch("visage.collectors.network.parse_socket_tables", return_value={
                 123456: {
                     "proto": "tcp",
                     "local_addr": "127.0.0.1:8080",
                     "remote_addr": "*:*",
                     "state": "LISTEN",
                     "inode": 123456,
                 }
             }):
            sockets = get_process_sockets(9999)
            assert len(sockets) == 1
            assert sockets[0]["local_addr"] == "127.0.0.1:8080"
            assert sockets[0]["state"] == "LISTEN"


class TestEbpfNetTracer:
    def test_ebpf_tracer_unavailable_graceful(self):
        tracer = EbpfNetTracer()
        # When BCC is not installed, start() returns False without crashing
        with patch.dict("sys.modules", {"bcc": None}):
            assert tracer.start() is False
            assert tracer.available is False
            assert tracer.get_stats() == {}
            tracer.stop()

    def test_ebpf_tracer_stats_mock(self):
        tracer = EbpfNetTracer()
        mock_bpf = MagicMock()
        mock_flow = {
            MagicMock(value=1001): MagicMock(rx_bytes=1048576, tx_bytes=2097152),
            MagicMock(value=1002): MagicMock(rx_bytes=51200, tx_bytes=102400),
        }
        mock_bpf.__getitem__.return_value.items.return_value = mock_flow.items()

        tracer._bpf = mock_bpf
        tracer._active = True

        stats = tracer.get_stats()
        assert 1001 in stats
        assert stats[1001]["rx_bytes"] == 1048576
        assert stats[1001]["tx_bytes"] == 2097152
        assert 1002 in stats
        assert stats[1002]["rx_bytes"] == 51200
        assert stats[1002]["tx_bytes"] == 102400

    def test_collect_per_process_with_ebpf(self):
        mock_tracer = MagicMock()
        mock_tracer.available = True
        mock_tracer.get_stats.return_value = {
            1001: {"rx_bytes": 500000, "tx_bytes": 1000000},
        }

        mock_p1 = MagicMock()
        mock_p1.info = {"pid": 1001, "name": "web_server"}

        with patch("sys.platform", "linux"), \
             patch("visage.tracing.tracer.get_ebpf_net_tracer", return_value=mock_tracer), \
             patch("psutil.process_iter", return_value=[mock_p1]):
            results = collect_per_process(top_n=5)
            assert len(results) == 1
            assert results[0]["pid"] == 1001
            assert results[0]["name"] == "web_server"
            assert results[0]["rx_bytes"] == 500000
            assert results[0]["tx_bytes"] == 1000000
            assert results[0]["method"] == "ebpf"
