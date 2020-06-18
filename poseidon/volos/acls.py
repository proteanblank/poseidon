# -*- coding: utf-8 -*-
"""
Created on 31 January 2020
@author: Ryan Ashley
"""

import logging
import os
from pathlib import Path
from poseidon.controllers.faucet.helpers import yaml_in, yaml_out



class Acl:

    def __init__(self, acl_file=None):
        self.acls = {}
        self.acl_file = acl_file

    def read(self, config_yaml=None):
        try:
            if config_yaml is None:
                config_yaml = yaml_in(self.acl_file)
            self.acls = config_yaml.get('acls', {})
        except (FileNotFoundError, PermissionError):
            return

    def write(self):
        try:
            config = yaml_in(self.acl_file)
            if 'acls' not in config:
                config['acls'] = {}
            config['acls'].update(self.acls)
            yaml_out(self.acl_file, config)
            return True
        except (FileNotFoundError, PermissionError):
            return False

    def add_rule(self, name, rule):
        if name not in self.acls:
            self.acls[name] = []
        self.acls[name].append(rule)


class ExclusiveAcl(Acl):

    def write(self):
        try:
            config = yaml_in(self.acl_file)
            if 'acls' not in config:
                config['acls'] = {}
            config['acls'] = self.acls
            yaml_out(self.acl_file, config)
            return True
        except (FileNotFoundError, PermissionError):
            return False


class VolosAcl(ExclusiveAcl):

    def __init__(self, endpoint, acl_dir, copro_vlans=[2], copro_port=23):
        self.mac = endpoint.endpoint_data['mac']
        self.acl_key = f'volos_copro_{self.mac}'
        self.acl_dir = acl_dir
        acl_file = os.path.join(self.acl_dir, f'/%s.yaml' % self.acl_key)
        super(VolosAcl, self).__init__(acl_file=acl_file)
        self.logger = logging.getLogger('coprocessor')
        self.endpoint = endpoint
        self.id = endpoint.name
        self.copro_vlans = copro_vlans
        self.copro_port = copro_port

    def write_acl_file(self, port_list=[]):
        self.acls = {}
        for port in port_list:
            for eth_type in (0x0800, 0x86dd):
                ip_str = port['proto']
                addresses = self.endpoint.metadata.get('%s_addresses' % ip_str, None)
                if addresses:
                    for ip in addresses:
                        rule = {'rule': {
                            'dl_type': eth_type,
                            'nw_proto': port['proto_id'],
                            '%s_src' % ip_str: ip,
                            'actions': {
                                'output': {
                                    'ports': [self.copro_port],
                                    'vlan_vid': self.copro_vlans}}}}
                    rule['rule']['%s_dst' % ip_str] = port['port']
                    self.add_rule(self.acl_key, rule)
        self.add_rule(self.acl_key, {'rule': {'actions': {'allow': 1}}})
        status = self.write()
        if not status:
            self.logger.error(
                'Volos ACL file:{0} could not be written. Coprocessing may not work as expected'.format(self.acl_file))
        return status

    def delete_acl_file(self):
        try:
            if os.path.exists(self.acl_file):
                os.remove(self.acl_file)
                return True
        except Exception as e:  # pragma: no cover
            self.logger.error(
                'Volos ACL file:{0} could not be deleted. Coprocessing may not work as expected'.format(self.acl_file))
        return False

    def ensure_acls_dir(self):
        try:
            if not os.path.exists(self.acl_dir):
                Path(self.acl_dir).mkdir(parents=True, exist_ok=True)
                return True
        except Exception as e:  # pragma: no cover
            self.logger.error(
                'Volos ACL directory:{0} could not be created. Coprocessing may not work as expected'.format(self.acl_file))
        return False
