''' Python interface to manage hugepages memory
'''
import os
import hugepages
import math
import ctypes

from lone.system import DevMemMgr, MemoryLocation, DMADirection


class HugePagesMemoryMgr(DevMemMgr):
    ''' Uses hugepage backed memory but allocates and frees it in chunks of
        a certain page size.
    '''

    def __init__(self, device):
        # Initialize parent
        super().__init__(device)

        self.hugepages_memory = HugePagesMemory(self.page_size)

        # Allocate one huge page initially
        self.pages = []
        self._malloc_hps(1)

        # Keep track of memory given out on malloc calls
        self.malloc_mem = []

    def free_pages(self):
        return [p for p in self.pages if p.in_use is False]

    def allocated_mem_list(self):
        return self.malloc_mem

    def _malloc_hps(self, num_hps):
        ''' Allocates a certain number of hugepages and splits them up into
            pages (MemoryLocation).
        '''
        for hp_idx in range(num_hps):

            # Malloc hugepage
            vaddr, size = self.hugepages_memory._malloc(self.hugepages_memory.hugepages_size)

            # Split it up into pages, add to the self.pages list
            for pg_idx in range(size // self.page_size):
                self.pages.append(MemoryLocation(vaddr + (pg_idx * self.page_size),
                                                 0,
                                                 self.page_size,
                                                 __class__.__name__))

    def malloc(self, size, direction, client='HugePagesMemoryMgr'):
        ''' Allocates whatever number of pages needed to satisfy a
            contiguous memory area of size
            Will allocate more hugepages if needed
        '''
        # Allocations have to be at least one sc_page_size
        if size < self.hugepages_memory.sc_page_size:
            size = self.hugepages_memory.sc_page_size

        # Caclulate the consecutive number of pages needed
        pages_needed = max(1, size // self.page_size)

        # Allocate more hps if needed
        pages_per_hp = self.hugepages_memory.hugepages_size // self.page_size
        if pages_needed > len(self.free_pages()):
            num_alloc = max(1, math.ceil((pages_needed - len(self.free_pages())) // pages_per_hp))
            self._malloc_hps(num_alloc)

        # Generator to group pages in sets of n
        def grouper(in_list, n):
            for i in range(len(in_list) - (n - 1)):
                yield in_list[i:i + n]

        # Go through all groups of consecutive pages until we find on that is all free
        ret_mem = None
        for group in grouper(self.free_pages(), pages_needed):

            # First check if all the pages in group are free
            if any([p.in_use is True for p in group]):
                continue

            # Then make sure the pages_needed in group are contiguous. If not, we need
            #   to move on to the next set of pages
            if all([p0.vaddr + p0.size == p1.vaddr for p0, p1 in grouper(group, 2)]):

                # Found it!
                ret_mem = group[0]

                # Link the memory pages together to be able to free it later
                for m in group[1:]:
                    m.in_use = True
                    ret_mem.linked_mem.append(m)

                # Done!
                break

        else:
            raise MemoryError('Not able to find memory to malloc')

        # Update size so the MemoryLocation object we return can be used as if it was
        #  of that size
        ret_mem.size = size

        # Update the client that allocated this segment for debugging purposes
        ret_mem.client = client

        # Add iova
        ret_mem.iova = self.iova_mgr.get(ret_mem.size)

        # Mark in use
        ret_mem.in_use = True

        # Add to our tracking list
        self.malloc_mem.append(ret_mem)

        # Map it with the device
        self.map_iova(ret_mem, direction)

        # Return it!
        return ret_mem

    def map_iova(self, mem, direction):
        # Map the vaddr to an iova with the device
        if direction == DMADirection.HOST_TO_DEVICE:
            self.device.pci_userspace_device.map_dma_region_read(mem.vaddr, mem.iova, mem.size)
        elif direction == DMADirection.DEVICE_TO_HOST:
            self.device.pci_userspace_device.map_dma_region_write(mem.vaddr, mem.iova, mem.size)
        else:
            assert False, 'Direction {} not yet supported!'.format(direction)

        mem.iova_direction = direction
        mem.iova_mapped = True

    def malloc_pages(self, num_pages, client='HugePagesMemoryMgr'):
        ''' Allocates a number of free pages. Not guaranteed to be contiguous!
        '''
        # Allocate more hugepages if needed
        pages_per_hp = self.hugepages_memory.hugepages_size // self.page_size
        if num_pages > len(self.free_pages()):
            num_alloc = max(1, math.ceil((num_pages - len(self.free_pages())) / pages_per_hp))
            self._malloc_hps(num_alloc)

        # Mark the ones we are returning as used
        pages = self.free_pages()[:num_pages]
        for p in pages:
            p.in_use = True

        # Return allocated pages as a list
        assert len(pages) == num_pages, 'Did not allocate enough pages!'
        return pages

    def free(self, memory):
        ''' Free previously allocated pages
        '''
        # First free the links
        for m in memory.linked_mem:
            assert m.in_use is True
            m.in_use = False
            m.size = self.page_size

        # Clear linked memory
        memory.linked_mem = []

        # If no links, just the first one
        assert memory.in_use is True
        memory.in_use = False
        memory.size = self.page_size

        # Unmap the iova with the device
        assert memory.iova_mapped is True
        self.device.pci_userspace_device.unmap_dma_region(memory.iova, memory.size)
        memory.iova_mapped = False

        # Free the iova used for this memory
        self.iova_mgr.free(memory.iova)

        # Clear free'd memory
        ctypes.memset(memory.vaddr, 0, memory.size)

        # Remove from tracking list
        self.malloc_mem.remove(memory)

    def free_all(self):
        ''' Free all pages and hugepages memory previously allocated (no checks for double free)
        '''
        malloc = self.malloc_mem.copy()
        for m in malloc:
            self.free(m)

        # Remove all pages from our tracking list
        self.pages = []

        # Free all backing hugepages
        self.hugepages_memory._free_all()

        # Make sure it is all gone!
        assert len(self.malloc_mem) == 0, 'Memory not free after free_all'


class HugePagesMemory():

    def __init__(self, page_size):
        self.sc_page_size = os.sysconf('SC_PAGE_SIZE')

        # Initialize the hugepages extension
        hugepages.init()

        # Save off size
        self.hugepages_size = hugepages.get_size()

        # Keep track of all hugepage memory allocated
        self.allocated_memory = []

    def _malloc(self, size, align=os.sysconf('SC_PAGE_SIZE')):
        # Checks for size
        assert (self.hugepages_size % size) == 0, 'Must be a multiple of hugepages_size'
        assert (size % self.sc_page_size) == 0, 'Must be a multiple of SC_PAGE_SIZE'

        # Call our C extension to allocate memory
        vaddr = hugepages.malloc(size, align)
        if vaddr == 0 or vaddr == -1:
            raise MemoryError('Not able to allocate {} {}'.format(size, align))
        else:
            # Keep track of all allocated memory
            self.allocated_memory.append((vaddr, size))

        return vaddr, size

    def _free_all(self):
        # Free all memory
        for vaddr, size in self.allocated_memory:
            hugepages.free(vaddr)
            self.allocated_memory.remove((vaddr, size))
