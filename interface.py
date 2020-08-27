import ipaddress


class Interface:
    def __init__(self, name, ip, description, status="down"):
        self.name = name
        self.ip = ipaddress.IPv4Interface(ip)
        self.description = description
        self.status = status

    def get_ip(self):
        return self.ip.ip

    def get_netmask(self):
        return self.ip.netmask

    def show_int(self):
        return str('name: {}\nip: {}\ndescription: {}\nstatus: {}'.format(
            self.name, str(self.ip), self.description, self.status
        ))

    def set_ip(self, ip):
        self.ip = ip

    def get_p2p_connected_host(self):
        hosts = list(self.ip.network.hosts())
        for host in hosts:
            if str(host) != str(self.ip.ip):
                return str(host)

