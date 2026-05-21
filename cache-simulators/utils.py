class Level:
    """Abstract base class for every level in the memory hierarchy."""

    def __init__(self, name, higher_level=None, lower_level=None):
        self.name = name
        self.higher_level = higher_level
        self.lower_level = lower_level

        # Statistics counters
        self.read_hits = 0
        self.write_hits = 0
        self.read_misses = 0
        self.write_misses = 0
        self.evictions = 0
        self.writebacks = 0

    def access(self, operation, address):
        """Perform a read or write to the given memory address.
        operation is 'R' for read, 'W' for write, 'B' for writeback fetch."""
        raise NotImplementedError(f"{self.name}.access() is not implemented.")

    def evict(self, cache_index):
        """Remove a cache line from a cache set."""
        raise NotImplementedError(f"{self.name}.evict() is not implemented.")

    def is_dirty(self, block_address):
        """True if the cache line has been written but not yet written back."""
        raise NotImplementedError(f"{self.name}.is_dirty() is not implemented.")

    def invalidate(self, block_address):
        """Remove a cache line from this level (for inclusive cache behavior)."""
        raise NotImplementedError(f"{self.name}.invalidate() is not implemented.")

    def report_hit(self, operation, address):
        """Increment the hit counter and print a hit message."""
        if operation == "W":
            self.write_hits += 1
            print(f"{self.name}: write hit at address 0x{address:08x}")
        else:
            self.read_hits += 1
            print(f"{self.name}: read hit at address 0x{address:08x}")

    def report_miss(self, operation, address):
        """Increment the appropriate miss counter and print a miss message."""
        if operation == "W":
            self.write_misses += 1
            print(f"{self.name}: write miss at address 0x{address:08x}")
        else:
            self.read_misses += 1
            print(f"{self.name}: read miss at address 0x{address:08x}")

    def report_eviction(self, address):
        """Increment the eviction counter and print an eviction message."""
        self.evictions += 1
        print(f"{self.name}: evicted cache line at 0x{address:08x}")

    def report_writeback(self, address):
        """Increment the writeback counter and print a writeback message."""
        self.writebacks += 1
        print(f"{self.name}: performing writeback of cache line 0x{address:08x}")

    def report_statistics(self):
        """Print final statistics for this level after the trace finishes."""
        total_hits = self.read_hits + self.write_hits
        total_misses = self.read_misses + self.write_misses
        print(f"{self.name} Statistics")
        print(f"        {total_hits} hits ({self.read_hits} read, {self.write_hits} write)")
        print(f"        {total_misses} misses ({self.read_misses} read, {self.write_misses} write)")
        print(f"        {self.evictions} evictions")
        print(f"        {self.writebacks} writebacks")

    def __str__(self):
        return self.name


class Memory(Level):
    """
    Represents main memory. Memory always reports a hit. It has no sets, tags, dirty bits,
    or eviction policy. It cannot be evicted or invalidated.
    """
    def __init__(self):
        super().__init__(name="Memory")

    def access(self, operation, address):
        """Memory always contains every address, so every access is a hit."""
        self.report_hit(operation, address)

    def evict(self, cache_index):
        """Memory does not evict cache lines — do nothing."""
        pass

    def is_dirty(self, block_address):
        """The simulator does not track dirty state in main memory."""
        return False

    def invalidate(self, block_address):
        """Memory blocks are never removed — do nothing."""
        pass