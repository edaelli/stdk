from nvsim.simulators.generic import GenericNVMeNVSimDevice, GenericNVMeNVSimNamespace


class FDPNVMeSimDevice(GenericNVMeNVSimDevice):
    def __init__(self):
        super().__init__()

        # Initialize our namespaces
        self.sim_thread.config.namespaces = [
            None,  # Namespace 0 is never valid
            GenericNVMeNVSimNamespace(512, 4096, '/tmp/ns1.dat'),
        ]

        self.sim_thread.config.init_namespaces_data()
