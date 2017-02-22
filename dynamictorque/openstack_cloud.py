#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque Openstack wrapper
# This class implements ICloud to talk to openstack

import logging
import subprocess
import time
import os.path
import sys

import dynamictorque.utilities as utilities
from dynamictorque.cloud_tools import ICloud
from dynamictorque.cloud_tools import VM
from dynamictorque.cloud_tools import VMFlavor

from novaclient.v1_1 import client
import novaclient
import uuid
import datetime

log = utilities.get_logger()


class OpenStackCloud(ICloud):
    def __init__(self, config):
        self.vm_prefix=config.cloud_vm_prefix
        self.image_uuid=config.cloud_image_uuid
        self.vm_flavor=config.cloud_vm_flavor
        self.keyname=config.cloud_key_name
        self.security_groups=config.cloud_security_groups
        self.private_key_location=config.cloud_private_key_location
        self.ssh_connection_timeout_value=config.ssh_connection_timeout_value
        self.default_availability_zone=config.cloud_availability_zone
        self.vm_init_file=config.cloud_vm_init_file
        self.cloud_username=config.cloud_username
        self.cloud_password=config.cloud_password
        self.cloud_tenant_name=config.cloud_tenant_name
        self.cloud_auth_url=config.cloud_auth_url
        self.vm_userdata_file=config.cloud_vm_userdata_file
        self.vm_init_finish_file=config.cloud_vm_init_finish_file
        self.shell_user=config.cloud_shell_user
        self.cloud_resources=config.cloud_resources
    
    def _open_connection(self, res=None):
        if res is None or self.cloud_resources[res] is None:
            username=self.cloud_username
            password=self.cloud_password
            tenant_name=self.cloud_tenant_name
        else:
            username=self.cloud_resources[res].username
            password=self.cloud_resources[res].password
            tenant_name=self.cloud_resources[res].tenant_name
            
        log.debug("Opening connection to OpenStack for %s of %s." % (username,tenant_name))
        connected=False
        sleep_time=5
        
        while not connected:
            try:
                conn=client.Client(username, password, tenant_name, self.cloud_auth_url)
                conn.authenticate()
                connected=True
            except:
                e = sys.exc_info()[0]
                log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))
                sleep_time=sleep_time+5
                time.sleep(sleep_time)
        return conn
    
    def vm_destroy(self, vm):
        """ Terminate an instance """
        connection=self._open_connection(vm.cloud_resource_name)
        log.info("Destroying VM %s (ip=%s)"%(vm.id,vm.ip))
        try:
            server = connection.servers.get(vm.id)
            connection.servers.delete(server)
            vm.delete_time = datetime.datetime.utcnow()
        except novaclient.exceptions.NotFound as ex:
            log.info("VM %s is already shut down"%(vm.id))
            vm.delete_time = datetime.datetime.utcnow()
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))
            return False
        time.sleep(1)
        try:
            server = connection.servers.get(vm.id)
            if server.status == "ACTIVE":
                time.sleep(2)
        except:
            pass
        return True

    def vm_start(self, flavor, availability_zone=None, res=None):
        """ Start a new instance (used by active mode only) """
        connection=self._open_connection(res)
        try:
            if res is None or self.cloud_resources[res] is None:
                image_uuid=self.image_uuid
                user_data_file=self.vm_userdata_file
            else:
                image_uuid=self.cloud_resources[res].image_uuid
                user_data_file=self.cloud_resources[res].user_data_file
            server_name=self.vm_prefix+"-"+res+"-"+utilities.get_unique_string()
            if os.path.exists(user_data_file) and os.path.isfile(user_data_file):
                userdata_string=self.load_template_with_jinja(user_data_file, {"minion_id":server_name})
            else:
                log.exeception("userdata file does not exist, can't create VM, please check your config.")
                return None
            flavor_obj=connection.flavors.get(flavor)
            if not availability_zone:
                availability_zone=self.default_availability_zone
            log.debug("flavor %s; availability_zone %s; image-uuid %s; userdata %s;" % (flavor_obj, availability_zone, image_uuid, user_data_file))
            server = connection.servers.create(server_name, image_uuid, flavor_obj, key_name=self.keyname, max_count=1, min_count=1, userdata=userdata_string, security_groups=self.security_groups, availability_zone=availability_zone) #scheduler_hints={'cell':self.default_availability_zone})
            return VM(server.id,server_name,vcpu_number=flavor_obj.vcpus,flavor=flavor,created=server.created, availability_zone=availability_zone, image_id=image_uuid, cloud_resource_name=res)
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when creating a new VM: %s" % str(e))
            return None
        
    def vm_check(self,vm):
        """ check the instance's status (used by active mode only) 
              return value: 0, ready; 1, cloud-init/configuration running; 2, cloud provisioning; 3, destroyed; 4. error 
        """
        connection=self._open_connection(vm.cloud_resource_name)
        log.verbose("Polling VM %s (ip=%s)..." % (vm.id,vm.ip))
        try:
            server = connection.servers.get(vm.id)
        except:
            log.info("VM %s doesn't exist"%vm.id)
            return 3
        log.debug("Status: %s" % server.status)
        vm.state=server.status
        vm.start_time=server.created
        if vm.vcpu_number == 0:
            vm.vcpu_number=connection.flavors.get(server.flavor['id']).vcpus
        if server.status == "ERROR" or getattr(server,"OS-EXT-STS:vm_state") == "error":
            return 4
        if server.status != "ACTIVE" or getattr(server,"OS-EXT-STS:vm_state") != "active" or getattr(server,"OS-EXT-STS:task_state") is not None:
            return 2
        try:
            ip=server.addresses.values()[0][0]['addr']
        except:
            log.error("Unable to get IP for VM %s"%vm)
            return 2
        #vm.availability_zone=getattr(server,"OS-EXT-AZ:availability_zone")
        vm.availability_zone=self.default_availability_zone
        vm.image_id=server.image['id']
        vm.set_ip(ip)
        os_flavor=connection.flavors.get(server.flavor['id'])
        vm.flavor=VMFlavor(os_flavor.id, os_flavor.name, int(os_flavor.vcpus), int(os_flavor.ram))
        #cmd='ssh-keygen -R '+ip+'; ssh -i '+self.private_key_location+' -o "ConnectTimeout '+str(self.ssh_connection_timeout_value)+'" -o "CheckHostIP no" -o "StrictHostKeyChecking no" -o "BatchMode yes" '+self.shell_user+'@'+ip+' "ls '+self.vm_init_finish_file+'"'
        #cmd='ssh-keygen -R '+ip+'; ssh -i '+self.private_key_location+' -o "ConnectTimeout '+str(self.ssh_connection_timeout_value)+'" -o "CheckHostIP no" -o "StrictHostKeyChecking no" -o "BatchMode yes" '+self.shell_user+'@'+ip+' "ps -ef|grep mom|grep -v grep"'
        #process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #output,stderr = process.communicate()
        #status = process.poll()
        #log.debug("init script status: %d; output: %s" % (status, output))
        #if status == 0:
        if self.check_server(ip, 15002):
            return 0
#        elif status == 255:
#            return 2
        else:
            return 1
        
    def vm_list(self, res=None):
        """ List all instances with the configured prefix """
        connection=self._open_connection(res)
        try:
            servers = connection.servers.list(search_opts={"name":self.vm_prefix+"-"+res+"*"})
            all_vms = []
            for server in servers:
                vm=VM(server.id, server.name)
                if server.status == "ACTIVE" and getattr(server,"OS-EXT-STS:vm_state") == "active" and getattr(server,"OS-EXT-STS:task_state") is None:
                    try:
                        log.debug("ip1 %s"%server.addresses.values())
                        log.debug("ip2 %s"%server.addresses.values()[0])
                        log.debug("ip3 %s"%server.addresses.values()[0][0])
                        ip=server.addresses.values()[0][0]['addr']
                        vm.set_ip(ip)
                    except:
                        log.error("Unable to get IP for VM %s"%vm)
                    vm.availability_zone=getattr(server,"OS-EXT-AZ:availability_zone")
                    vm.image_id=server.image['id']
                vm.start_time=server.created
                vm.state=server.status
                os_flavor=connection.flavors.get(server.flavor['id'])
                vm.flavor=VMFlavor(os_flavor.id, os_flavor.name, int(os_flavor.vcpus), int(os_flavor.ram))
                vm.vcpu_number=os_flavor.vcpus
                vm.cloud_resource_name=res
                all_vms.append(vm)
            return all_vms
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))
            return []

    def get_flavor_list(self, max_number_cores_per_vm=0, min_number_cores_per_vm=0):
        """ Get all flavors from the cloud """
        connection=self._open_connection()
        try:
            return [VMFlavor(f.id, f.name, int(f.vcpus), int(f.ram)) for f in connection.flavors.list() if (max_number_cores_per_vm<1 or int(f.vcpus)<=max_number_cores_per_vm) and (min_number_cores_per_vm<1 or int(f.vcpus)>=min_number_cores_per_vm)]
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))
            return []
            
    def add_security_group_rule(self, res, sg_name, protocol, cidr, from_port, to_port):
        """ add a new rule to security group """
        connection=self._open_connection(res)
        try:
            sg_list=connection.security_groups.list()
            for sg in sg_list:
                if sg.name==sg_name:
                    the_sg=sg
                    break
            if the_sg is not None:
                has_rule=False
                for rule in the_sg.rules:
                    if rule['from_port']==from_port and rule['to_port']==to_port and 'cidr' in rule['ip_range'] and rule['ip_range']['cidr']==cidr:
                        has_rule=True
                        break
                if not has_rule:
                    log.debug("adding security group rule (%s:%s-%s, %s) to security group %s" % (protocol, from_port, to_port, cidr, sg_name))
                    connection.security_group_rules.create(the_sg.id, protocol, from_port, to_port, cidr)
                else:
                    log.warn("security group rule (%s:%s-%s, %s) is found in security group %s" % (protocol, from_port, to_port, cidr, sg_name))
            else:
                log.error("security group %s not found" % sg_name)
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))

    def remove_security_group_rule(self, res, sg_name, protocol, cidr, from_port, to_port):
        """ remove a new rule to security group """
        connection=self._open_connection(res)
        try:
            sg_list=connection.security_groups.list()
            for sg in sg_list:
                if sg.name==sg_name:
                    the_sg=sg
                    break
            if the_sg is not None:
                the_rule=None
                for rule in the_sg.rules:
                    if rule['from_port']==from_port and rule['to_port']==to_port and 'cidr' in rule['ip_range'] and rule['ip_range']['cidr']==cidr:
                        the_rule=rule
                        break
                if the_rule is not None:
                    log.debug("removing security group rule (%s:%s-%s, %s) from security group %s" % (protocol, from_port, to_port, cidr, sg_name))
                    connection.security_group_rules.delete(the_rule['id'])
                else:
                    log.error("security group rule (%s:%s-%s, %s) not found in security group %s" % (protocol, from_port, to_port, cidr, sg_name))
            else:
                log.error("security group %s not found" % sg_name)
        except:
            e = sys.exc_info()[0]
            log.exception("Encounter an error when connecting to OpenStack: %s" % str(e))
                   
    def load_template_with_jinja(self, location, vars):
        # Load the jinja library's namespace into the current module.
        import jinja2
        
        # In this case, we will load templates off the filesystem.
        # This means we must construct a FileSystemLoader object.
        # 
        # The search path can be used to make finding templates by
        #   relative paths much easier.  In this case, we are using
        #   absolute paths and thus set it to the filesystem root.
        templateLoader = jinja2.FileSystemLoader( searchpath="/" )
        
        # An environment provides the data necessary to read and
        #   parse our templates.  We pass in the loader object here.
        templateEnv = jinja2.Environment( loader=templateLoader )
        
        # Read the template file using the environment object.
        # This also constructs our Template object.
        template = templateEnv.get_template( location )
        
        # Finally, process the template to produce our final text.
        return template.render( vars )
    
    def check_server(self, address, port):
        import socket
        # Create a TCP socket
        log.debug( "Attempting to connect to %s on port %s" % (address, port) )
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((address, port))
            log.debug(  "Connected to %s on port %s" % (address, port))
            s.shutdown(2)
            return True
        except socket.error, e:
            log.debug( "Connection to %s on port %s failed: %s" % (address, port, e))
            return False
