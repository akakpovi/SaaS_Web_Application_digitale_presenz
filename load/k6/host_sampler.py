#!/usr/bin/env python3
"""Sample host CPU, RAM and load average while k6 runs.

Usage: python3 host_sampler.py <output.csv> <duration_seconds> [interval]

Only reads /proc; no dependency. CPU usage is computed from the delta of
/proc/stat, so the first sample is skipped. At the end the CSV is summarised
on stdout (avg/max CPU, max RAM used, max load average).
"""

from __future__ import annotations

import csv
import os
import sys
import time

FIELDS = ["timestamp", "cpu_percent", "mem_used_mb", "mem_total_mb", "load1"]


def cpu_times() -> tuple[int, int]:
    with open("/proc/stat", encoding="ascii") as handle:
        parts = handle.readline().split()[1:]
    values = [int(value) for value in parts]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    return idle, total


def mem() -> tuple[int, int]:
    info: dict[str, int] = {}
    with open("/proc/meminfo", encoding="ascii") as handle:
        for line in handle:
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0])
    total = info["MemTotal"] // 1024
    available = info.get("MemAvailable", info.get("MemFree", 0)) // 1024
    return total - available, total


def load1() -> float:
    return os.getloadavg()[0]


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path = sys.argv[1]
    duration = float(sys.argv[2])
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    start = time.time()
    previous = cpu_times()
    rows: list[dict] = []

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        while time.time() - start < duration:
            time.sleep(interval)
            current = cpu_times()
            idle_delta = current[0] - previous[0]
            total_delta = current[1] - previous[1]
            previous = current
            cpu_percent = (
                100.0 * (1 - idle_delta / total_delta) if total_delta else 0.0
            )
            used, total = mem()
            row = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "cpu_percent": round(cpu_percent, 2),
                "mem_used_mb": used,
                "mem_total_mb": total,
                "load1": round(load1(), 2),
            }
            writer.writerow(row)
            rows.append(row)

    if not rows:
        print("no sample collected")
        return 1

    cpu_values = [row["cpu_percent"] for row in rows]
    mem_values = [row["mem_used_mb"] for row in rows]
    load_values = [row["load1"] for row in rows]
    print(f"samples={len(rows)}")
    print(f"cpu_avg={sum(cpu_values) / len(cpu_values):.1f}%")
    print(f"cpu_max={max(cpu_values):.1f}%")
    print(f"mem_avg={sum(mem_values) / len(mem_values):.0f}MB")
    print(f"mem_max={max(mem_values)}MB / {rows[0]['mem_total_mb']}MB")
    print(f"load1_avg={sum(load_values) / len(load_values):.2f}")
    print(f"load1_max={max(load_values):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
