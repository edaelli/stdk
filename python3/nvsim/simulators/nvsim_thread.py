import time
import threading

from nvsim.simulators import NVSimInterface

import logging
logger = logging.getLogger('nvsim_thread')


class NVSimThread(threading.Thread):
    def __init__(self, nvme_device):
        self.nvme_device = nvme_device

        # Sanity check for interface type
        assert issubclass(type(self.nvme_device), NVSimInterface), (
            'Must be a subclass of NVSimInterface')

        # Save interfaces off here to avoid dereferencing every loop
        self.ifc_pcie_changed = self.nvme_device.nvsim_pcie_regs_changed
        self.ifc_nvme_changed = self.nvme_device.nvsim_nvme_regs_changed

        # Intialize thread stuff
        threading.Thread.__init__(self)
        self.daemon = True

        # Initialize Events
        self.stop_event = threading.Event()
        self.nvme_regs_event = threading.Event()
        self.pcie_regs_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def pcie_changed(self):
        self.pcie_regs_event.set()

    def nvme_changed(self):
        self.nvme_regs_event.set()

    def run(self):

        while True:
            try:
                # Call interfaces, checking for exceptions
                if self.pcie_regs_event.is_set():
                    self.ifc_pcie_changed()
                    self.pcie_regs_event.clear()

                if self.nvme_regs_event.is_set():
                    self.ifc_nvme_changed()
                    self.nvme_regs_event.clear()

            except Exception as e:
                # If the simulator code sees an exception while handling changes we
                #   call the interface here and break out.
                self.exception_handler(e)
                break

            # Exit if the main thread is not alive anymore
            if not threading.main_thread().is_alive():
                break

            # Check if we were asked to stop
            if self.stop_event.is_set():
                break

            # Briefly yield so other tasks can run
            time.sleep(0)
