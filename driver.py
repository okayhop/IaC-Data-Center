#!/usr/bin/env python
import yaml
import argparse
import ipaddress
import napalm
import logging
import sys
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
import time
from io import StringIO
from configparser import ConfigParser
from napalm.base.exceptions import ConnectionException
from jinja2 import Environment, FileSystemLoader

from router import Router


def __get_args():
    """
    Command line parser
    :return: args object
    """
    # command line parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-config',
        '--config',
        help='YAML file containing network configuration data')
    parser.add_argument(
        '-log',
        '--log',
        default="warning",
        help=(
            'Provide logging level.'
            "Example --log debug', default='warning''"),
    )
    parser.add_argument(
        '-vars',
        '--vars',
        default="env.cfg",
        help='Environment variables.',
    )
    return parser.parse_args()


def device_setup(hostname, data, env_vars, que):
    device = Router(
        hostname=hostname,
        mgmt_ip=data['mgmt'],
        vendor=data['vendor'],
        os=data['os']
    )

    for name, interface in data['interfaces'].items():
        device.add_interface(
            name=name,
            ip=ipaddress.IPv4Interface(interface['ipaddr']),
            description=interface['description'],
            status=interface['state']
        )

    all_neighbors = []
    for neighbor in data['bgp']['neighbors']:
        all_neighbors.append((neighbor['ipaddr'], neighbor['remote_asn']))

    device.add_bgp(
        rid=data['bgp']['rid'],
        asn=data['bgp']['asn'],
        neighbors=all_neighbors
    )

    open_device = connect_to_device(device, env_vars)

    que.put((device, open_device))


def connect_to_device(device, env_vars):
    """
    Opens a NAPALM device object
    :param device: Router object
    :param env_vars: cfg file
    :return:
    """
    # Use the appropriate network driver to connect to the device:
    driver = napalm.get_network_driver(device.os)

    # Connect:
    net_device = driver(
        hostname=str(ipaddress.IPv4Interface(device.mgmt_ip).ip),
        username=env_vars['ROUTERS']['username'],
        password=env_vars['ROUTERS']['password']
    )

    try:
        net_device.open()
        logging.info('{} is open!'.format(device.hostname))
    except ConnectionException:
        logging.warning('Could not open {}'.format(device.hostname))

    return net_device


def generate_config(device, env_vars, action):
    """
    Generic function to generate configuration from jinja2 templates

    :param device: Router object that contains configuraton
    :param env_vars: cfg file
    :param action: Action to be completed. Tied to the naming schema of the templates
    :return: String - configuration
    """
    template_path = env_vars['CONFIGURATION']['templates'] + '/' + device.vendor + '/' + device.os
    env = Environment(loader=FileSystemLoader(template_path))
    config_template = env.get_template(action + '.txt')

    config = StringIO()
    config.write(config_template.render(data=device))

    return config.getvalue()


def send_config_to_device(net_device, device, config):
    """
    Sends configuration to device
    :param net_device: NAPALM device object
    :param device: Router object
    :param config: String configuration
    :return: None
    """
    logging.debug('Sending configuration to {}'.format(device.hostname))
    net_device.load_merge_candidate(config=config)
    net_device.commit_config()


def main(args):
    f = open(args.config, 'r')
    network_yml = yaml.safe_load(f)

    env_vars = ConfigParser()
    env_vars.read(args.vars)

    # Create objects for each device
    devices = []
    threads = []
    ques = []

    for hostname, data in network_yml.items():
        q = queue.Queue()
        t = threading.Thread(
            target=device_setup,
            args=(hostname, data, env_vars, q)) # Using multiple threads to speed up this process
        threads.append(t)
        ques.append(q)
        t.start()

    for thread in threads:
        thread.join()

    for que in ques:
        devices.append(que.get())


    # Base configuration on each device
    for device in devices:
        logging.info('Generating configuration for {}'.format(device[0].hostname))
        config = ''
        config += generate_config(device[0], env_vars, 'add_hostname') + '\n'
        config += generate_config(device[0], env_vars, 'add_interface') + '\n'
        send_config_to_device(device[1], device[0], config)

    # Validate p2p links
    for device in devices:
        logging.info('Testing interfaces on {}'.format(device[0].hostname))
        for interface in device[0].interfaces:
            # Will get each interfaces P2P peer host and ping it. Log messages generated based on the boolean output
            if interface.status == 'up':
                ping_status = device[1].ping(interface.get_p2p_connected_host())
                if ping_status['success']['probes_sent'] > ping_status['success']['packet_loss']:
                    logging.info('{interface} on {device} can reach its peer!'.format(
                        interface=interface.name,
                        device=device[0].hostname
                    ))
                else:
                    logging.warning('{interface} on {device} CANNOT reach its peer!'.format(
                        interface=interface.name,
                        device=device[0].hostname
                    ))

    # Configure BGP
    for device in devices:
        logging.info('Generating BGP configuration for {}'.format(device[0].hostname))
        config = ''
        config += generate_config(device[0], env_vars, 'add_bgp_neighbor') + '\n'
        send_config_to_device(device[1], device[0], config)

    # Validate BGP

    # Close open device connections
    for device in devices:
        logging.info('Closing {} connection'.format(device[0].hostname))
        try:
            device[1].close()
            logging.info('{} is closed!'.format(device[0].hostname))
        except ConnectionException:
            logging.warning('An issue occured while closing {}'.format(device[0].hostname))

    # Bye!
    sys.exit()


if __name__ == "__main__":
    args = __get_args()

    logging.basicConfig(level=args.log.upper(),
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M',
                        filename='log/config.log',
                        filemode='w')
    console = logging.StreamHandler()
    console.setLevel(args.log.upper())
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    main(args)
