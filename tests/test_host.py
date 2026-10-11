#!/usr/bin/env python3
"""
test_host.py - Unit test suite for Native Messaging Host protocol & security.
"""

import io
import json
import struct
import unittest
from unittest.mock import patch, MagicMock

import sys
import os

# Add host directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "host")))

import smi_host


class TestNativeMessagingHost(unittest.TestCase):

    def test_message_framing_encode_decode(self):
        """Verify that length-prefixed protocol packaging strictly adheres to Chrome spec."""
        payload = {"action": "ping", "test_val": 42}
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        raw_stream = struct.pack("=I", len(encoded)) + encoded

        stream = io.BytesIO(raw_stream)
        decoded = smi_host.read_message(stream=stream)
        self.assertEqual(decoded, payload)

        # Test writing
        out_stream = io.BytesIO()
        smi_host.send_message(payload, stream=out_stream)
        out_stream.seek(0)
        self.assertEqual(smi_host.read_message(stream=out_stream), payload)

    def test_oversized_payload_rejection(self):
        """Adversarial test: An oversized message length must be aborted to prevent DoS."""
        oversized_len = struct.pack("=I", smi_host.MAX_PAYLOAD_BYTES + 500)
        stream = io.BytesIO(oversized_len)
        with self.assertRaises(ValueError) as ctx:
            smi_host.read_message(stream=stream)
        self.assertIn("exceeds max payload limit", str(ctx.exception))

    def test_unauthorized_action_rejection(self):
        """Adversarial test: Arbitrary action strings must be blocked with error."""
        attack_req = {"action": "exec", "cmd": "notepad.exe"}
        resp = smi_host.handle_request(attack_req)
        self.assertEqual(resp["status"], "error")
        self.assertIn("Rejected unauthorized action", resp["error"])

    def test_ping_action(self):
        """Test ping/pong health check."""
        resp = smi_host.handle_request({"action": "ping"})
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["message"], "pong")

    @patch("subprocess.run")
    @patch("shutil.which", return_value="nvidia-smi")
    def test_query_nvidia_smi_success(self, mock_which, mock_run):
        """Test parsing valid nvidia-smi CSV telemetry output."""
        mock_proc = MagicMock()
        mock_proc.stdout = "0, NVIDIA GeForce RTX 4090, 45.0, 8192.0, 24576.0, 58.0, 185.5\n"
        mock_run.return_value = mock_proc

        result = smi_host.query_nvidia_smi()
        self.assertEqual(result["status"], "ok")
        gpu = result["gpu"]
        self.assertEqual(gpu["index"], 0)
        self.assertEqual(gpu["name"], "NVIDIA GeForce RTX 4090")
        self.assertEqual(gpu["gpu_util_pct"], 45.0)
        self.assertEqual(gpu["vram_used_mb"], 8192.0)
        self.assertEqual(gpu["vram_total_mb"], 24576.0)
        self.assertEqual(gpu["temperature_c"], 58.0)
        self.assertEqual(gpu["power_w"], 185.5)

    @patch("shutil.which", return_value=None)
    @patch("os.path.exists", return_value=False)
    def test_query_nvidia_smi_missing(self, mock_exists, mock_which):
        """Test graceful degradation when nvidia-smi is not found."""
        result = smi_host.query_nvidia_smi()
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("not found", result["error"])


if __name__ == "__main__":
    unittest.main()
