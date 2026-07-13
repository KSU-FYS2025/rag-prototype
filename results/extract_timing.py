#!/usr/bin/env python3
"""
Extract timing information from eval set result JSON files.
Usage: python extract_timing.py <path_to_json_file>
"""

import json
import sys
from datetime import datetime, timezone


def ts_to_str(ts: float) -> str:
    """Convert a Unix timestamp to a human-readable UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fmt_duration(seconds: float) -> str:
    return f"{seconds:.2f}s"


def extract_timing(data: dict) -> None:
    eval_set_id = data.get("evalSetId", "unknown")
    creation_ts = data.get("creationTimestamp")
    total_actions = {"navigation": 0, "resolve_nearest": 0, "answer": 0, "clarify": 0}
    csv_output = [["query", "action", ""]]

    print("=" * 70)
    print(f"Eval Set:  {eval_set_id}")
    if creation_ts:
        print(f"Created:   {ts_to_str(creation_ts)}  ({creation_ts})")
    print("=" * 70)

    case_results = data.get("evalCaseResults", [])

    # Collect summary rows for the final table
    summary_rows = []

    for case in case_results:
        eval_id = case.get("evalId", "unknown")
        session = case.get("sessionDetails", {})
        events = session.get("events", [])

        if not events:
            print(f"\n[{eval_id}] No events found.\n")
            continue

        timestamps = [e["timestamp"] for e in events if "timestamp" in e]
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        total_duration = last_ts - first_ts

        print(f"\n{'─' * 70}")
        print(f"Eval:      {eval_id}")
        print(f"Start:     {ts_to_str(first_ts)}")
        print(f"End:       {ts_to_str(last_ts)}")
        print(f"Duration:  {fmt_duration(total_duration)}")

        # Per-agent breakdown
        agent_events = [
            e
            for e in events
            if "timestamp" in e
            and e.get("author") not in ("user", None)
            and "content" in e  # skip routing-only events
        ]

        if agent_events:
            print("\n  Agent Breakdown:")
            print(f"  {'Agent':<30} {'Timestamp':<25} {'Since Start':>12}")
            print(f"  {'─' * 30} {'─' * 25} {'─' * 12}")
            for e in agent_events:
                author = e.get("author", "unknown")
                ts = e["timestamp"]
                since_start = ts - first_ts
                if author == "actions_agent":
                    full_response = e["content"]["parts"][0]["text"]
                    response_json = json.loads(full_response)
                    for action in response_json["actions"]:
                        if total_actions[action["cmd"]]:
                            total_actions[action["cmd"]] += 1
                        else:
                            total_actions[action["cmd"]] = 1
                print(
                    f"  {author:<30} {ts_to_str(ts):<25} {fmt_duration(since_start):>12}"
                )

            # Token usage per agent
            token_events = [e for e in agent_events if e.get("usageMetadata")]
            if token_events:
                print("\n  Token Usage:")
                print(
                    f"  {'Agent':<30} {'Prompt':>8} {'Thoughts':>10} {'Output':>8} {'Total':>8}"
                )
                print(f"  {'─' * 30} {'─' * 8} {'─' * 10} {'─' * 8} {'─' * 8}")
                for e in token_events:
                    usage = e["usageMetadata"]
                    author = e.get("author", "unknown")
                    prompt = usage.get("promptTokenCount", 0)
                    thoughts = usage.get("thoughtsTokenCount", 0)
                    candidates = usage.get("candidatesTokenCount", 0)
                    total = usage.get("totalTokenCount", 0)
                    print(
                        f"  {author:<30} {prompt:>8} {thoughts:>10} {candidates:>8} {total:>8}"
                    )

        summary_rows.append(
            (eval_id, fmt_duration(total_duration), f"{first_ts:.2f}", f"{last_ts:.2f}")
        )

    # Final summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Eval ID':<45} {'Duration':>10}")
    print(f"{'─' * 45} {'─' * 10}")
    for eval_id, duration, _, _ in summary_rows:
        print(f"{eval_id:<45} {duration:>10}")

    if summary_rows:
        # Find fastest and slowest
        durations = [(r[0], float(r[1][:-1])) for r in summary_rows]
        fastest = min(durations, key=lambda x: x[1])
        slowest = max(durations, key=lambda x: x[1])
        avg = sum(d for _, d in durations) / len(durations)
        print(f"\n  Fastest: {fastest[0]} ({fastest[1]:.2f}s)")
        print(f"  Slowest: {slowest[0]} ({slowest[1]:.2f}s)")
        print(f"  Average: {avg:.2f}s")
    print()
    print("ACTIONS")
    print(f"{'=' * 25}")
    print(f"{'Action ID':<17} {'Count':>7}")
    print(f"{'─' * 17} {'─' * 7}")

    for action, count in total_actions.items():
        print(f"{action:<17} {count:>7}")

    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_timing.py <path_to_json_file>")
        sys.exit(1)

    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)

    extract_timing(data)


if __name__ == "__main__":
    main()
