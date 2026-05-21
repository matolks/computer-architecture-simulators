from collections import deque
from utils import Level

class CacheLevel(Level):
    def __init__(
        self,
        size,
        block_size,
        associativity,
        eviction_policy,
        write_policy,
        level_name,
        higher_level=None, 
        lower_level=None,
    ):
        super().__init__(level_name, higher_level, lower_level)
        # Config from file
        self.size = size
        self.block_size = block_size
        self.associativity = associativity
        self.eviction_policy = eviction_policy
        self.write_policy = write_policy

        self.num_sets = self.size // (self.block_size * self.associativity)
        self.sets = [dict() for _ in range(self.num_sets)] # Maps tag to metadata
        self.evic_queue = [deque() for _ in range(self.num_sets)] # FIFO, MRU, LRU

    # Selects which cache set the address maps to
    def calculate_index(self, address):
        return (address // self.block_size) % self.num_sets

    # Finds the memory block within a given set
    def calculate_tag(self, address):
        return address // (self.block_size * self.num_sets)

    # Returns the block starting address
    def calculate_block_address(self, address):
        return (address // self.block_size) * self.block_size

    # Calculates block starting address from its tag and set index
    def calculate_block_address_from_tag_index(self, tag, cache_index):
        return (tag * self.num_sets + cache_index) * self.block_size

    # Updates replacement order after normal cache accesses
    def _touch(self, cache_index, tag, operation):
        if operation == "B":
            return
        # Recently used blocks are moved to the back
        # LRU evicts from the front, MRU evicts from the back
        if self.eviction_policy in {"LRU", "MRU"}:
            if tag in self.evic_queue[cache_index]:
                self.evic_queue[cache_index].remove(tag)
            self.evic_queue[cache_index].append(tag)

    # Checks if a block is present and dirty
    def is_dirty(self, block_address):
        cache_index = self.calculate_index(block_address)
        tag = self.calculate_tag(block_address)
        return self.sets[cache_index].get(tag, {}).get("dirty", False)


    def access(self, operation, address):
        # Converts address into cache lookup field
        cache_index = self.calculate_index(address)
        tag = self.calculate_tag(address)
        block_address = self.calculate_block_address(address)
        if tag in self.sets[cache_index]: # Cache-hit
            self.report_hit(operation, address)
            if operation in {"W", "B"}: # Writes and writebacks make cached block dirty
                self.sets[cache_index][tag]["dirty"] = True
            self._touch(cache_index, tag, operation)
            return

        self.report_miss(operation, address) # Cache miss
        if len(self.sets[cache_index]) >= self.associativity: # Evict if full
            self.evict(cache_index)
        fetched_dirty = False
        if operation != "B" and self.higher_level is not None: # CPU reads/writes fetch from the next level toward memory
            self.higher_level.access("R", address)
            fetched_dirty = self.higher_level.is_dirty(block_address)
        self.sets[cache_index][tag] = { # # Insert block into cache set
            "dirty": operation in {"W", "B"} or fetched_dirty
        }
        self.evic_queue[cache_index].append(tag)


    def evict(self, cache_index):
        if not self.evic_queue[cache_index]:
            return
        # FIFO and LRU evict from the front/oldest
        # MRU evicts from the back
        if self.eviction_policy in {"FIFO", "LRU"}:
            victim_tag = self.evic_queue[cache_index].popleft()
        else:
            victim_tag = self.evic_queue[cache_index].pop()
        block_address = self.calculate_block_address_from_tag_index(victim_tag, cache_index)
        self.invalidate(block_address)


    def invalidate(self, block_address):
        cache_index = self.calculate_index(block_address)
        tag = self.calculate_tag(block_address)
        if tag not in self.sets[cache_index]:
            return
        # If a block is removed from this level, remove it from lower levels too
        if self.lower_level is not None:
            self.lower_level.invalidate(block_address)
        # Dirty blocks must be written back before evicted
        if self.sets[cache_index][tag]["dirty"]:
            self.report_writeback(block_address)
            if self.higher_level is not None:
                self.higher_level.access("B", block_address)
        del self.sets[cache_index][tag]
        if tag in self.evic_queue[cache_index]:
            self.evic_queue[cache_index].remove(tag)
        self.report_eviction(block_address)