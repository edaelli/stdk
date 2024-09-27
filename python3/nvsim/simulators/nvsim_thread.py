import time
import threading

import logging
logger = logging.getLogger('nvsim_thread')


class NVSimThread(threading.Thread):
    def __init__(self, nvme_device):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

        # Devices must implement the following interfaces
        try:
            self.pcie_handler = nvme_device.nvsim_pcie_handler
            self.nvme_handler = nvme_device.nvsim_nvme_handler
            self.exception_handler = nvme_device.nvsim_exception_handler
        except AttributeError:
            raise Exception('NVMe simulated device must implement the NVMeSimulator interface')

    def stop(self):
        self.stop_event.set()

    def run(self):

        while True:
            try:
                # Check for changes to pcie registers and act on them, make sure to
                #  lock so register objects are not able to move under the checking
                with self.lock:
                    self.pcie_handler()

                # Check for changes to nvme registers and act on them, make sure to
                #  lock so register objects are not able to move under the checking
                with self.lock:
                    self.nvme_handler()

            except Exception as e:
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
