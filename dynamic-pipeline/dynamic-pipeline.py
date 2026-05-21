from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional


@dataclass
class Instruction:
    # Stores original instruction fields and the simulated pipeline state
    index: int
    op: str
    parts: List[str]

    fe: int = -1 # Fetch
    de: int = -1 # Decode
    re: int = -1 # Rename
    di: int = -1 # Dispatch
    is_: int = -1 # Issue
    wb: int = -1 # Writeback
    co: int = -1 # Commit

    # Dependency tracking and register freeing
    src_phys: List[int] = field(default_factory=list)
    new_phys: Optional[int] = None
    old_phys: Optional[int] = None
    wb_ready_cycle: int = -1


def parse_input(path: str) -> tuple[int, int, List[Instruction]]:
    # Reads the machine configuration. <PHYSICAL_REGISTERS>,<ISSUE_WIDTH>
    with open(path, "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]
    if not lines:
        return 0, 0, []
    first = lines[0].split(",")
    if len(first) != 2:
        raise ValueError("invalid first line")
    num_physical_regs = int(first[0])
    issue_width = int(first[1])
    instructions: List[Instruction] = []
    # Converts each line into an Instruction object
    for index, line in enumerate(lines[1:]):
        parts = line.split(",")
        if len(parts) != 4:
            raise ValueError(f"invalid instruction: {line}")
        instructions.append(Instruction(index=index, op=parts[0], parts=parts))
    return num_physical_regs, issue_width, instructions


class Simulator:
    # Core simulator state
    # Decode/rename/dispatch queues preserve program order, while the issue queue, ROB,
    # map/ready table, and free list model out-of-order scheduling.
    def __init__(self, num_physical_regs: int, issue_width: int, instructions: List[Instruction]) -> None:
        self.num_physical_regs = num_physical_regs
        self.issue_width = issue_width
        self.instructions = instructions

        self.cycle = 0
        self.fetch_index = 0
        self.committed = 0

        self.map_table: List[int] = list(range(32)) # Architectural to physical register mapping, A0-A31 map directly to P0-P31
        self.ready_table: List[bool] = [True] * num_physical_regs # Tracks physical registers for a ready value
        self.free_list: Deque[int] = deque(range(32, num_physical_regs)) # Physical registers not currently mapped
        self.delayed_free: List[tuple[int, int]] = [] # Registers freed at commit cannot be used for a cycle

        self.decode_queue: Deque[int] = deque()
        self.rename_queue: Deque[int] = deque()
        self.dispatch_queue: Deque[int] = deque()
        self.issue_queue: List[int] = []
        self.wb_queue: Deque[int] = deque()
        self.rob: Deque[int] = deque()

    # Moves physical registers back to the free list after delay
    def release_freed_registers(self) -> None:
        keep: List[tuple[int, int]] = []
        for available_cycle, reg in self.delayed_free:
            if available_cycle <= self.cycle:
                self.free_list.append(reg)
            else:
                keep.append((available_cycle, reg))
        self.delayed_free = keep

    # Converts architectural source registers into their current physical register mappings
    def physical_sources(self, inst: Instruction) -> List[int]:
        parts = inst.parts
        op = inst.op

        if op == "R":
            src1 = int(parts[2])
            src2 = int(parts[3])
            return [self.map_table[src1], self.map_table[src2]]
        if op == "I":
            src = int(parts[2])
            return [self.map_table[src]]
        if op == "L":
            base = int(parts[3])
            return [self.map_table[base]]
        if op == "S":
            src = int(parts[1])
            base = int(parts[3])
            return [self.map_table[src], self.map_table[base]]

        raise ValueError(f"unknown op {op}")

    # Only R, I, and L instructions allocate a new physical destination register
    def writes_destination(self, inst: Instruction) -> bool:
        if inst.op not in {"R", "I", "L"}:
            return False
        return int(inst.parts[1]) != 0

    # Instructions can issue only when all renamed physical source registers have values
    def is_ready(self, inst: Instruction) -> bool:
        return all(self.ready_table[reg] for reg in inst.src_phys)

    # Commits completed instructions in program order from the ROB
    def commit(self) -> None:
        committed_this_cycle = 0
        while committed_this_cycle < self.issue_width and self.rob:
            idx = self.rob[0]
            inst = self.instructions[idx]
            if inst.wb == -1 or inst.wb >= self.cycle:
                break
            self.rob.popleft()
            inst.co = self.cycle
            committed_this_cycle += 1
            self.committed += 1
            if inst.old_phys not in (None, 0):
                self.delayed_free.append((self.cycle + 1, inst.old_phys))

    # Completes issued instructions once their writeback cycle is reached
    def writeback(self) -> None:
        wrote_back = 0
        while wrote_back < self.issue_width and self.wb_queue:
            idx = self.wb_queue[0]
            inst = self.instructions[idx]
            if inst.wb_ready_cycle != self.cycle:
                break
            self.wb_queue.popleft()
            inst.wb = self.cycle
            if inst.new_phys not in (None, 0):
                self.ready_table[inst.new_phys] = True
            wrote_back += 1

    # Selects ready instructions from the issue queue up to issue width
    def issue(self) -> None:
        chosen: List[int] = []
        issued = 0
        memory_bundle_mode: Optional[str] = None
        for idx in self.issue_queue:
            if issued >= self.issue_width:
                break
            inst = self.instructions[idx]
            if not self.is_ready(inst):
                continue
            # So dependent loads and stores do not issue together in the same cycle
            if inst.op == "L":
                if memory_bundle_mode == "store":
                    continue
                chosen.append(idx)
                memory_bundle_mode = "load"
                issued += 1
                continue
            if inst.op == "S":
                if memory_bundle_mode is not None:
                    continue
                chosen.append(idx)
                memory_bundle_mode = "store"
                issued += 1
                continue
            chosen.append(idx)
            issued += 1
        if not chosen:
            return
        chosen_set = set(chosen)
        self.issue_queue = [idx for idx in self.issue_queue if idx not in chosen_set]
        for idx in chosen:
            inst = self.instructions[idx]
            inst.is_ = self.cycle
            inst.wb_ready_cycle = self.cycle + 1
            self.wb_queue.append(idx)

    # Moves renamed instructions into the issue queue
    def dispatch(self) -> None:
        dispatched = 0
        while dispatched < self.issue_width and self.dispatch_queue:
            idx = self.dispatch_queue.popleft()
            self.instructions[idx].di = self.cycle
            self.issue_queue.append(idx)
            dispatched += 1

    # Performs register renaming
    # If no physical register is available, rename stalls
    def rename(self) -> None:
        renamed = 0
        while renamed < self.issue_width and self.rename_queue:
            idx = self.rename_queue[0]
            inst = self.instructions[idx]
            if self.writes_destination(inst) and not self.free_list:
                break
            self.rename_queue.popleft()
            inst.src_phys = self.physical_sources(inst)
            if inst.op == "R":
                dest = int(inst.parts[1])
                if dest != 0:
                    inst.old_phys = self.map_table[dest]
                    inst.new_phys = self.free_list.popleft()
                    self.map_table[dest] = inst.new_phys
                    self.ready_table[inst.new_phys] = False
            elif inst.op == "I":
                dest = int(inst.parts[1])
                if dest != 0:
                    inst.old_phys = self.map_table[dest]
                    inst.new_phys = self.free_list.popleft()
                    self.map_table[dest] = inst.new_phys
                    self.ready_table[inst.new_phys] = False
            elif inst.op == "L":
                dest = int(inst.parts[1])
                if dest != 0:
                    inst.old_phys = self.map_table[dest]
                    inst.new_phys = self.free_list.popleft()
                    self.map_table[dest] = inst.new_phys
                    self.ready_table[inst.new_phys] = False
            inst.re = self.cycle
            self.dispatch_queue.append(idx)
            self.rob.append(idx)
            renamed += 1

    # Moves fetched instructions into the rename stage
    # Fetch and decode do not stall except for issue width limits
    def decode(self) -> None:
        decoded = 0
        while decoded < self.issue_width and self.decode_queue:
            idx = self.decode_queue.popleft()
            self.instructions[idx].de = self.cycle
            self.rename_queue.append(idx)
            decoded += 1

    # Fetches instructions in program order
    def fetch(self) -> None:
        fetched = 0
        while fetched < self.issue_width and self.fetch_index < len(self.instructions):
            inst = self.instructions[self.fetch_index]
            inst.fe = self.cycle
            self.decode_queue.append(self.fetch_index)
            self.fetch_index += 1
            fetched += 1

    # Cycle loop
    def run(self) -> None:
        while self.committed < len(self.instructions):
            self.release_freed_registers()
            self.commit()
            self.writeback()
            self.issue()
            self.dispatch()
            self.rename()
            self.decode()
            self.fetch()
            self.cycle += 1

    def write_output(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as file:
            if self.num_physical_regs <= 32:
                return
            for inst in self.instructions:
                file.write(
                    f"{inst.fe},{inst.de},{inst.re},{inst.di},{inst.is_},{inst.wb},{inst.co}\n"
                )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 pipeline.py test.in")

    input_path = sys.argv[1]
    output_path = "out.txt"
    num_physical_regs, issue_width, instructions = parse_input(input_path)
    if num_physical_regs <= 32:
        with open(output_path, "w", encoding="utf-8"):
            pass
        return 0
    simulator = Simulator(num_physical_regs, issue_width, instructions)
    simulator.run()
    simulator.write_output(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())