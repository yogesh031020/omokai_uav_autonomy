"""
CLI entry-point for the Omokai UAV Autonomy Stack.

Usage:
    python3 cli.py "your prompt here"           # dry-run (default)
    python3 cli.py "your prompt here" --live     # connect to real SITL
"""
import sys
import os
import asyncio

from llm_parser import parse_prompt_to_json
from validator import validate_mission_json
from executor import DroneExecutor


async def run_pipeline(prompt_str, dry_run=True):
    print("=" * 60)

    # -- Step 1: Parse --
    print("STEP 1: LLM Parsing")
    try:
        raw_json = parse_prompt_to_json(prompt_str)
        print(f"  Generated JSON:\n  {raw_json}\n")
    except Exception as e:
        print(f"  Parsing error: {e}")
        return

    # -- Step 2: Validate --
    print("STEP 2: Safety Validation")
    try:
        validated = validate_mission_json(raw_json)
        print("  Safety check PASSED\n")
    except ValueError as e:
        print(f"  Safety check FAILED: {e}")
        print("  MISSION ABORTED -- blocked by safety guardrails.")
        print("=" * 60)
        return

    # -- Step 3: Execute --
    mode = "LIVE SIMULATION" if not dry_run else "DRY-RUN"
    print(f"STEP 3: Mission Execution  [{mode}]")
    try:
        executor = DroneExecutor(dry_run=dry_run)
        await executor.connect()
        await executor.execute_mission(validated)
    except Exception as e:
        print(f"  Execution failed: {e}")

    print("=" * 60)


if __name__ == "__main__":
    args = sys.argv[1:]
    dry_run = True

    if "--live" in args:
        dry_run = False
        args.remove("--live")

    prompt = " ".join(args) if args else \
        "Takeoff to 12 meters, go to waypoint 15,25,12, and then land"

    asyncio.run(run_pipeline(prompt, dry_run=dry_run))
