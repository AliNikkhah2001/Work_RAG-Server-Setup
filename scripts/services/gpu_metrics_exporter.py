#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal Prometheus exporter for nvidia-smi metrics (GPU util/mem/temp/power).

Exposes on :9101/metrics. Pure stdlib, runs on the host (no container/DCGM).
"""
import http.server
import subprocess
import time

METRICS = [
    ("gpu_utilization_percent", "gauge", "GPU utilization %"),
    ("gpu_memory_used_mb", "gauge", "GPU memory used MiB"),
    ("gpu_memory_total_mb", "gauge", "GPU memory total MiB"),
    ("gpu_temperature_celsius", "gauge", "GPU temperature C"),
    ("gpu_power_watts", "gauge", "GPU power draw W"),
]

QUERY = [
    "utilization.gpu",
    "memory.used",
    "memory.total",
    "temperature.gpu",
    "power.draw",
]
HEADERS = "index," + ",".join(QUERY)

BASE = time.time()


def collect():
    out = subprocess.run(
        ["nvidia-smi", f"--query-gpu={HEADERS}", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
    rows = []
    for line in out:
        parts = [p.strip() for p in line.split(",")]
        g = parts[0]
        for m in range(len(METRICS)):
            rows.append(f"{METRICS[m][0]}{{gpu=\"{g}\"}} {parts[1 + m]}")
    return rows


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404); self.end_headers(); return
        body = "\n".join(collect()).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 9101), Handler).serve_forever()
