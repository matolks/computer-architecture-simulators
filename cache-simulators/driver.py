import argparse
import sys
from collections import deque
from utils import Memory, Level
from cache import CacheLevel


def parse_args():
    parser = argparse.ArgumentParser(description="Cache Simulator Driver")
    parser.add_argument("config", help="Path to cache configuration file")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-t", "--trace", help="Path to trace input file")
    input_group.add_argument("--stdin", action="store_true", help="Read trace input from stdin")
    return parser.parse_args()

def build_hierarchy(config_path):
    memory = Memory()
    top = memory
    with open(config_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    num_levels = int(lines[0])
    level_configs = lines[1:num_levels + 1]

    for config_line in reversed(level_configs):
        parts = [p.strip() for p in config_line.split(",")]
        size             = int(parts[0])
        block_size       = int(parts[1])
        associativity    = int(parts[2])
        eviction_policy  = parts[3]
        write_policy     = parts[4]
        level_name       = parts[5]

        new_level = CacheLevel(
            size=size,
            block_size=block_size,
            associativity=associativity,
            eviction_policy=eviction_policy,
            write_policy=write_policy,
            level_name=level_name,
            higher_level=top,
        )
        top.lower_level = new_level
        top = new_level
    return top


def print_hierarchy(top):
    parts = []
    current = top
    while current is not None:
        parts.append(str(current))
        current = current.higher_level
    print("Memory Hierarchy:")
    print("        " + " <-> ".join(parts))


def run_trace(top, trace_lines):
    for line in trace_lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        operation   = parts[0].strip()
        address_str = parts[1].strip()
        if operation not in ("R", "W"):
            print(f"Error: invalid access type '{operation}' in trace.", file=sys.stderr)
            sys.exit(1)
        address = int(address_str, 16)
        top.access(operation, address)

def print_all_statistics(top):
    current = top
    while current is not None:
        current.report_statistics()
        current = current.higher_level

def main():
    args = parse_args()
    top = build_hierarchy(args.config)
    print_hierarchy(top)
    if args.stdin:
        trace_lines = sys.stdin.readlines()
    else:
        with open(args.trace, "r") as f:
            trace_lines = f.readlines()
    run_trace(top, trace_lines)
    print_all_statistics(top)

if __name__ == "__main__":
    main()