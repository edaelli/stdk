import ctypes

from lone.system import DevMemMgr, MemoryLocation


class SimMemMgr(DevMemMgr):
    ''' Simulated memory implemenation
    '''
    def __init__(self, page_size):
        ''' Initializes a memory manager
        '''
        self.page_size = page_size
        self._allocated_mem_list = []

    def malloc(self, size, direction, client=None):
        memory_obj = (ctypes.c_uint8 * size)()

        # Append to our list so it stays allocated until we choose to free it
        vaddr = ctypes.addressof(memory_obj)

        # Create the memory location object from the allocated memory above
        mem = MemoryLocation(vaddr, vaddr, size, client)
        mem.mem_obj = memory_obj
        self._allocated_mem_list.append(mem)

        return mem

    def malloc_pages(self, num_pages, client=None):
        pages = []
        for page_idx in range(num_pages):
            pages.append(self.malloc(self.page_size))
        return pages

    def free(self, memory):
        for m in self._allocated_mem_list:
            if m == memory:
                self._allocated_mem_list.remove(m)

    def free_all(self):
        self._allocated_mem_list = []

    def allocated_mem_list(self):
        return self._allocated_mem_list
