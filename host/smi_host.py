#!/usr/bin/env python3
"""
smi_host.py - Chrome Native Messaging Host for NVIDIA SMI Telemetry.

Reads length-prefixed JSON requests from Chrome on standard input,
queries local GPU status safely without shell execution, and sends
back length-prefixed JSON responses on standard output.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys

MAX_PAYLOAD_BYTES = 1024 * 1024  # 1 MB limit (Chrome Native Messaging ceiling)
ALLOWED_ACTIONS = frozenset({"get_gpu", "ping"})


def read_message(stream=None) -> dict | None:
    """Reads a Chrome Native Messaging 32-bit length-prefixed JSON message from stdin or stream."""
    in_stream = stream if stream is not None else sys.stdin.buffer
    raw_length = in_stream.read(4)
    if not raw_length or len(raw_length) < 4:
        return None

    msg_len = struct.unpack("=I", raw_length)[0]
    if msg_len > MAX_PAYLOAD_BYTES:
        raise ValueError(f"Message length {msg_len} exceeds max payload limit of {MAX_PAYLOAD_BYTES} bytes")

    raw_data = in_stream.read(msg_len)
    if len(raw_data) < msg_len:
        return None

    return json.loads(raw_data.decode("utf-8"))


def send_message(payload: dict, stream=None) -> None:
    """Writes a Chrome Native Messaging 32-bit length-prefixed JSON message to stdout or stream."""
    out_stream = stream if stream is not None else sys.stdout.buffer
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    length_header = struct.pack("=I", len(encoded))
    out_stream.write(length_header)
    out_stream.write(encoded)
    out_stream.flush()


def query_nvidia_smi() -> dict:
    """Queries nvidia-smi via subprocess with shell=False for hardware telemetry."""
    smi_executable = shutil.which("nvidia-smi")
    if not smi_executable:
        # Check standard Windows path if not in system PATH
        win_default = os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"
        )
        if os.path.exists(win_default):
            smi_executable = win_default

    if not smi_executable:
        return {
            "status": "unavailable",
            "error": "nvidia-smi executable not found in PATH or standard system directories"
        }

    cmd = [
        smi_executable,
        "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits"
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
            timeout=3.0
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "nvidia-smi command timed out"}
    except (subprocess.CalledProcessError, OSError) as exc:
        return {"status": "error", "error": f"nvidia-smi execution failed: {exc}"}

    lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
    if not lines:
        return {"status": "empty", "error": "No GPU detected or empty output from nvidia-smi"}

    gpus = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 7:
            try:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "gpu_util_pct": float(parts[2]),
                    "vram_used_mb": float(parts[3]),
                    "vram_total_mb": float(parts[4]),
                    "temperature_c": float(parts[5]),
                    "power_w": float(parts[6]),
                })
            except ValueError:
                continue

    if not gpus:
        return {"status": "parse_error", "error": "Failed to parse nvidia-smi CSV output"}

    # Primary GPU is first entry
    primary = gpus[0]
    return {
        "status": "ok",
        "gpu": primary,
        "all_gpus": gpus,
        "count": len(gpus)
    }


def handle_request(req: dict) -> dict:
    """Dispatches validated incoming requests to safe handlers."""
    if not isinstance(req, dict):
        return {"status": "error", "error": "Invalid request: payload must be a JSON object"}

    action = req.get("action")
    if action not in ALLOWED_ACTIONS:
        return {
            "status": "error",
            "error": f"Rejected unauthorized action '{action}'. Permitted: {sorted(ALLOWED_ACTIONS)}"
        }

    if action == "ping":
        return {"status": "ok", "message": "pong", "version": "1.0.0"}

    if action == "get_gpu":
        return query_nvidia_smi()

    return {"status": "error", "error": "Unhandled action"}


def main() -> None:
    """Main event loop listening for Chrome Native Messaging packets."""
    # Ensure standard streams operate in unbuffered binary mode
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

    while True:
        try:
            req = read_message()
            if req is None:
                break  # EOF / Chrome closed connection
            resp = handle_request(req)
            send_message(resp)
        except Exception as exc:
            try:
                send_message({"status": "fatal_error", "error": str(exc)})
            except Exception:
                pass
            break


if __name__ == "__main__":
    main()
