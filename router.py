from interface import Interface


class Router:
    def __init__(self, hostname, mgmt_ip, vendor, os):
        self.hostname = hostname
        self.mgmt_ip = mgmt_ip
        self.vendor = vendor
        self.os = os
        self.interfaces = []
        self.bgp = {}

    def add_interface(self, name, ip, description, status):
        new_interface = Interface(name, ip, description, status)
        self.interfaces.append(new_interface)

    def interfaces_is_empty(self):
        if self.interfaces is None or len(self.interfaces) == 0:
            return True
        return False

    def add_bgp(self, rid, asn, neighbors):
        self.bgp = {'asn': asn,
                    'rid': rid,
                    'neighbors': []}

        for neighbor in neighbors:
            self.bgp['neighbors'].append(neighbor)

    def get_device_info(self):
        return str('\nHostname: {hostname}\nVendor: {vendor}\nOS: {os}\nMGMT IP: {mgmt}\n# of Interfaces: {total}'.format(
            hostname=self.hostname,
            vendor=self.vendor,
            os=self.os,
            mgmt=self.mgmt_ip,
            total=len(self.interfaces)
        ))