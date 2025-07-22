import logging
import socket


class HostNameFilter(logging.Filter):
    def filter(self, record):
        record.host_name = socket.gethostname()
        return True
