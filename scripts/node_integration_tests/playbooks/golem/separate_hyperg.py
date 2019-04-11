from .regular_run_stop_on_reject import RegularRun


class SeparateHyperdrive(RegularRun):
    provider_node_script = 'provider/separate_hyperg'
    requestor_node_script = 'requestor/debug'
