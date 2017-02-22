#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque model classes

import logging

import dynamictorque.utilities as utilities

log = utilities.get_logger()

class VM(object):
    def __init__(self, id, name, ip=None, jobid=None, vcpu_number=0, flavor=None, created=None, availability_zone=None, image_id=None, cloud_resource_name="default"):
        self.id=id
        self.name=name
        self.ip=ip
        self.jobid=jobid
        self.inaccessible_time=0
        self.idle_time=0
        self.vcpu_number=vcpu_number
        #self.hostname=None
        self.hostname=name
        self.flavor=flavor
        self.cloud_ready=False
        self.start_time=created
        self.state="N/A"
        self.state_time=None
        self.delete_time=None
        self.force_off=False
        self.dynamic=True
        self.ready_time=None
        self.availability_zone=None
        self.image_id=image_id
        self.cloud_resource_name=cloud_resource_name
        self.post_provision_command_executed=False
        
    def id(self):
        return self.id
    
    def name(self):
        return self.name
    
    def set_ip(self, ip):
        self.ip=ip
        
    def ip(self):
        return self.ip
    
    def set_jobid(self, jobid):
        self.jobid=jobid
        
    def jobid(self):
        return self.jobid
    
    def increase_inaccessible_time(self, sec):
        self.inaccessible_time = self.inaccessible_time + sec
        
    def reset_inaccessible_time(self):
        self.inaccessible_time = 0
        
    def get_inaccessible_time(self):
        return self.inaccessible_time

    def increase_idle_time(self, sec):
        self.idle_time = self.idle_time + sec
        
    def reset_idle_time(self):
        self.idle_time = 0
        
    def get_idle_time(self):
        return self.idle_time
    
    def __str__(self):
        return "VM {id: %s, name: %s, ip: %s, jobid: %s, vcpu_number: %i, hostname: %s, flavor: %s, dynamic: %s, zone: %s}" % (self.id, self.name, self.ip, self.jobid, self.vcpu_number, self.hostname, self.flavor, self.dynamic, self.availability_zone)

    def __repr__(self):
        return "VM {id: %s, name: %s, ip: %s, jobid: %s, vcpu_number: %i, hostname: %s, flavor: %s, dynamic: %s, zone: %s}" % (self.id, self.name, self.ip, self.jobid, self.vcpu_number, self.hostname, self.flavor, self.dynamic, self.availability_zone)

class VMFlavor(object):
    def __init__(self, id, name, vcpus, ram):
        self.id=id
        self.name=name
        self.vcpus=vcpus
        self.ram=ram
    def __str__(self):
        return "VMFlavor {id: %s, name: %s, vcpus: %i, ram: %i }" % (self.id, self.name, self.vcpus, self.ram)
    def __repr__(self):
        return "VMFlavor {id: %s, name: %s, vcpus: %i, ram: %i }" % (self.id, self.name, self.vcpus, self.ram)

class CloudResource(object):
    def __init__(self, username, password, tenant_name, image_uuid, user_data_file,worker_node_flavors, static_worker_nodes, number_of_dynamic_worker_nodes, static_vm_list, account_string=None, has_volume=False, reservation_type="account"):
        self.username = username
        self.password = password
        self.tenant_name = tenant_name
        self.image_uuid = image_uuid
        self.user_data_file = user_data_file
        self.worker_node_flavors=worker_node_flavors
        self.static_worker_nodes = static_worker_nodes
        self.number_of_dynamic_worker_nodes = number_of_dynamic_worker_nodes
        self.flavor_objects=[]
        self.static_vms_to_start=static_vm_list
        self.available_number_of_nodes=number_of_dynamic_worker_nodes
        self.account_string=account_string
        self.has_volume=has_volume
        self.reservation_type=reservation_type
        
    def available_cores(self):
        self.flavor_objects.sort(key=lambda flavor_object : flavor_object.vcpus, reverse=True)
        log.debug("self.available_number_of_nodes %i self.flavor_objects[0].vcpus %i"%(self.available_number_of_nodes,self.flavor_objects[0].vcpus))
        return self.available_number_of_nodes*self.flavor_objects[0].vcpus
        
    def __str__(self):
        return "CloudResource {username: %s, tenant_name: %s, worker_node_flavor: %s, static_worker_nodes: %s, number_of_dynamic_worker_nodes: %i, account_string: %s, image uuid: %s, userdata file: %s}" % (self.username, self.tenant_name, self.worker_node_flavors, self.static_worker_nodes, self.number_of_dynamic_worker_nodes, self.account_string, self.image_uuid, self.user_data_file)
    def __repr__(self):
        return "CloudResource {username: %s, tenant_name: %s, worker_node_flavor: %s, static_worker_nodes: %s, number_of_dynamic_worker_nodes: %i, account_string: %s, image uuid: %s, userdata file: %s}" % (self.username, self.tenant_name, self.worker_node_flavors, self.static_worker_nodes, self.number_of_dynamic_worker_nodes, self.account_string, self.image_uuid, self.user_data_file)
    
class ResAllocation(object):
    def __init__(self, v, location_property):
        self.vcpu_list=[v]
        self.location_property=location_property
    def get_total_num_cores(self):
        return sum(i for i in self.vcpu_list)
    def __repr__(self):
        return "[res_allocation %s @ %s]" % (self.vcpu_list, self.location_property)

class ProvisionVM(object):
    """
    the class to keep vm information for provisioning, flavor is the id of a flavor, zone is the availability zone name in the cloud
    """
    def __init__(self, flavor, zone, resource_name, static=False):
        self.flavor=flavor
        self.zone=zone
        self.resource_name=resource_name
        self.static=static
    def __repr__(self):
        return "[flavor: %s zone: %s resource_name: %s static: %s]" % (self.flavor, self.zone, self.resource_name, self.static)
    
class StaticVMs(object):
    """
    the class to keep static VM info, from config
    location is the location property used in job submit script
    location_properties is from config that keeps the mapping between location property (short name) and availability zone name (name in cloud)
    """
    def __init__(self):
        self.static_list=[]
    def add_static_req(self, location, num_of_vm):
        found=False
        for req in self.static_list:
            if req["location"]==location:
                req["num_of_vm"]+=num_of_vm
                found=True
                break
        if not found:
            self.static_list.append({"location":location, "num_of_vm":num_of_vm})
    def need_more(self):
        for req in self.static_list:
            if req["num_of_vm"]>0:
                return True
        return False
    def need_vm(self,vm,location_properties):
        log.debug("location_properties %s"%location_properties)
        for req in self.static_list:
            log.debug("req %s vm %s"%(req,vm))
            if (not location_properties or location_properties[req["location"]]==vm.availability_zone) and req["num_of_vm"]>0:
                req["num_of_vm"]-=1
                return True
        return False
    def get_provision_list(self, flavor, resource_name, location_properties):
        provision_list=[]
        for req in self.static_list:
            zone=None
            if location_properties:
                zone=location_properties[req["location"]]
            provision_list.extend([ProvisionVM(flavor.id, zone, resource_name, True)]*req["num_of_vm"])
        return provision_list
    def __repr__(self):
        str=""
        for req in self.static_list:
            str+="(location %s core_per_vm %d number_of_vms %d)" % (req["location"],req["core_per_vm"],req["num_of_vm"])
        return str
        
class ICloud(object):
    def vm_start(self, **args):
        '''
        Create a new VM
        '''
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define vm_start'

    def vm_destroy(self, **args):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define vm_destroy'

    def vm_check(self, **args):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define vm_check'

    def vm_list(self):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define vm_list'

    def get_flavor_list(self):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define get_flavor_list'

    def add_security_group_rule(self, **args):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define add_security_group_rule'

    def remove_security_group_rule(self, **args):
        log.debug('This method should be defined by all subclasses of ICloud\n')
        assert 0, 'Must define remove_security_group_rule'
