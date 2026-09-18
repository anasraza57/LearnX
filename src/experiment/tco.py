"""
Total cost of ownership for local backends.

Reviewer 4.10 objected to reporting a locally hosted model as free. It is not:
it draws power and it occupies hardware that was bought and wears out. This
computes what a local run actually costs from three measured or declared inputs:

- **compute time**, taken from the recorded per-call latencies (on a local
  backend the model is the only load, so call time is machine time);
- **power draw**, measured once with `powermetrics`, which needs sudo, so it is
  a step the author runs rather than something inferred;
- **hardware and tariff**, declared by the author in data/tco/hardware.json.

Anything not measured or declared is reported as missing. Nothing here invents a
power figure or a hardware price, because a total cost of ownership built from
guessed inputs is exactly the sort of number this revision exists to remove.

Usage:
    python -m src.experiment.tco power --seconds 60      # needs sudo; do it during a run
    python -m src.experiment.tco report --experiment e2 --model mistral:7b
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from .runner import EXPERIMENT_DIRS, RESULTS_DIR, model_slug

TCO_DIR = config.paths.data_dir / "tco"
POWER_PATH = TCO_DIR / "power.json"
HARDWARE_PATH = TCO_DIR / "hardware.json"

HARDWARE_TEMPLATE = {
    "_comment": "Fill these in from the actual purchase and tariff; leave a value null to omit it.",
    "machine": platform.platform(),
    "purchase_price_usd": None,
    "useful_life_years": 4,
    "electricity_price_per_kwh_usd": None,
    "hours_in_service_per_year": 8760,
}

# powermetrics prints a combined figure on Apple silicon; older builds print the
# parts, so both are parsed.
COMBINED_POWER = re.compile(r"Combined Power \(CPU \+ GPU \+ ANE\):\s*([\d.]+)\s*mW")
PART_POWER = re.compile(r"^(CPU|GPU|ANE) Power:\s*([\d.]+)\s*mW", re.MULTILINE)


def measure_power(seconds: int = 60, interval_ms: int = 1000) -> Dict[str, Any]:
    """
    Sample package power with powermetrics. Run this while a local arm is
    generating, so the figure reflects the load being measured.
    """
    command = ["sudo", "-n", "powermetrics", "--samplers", "cpu_power,gpu_power",
               "-i", str(interval_ms), "-n", str(max(1, seconds * 1000 // interval_ms))]
    try:
        output = subprocess.run(command, capture_output=True, text=True, timeout=seconds + 60).stdout
    except subprocess.TimeoutExpired:
        sys.exit("powermetrics timed out")
    except FileNotFoundError:
        sys.exit("powermetrics not found: this measurement is macOS only")

    samples = [float(v) for v in COMBINED_POWER.findall(output)]
    if not samples:
        parts: Dict[str, List[float]] = {}
        for name, value in PART_POWER.findall(output):
            parts.setdefault(name, []).append(float(value))
        if parts:
            length = min(len(v) for v in parts.values())
            samples = [sum(parts[name][i] for name in parts) for i in range(length)]
    if not samples:
        sys.exit("No power samples parsed. powermetrics needs sudo: run "
                 "'sudo -v' first, then this command again.")

    reading = {
        "measured_at": __import__("datetime").datetime.now().astimezone().isoformat(),
        "machine": platform.platform(),
        "samples": len(samples),
        "mean_package_power_w": statistics.fmean(samples) / 1000,
        "median_package_power_w": statistics.median(samples) / 1000,
        "max_package_power_w": max(samples) / 1000,
        "note": "Package power (CPU + GPU + ANE) while the local backend was generating.",
    }
    TCO_DIR.mkdir(parents=True, exist_ok=True)
    POWER_PATH.write_text(json.dumps(reading, indent=2) + "\n", encoding="utf-8")
    return reading


def _load(path: Path) -> Optional[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def compute_time(experiment: str, model: str) -> Dict[str, Any]:
    """Machine time a model's runs consumed, from the recorded call latencies."""
    root = RESULTS_DIR / EXPERIMENT_DIRS[experiment] / model_slug(model)
    runs, call_seconds, wall_seconds = 0, 0.0, 0.0
    for path in sorted(root.glob("*/*.json")):
        if path.name.endswith(".failed.json"):
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("failed"):
            continue
        runs += 1
        wall_seconds += record["wall_clock_s"]
        call_seconds += sum(c["latency_s"] or 0 for c in record["usage"]["calls"])
    return {"runs": runs, "generation_seconds": call_seconds, "wall_clock_seconds": wall_seconds}


def report(experiment: str, model: str) -> Dict[str, Any]:
    """Cost of ownership per scenario, with every missing input named."""
    timing = compute_time(experiment, model)
    if not timing["runs"]:
        sys.exit(f"No completed runs for {model} under {experiment}")

    power = _load(POWER_PATH)
    hardware = _load(HARDWARE_PATH) or {}
    missing = []
    result: Dict[str, Any] = {
        "experiment": experiment, "model": model, **timing,
        "generation_hours": timing["generation_seconds"] / 3600,
        "wall_clock_hours": timing["wall_clock_seconds"] / 3600,
        "api_cost_usd": 0.0,
        "power": power, "hardware": {k: v for k, v in hardware.items() if not k.startswith("_")},
    }

    if power:
        watts = power["mean_package_power_w"]
        kwh = watts * result["wall_clock_hours"] / 1000
        result["energy_kwh"] = kwh
        price = hardware.get("electricity_price_per_kwh_usd")
        if price:
            result["energy_cost_usd"] = kwh * price
        else:
            missing.append("electricity_price_per_kwh_usd in data/tco/hardware.json")
    else:
        missing.append("a power measurement: run 'python -m src.experiment.tco power' during a local run")

    price, life = hardware.get("purchase_price_usd"), hardware.get("useful_life_years")
    if price and life:
        hourly = price / (life * hardware.get("hours_in_service_per_year", 8760))
        result["amortised_hardware_usd"] = hourly * result["wall_clock_hours"]
        result["amortised_hardware_rate_usd_per_hour"] = hourly
    else:
        missing.append("purchase_price_usd and useful_life_years in data/tco/hardware.json")

    total = sum(result.get(k, 0.0) or 0.0 for k in ("energy_cost_usd", "amortised_hardware_usd"))
    result["total_cost_usd"] = total if not missing else None
    result["cost_per_scenario_usd"] = (total / timing["runs"]) if total and not missing else None
    result["missing_inputs"] = missing
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["power", "report", "template"])
    parser.add_argument("--experiment", choices=sorted(EXPERIMENT_DIRS), default="e2")
    parser.add_argument("--model", default="mistral:7b")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()

    if args.command == "template":
        TCO_DIR.mkdir(parents=True, exist_ok=True)
        if HARDWARE_PATH.exists():
            sys.exit(f"{HARDWARE_PATH} already exists")
        HARDWARE_PATH.write_text(json.dumps(HARDWARE_TEMPLATE, indent=2) + "\n", encoding="utf-8")
        print(f"Written {HARDWARE_PATH}: fill in the purchase price and your electricity tariff.")
    elif args.command == "power":
        reading = measure_power(args.seconds)
        print(json.dumps(reading, indent=2))
        print(f"\nWritten: {POWER_PATH}")
    else:
        result = report(args.experiment, args.model)
        print(json.dumps(result, indent=2))
        if result["missing_inputs"]:
            print("\nNot computed, because these inputs are missing:", file=sys.stderr)
            for item in result["missing_inputs"]:
                print(f"  - {item}", file=sys.stderr)


if __name__ == "__main__":
    main()
