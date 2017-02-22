#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque resource management class
## This is the main class of active mode, it monitors Torque queue and launch/destroy worker nodes accordingly
##

##
## IMPORTS
##
from __future__ import with_statement
import os
import logging
import threading
import shlex
import subprocess
import dynamictorque.config as config
import dynamictorque.local_commands as commands
import string
import datetime
import time
import re
from dynamictorque.cloud_tools import VMFlavor
from dynamictorque.cloud_tools import VM
from dynamictorque.cloud_tools import ProvisionVM
from dynamictorque.job_scheduler import calculate_new_instances
from dynamictorque.cloud_management import CloudManager
import xml.etree.ElementTree as ET
from random import choice

log = logging.getLogger("dynamictorque")

class ResourceCenter(object):
    def __init__(self, name="ResourceCenter"):
        log.verbose("New object %s created" %name)
        self.name = name
        # self states
        self.sleep_mode = False
        self.write_lock = threading.Lock()
        # cluster states
        self.last_query = None
        self.idle_jobs = []
        self.total_number_of_idle_jobs = 0
        self.running_jobs = []
        self.number_of_wn = 0
        self.worker_nodes = []
        self.provisioning = False
        self.pbs_server_up = True
        self.maui_server_up = True
        # cloud states
        self.cloud_manager=CloudManager()
        self.existing_instances=[]
        self.starting_instances=[]
        self.deleting_instances=[]
        self.provision_waiting_list=[]
        log.debug("config.torque_queue_to_monitor %s"%config.torque_queue_to_monitor)
        # initiate
        self._load_existing_worker_nodes()
        
    def get_info(self):
        """ gather all information for admin.py """
        info={"existing_instances": self.existing_instances,
              "starting_instances": self.starting_instances,
              "deleting_instances": self.deleting_instances,
              "provision_waiting_list": self.provision_waiting_list,
              "worker_nodes": self.worker_nodes,
              "provisioning": self.provisioning,
              "sleep_mode": self.sleep_mode,
              "pbs_server_up": self.pbs_server_up,
              "maui_server_up": self.maui_server_up,
              "idle_jobs": self.idle_jobs,
              "total_number_of_idle_jobs": self.total_number_of_idle_jobs,
              "cloud_resources": config.cloud_resources,
              "running_jobs": self.running_jobs}
        return info
    
    def toggle_sleep_mode(self):
        """ toggle sleep mode
        """
        self.sleep_mode=not self.sleep_mode
        log.info("Dynamic Torque in sleep mode: %s" % self.sleep_mode)
    
    def kill_vm(self, vm_name, forceoff=False):
        """ kill a vm
            vm_name: the hostname of the VM to kill
            forceoff: if True the node will be shut down if jobs are running (will wait for jobs to finish)
                        if False the node will not be killed if jobs are running
        """
        vm=None
        for v in self.existing_instances:
            if v.hostname==vm_name:
                vm=v
                break
        if not vm:
            raise Exception("%s not found in vm list"%vm_name)
        wn = self.find_wn_from_vm(vm)
        if not wn:
            raise Exception("%s is not a worker node"%vm_name)
        state=commands.check_node(wn["name"])
        if "jobs" in wn and not forceoff:
            raise Exception("%s is busy, can't be killed"%vm_name)
        vm.force_off=forceoff
        log.info("killing %s"%vm_name)
        commands.hold_node_in_torque(vm)
        with self.write_lock:
            self.deleting_instances.append(vm)
            self.existing_instances.remove(vm)

    def get_detail(self, vm_name):
        """ get details of a vm
            vm_name: the hostname of the VM to get details
        """
        vm=None
        for v in self.existing_instances:
            if v.hostname==vm_name:
                vm=v
                break
        if not vm:
            raise Exception("%s not found in vm list"%vm_name)
        wn = self.find_wn_from_vm(vm)
        if not wn:
            raise Exception("%s is not a worker node"%vm_name)
        return vm, wn
        
    def forceoff(self):
        """ force all worker nodes to shut down """
        for vm in self.existing_instances:
            log.info("killing existing vm %s"%vm.hostname)
            vm.force_off=True
            #commands.hold_node_in_torque(vm)
            log.info("removing it from the torque cluster")
            commands.remove_node_from_torque(vm)
            log.info("removing it from the /etc/hosts file")
            commands.remove_node_from_hosts_file(vm)
            log.info("removing it from the known_hosts file")
            commands.remove_node_from_known_hosts_file(vm)
            log.info("destroying the vm")
            self.cloud_manager.cloud_backend.vm_destroy(vm)
        with self.write_lock:
            self.deleting_instances.extend(self.existing_instances)
            self.existing_instances=[]
        for vm in self.starting_instances:
            log.info("killing starting vm %s"%vm.hostname)
            self.cloud_manager.cloud_backend.vm_destroy(vm)
        with self.write_lock:
            self.deleting_instances.extend(self.starting_instances)
            self.starting_instances=[]
        
    
    def _load_existing_worker_nodes(self):
        """
        Get a list of worker nodes from OpenStack and see if they are being used by Torque 
        """
        # get a list of all nodes from the cloud (with the prefix)
        self.existing_instances=self.cloud_manager.load_all_existing_worker_nodes()
        to_delete=[]
        to_starting=[]
        persistent_nodes=commands.read_nodes_from_persistent_file()
        log.debug("existing_instances %s"%self.existing_instances)
        self.pbs_server_up, self.worker_nodes = commands.wn_query()
        self.number_of_wn = len(self.worker_nodes)
        self.last_query = datetime.datetime.now()
        # check nodes from the cloud, to see if they are in torque
        for vm in self.existing_instances:
            if vm.ip is not None:
                #hostname=commands.hostname_lookup(vm.ip)
                hostname=vm.hostname
                if hostname is not None:
                    log.debug("vm %s has hostname %s"%(vm.ip, hostname))
                    vm.hostname=hostname
                    the_wn = self.find_wn_from_vm(vm)
                    log.debug("wn %s"%the_wn)
                    if the_wn is None:
                        if hostname in persistent_nodes:
                            to_starting.append(vm)
                        else:
                            to_delete.append(vm)
                    else:
                        if "jobs" not in the_wn and vm.image_id!=config.cloud_resources[vm.cloud_resource_name].image_uuid:
                            log.info("vm %s is not running jobs and its image id is not the same as the current one, delete it" % vm)
                            to_delete.append(vm)
                        else:
                            if ("offline" in the_wn['state'] or "down" in the_wn['state']):
                                to_delete.append(vm)
                                log.info("vm %s is offline or down, delete it" % vm)
                            else:
                                log.info("vm %s is already a worker node in torque" % vm)
            else:
                log.info("vm %s is not ready, destroying it..." % vm)
                to_delete.append(vm) 
                
        # check nodes from pbsnodes, to see if they are in the cloud (if its name has the prefix)
        wn_to_delete=[]
        for wn in self.worker_nodes:
            vm=self.find_vm_from_wn(wn)
            if not vm and ("down" in wn['state'] or "offline" in wn['state']):
                log.info("wn %s is an orphan node, the vm doesn't not exist, delete it from torque." % wn)
                dummy_vm=VM("0","dummy")
                dummy_vm.hostname=wn['name']
                commands.remove_node_from_torque(dummy_vm)
                wn_to_delete.append(wn)
        for wn in wn_to_delete:
            self.worker_nodes.remove(wn)
            
        #log.debug("existing_instances %s"%self.existing_instances)
        log.debug("to_delete %s"%to_delete)
        # move nodes to starting list or delete them if necessary
        for vm in to_starting:
            with self.write_lock:
                self.existing_instances.remove(vm)
                self.starting_instances.append(vm)
        for vm in to_delete:
            log.info("vm %s is not being used by torque, destroying it..." % vm)
            self.cloud_manager.cloud_backend.vm_destroy(vm)
            with self.write_lock:
                self.existing_instances.remove(vm)
                self.deleting_instances.append(vm)
                
        # check if we have enough static worker nodes and mark some existing nodes to be static
        for resource in config.cloud_resources:
            existing_instances_of_resource=[vm for vm in self.existing_instances if vm.cloud_resource_name==resource]
            static_vms_to_start=config.cloud_resources[resource].static_vms_to_start
            if static_vms_to_start.need_more():
                for vm in existing_instances_of_resource:
                    if vm.flavor.name==config.cloud_resources[resource].worker_node_flavor and static_vms_to_start.need_vm(vm,config.location_properties): #vm.vcpu_number==self.static_core_per_vm and self.static_vms_to_start>0:
                        log.debug("VM %s is set to be static" % vm)
                        vm.dynamic=False
                    
            # check if we overused, if yes, kill some
            num_of_instances=len([vm for vm in existing_instances_of_resource if vm.dynamic])
            while num_of_instances>config.cloud_resources[resource].number_of_dynamic_worker_nodes:
                log.debug("used more vms than config: vms used %d  number configed %d" % (num_of_instances,config.cloud_resources[resource].number_of_dynamic_worker_nodes))
                vm=existing_instances_of_resource.pop()
                wn=self.find_wn_from_vm(vm)
                if not vm.dynamic or (wn and "jobs" in wn):
                    continue
                log.info("deleting %s because we overused" % vm)
                self.cloud_manager.cloud_backend.vm_destroy(vm)
                with self.write_lock:
                    self.existing_instances.remove(vm)
                    self.deleting_instances.append(vm)
                num_of_instances-=1
            config.cloud_resources[resource].available_number_of_nodes=config.cloud_resources[resource].number_of_dynamic_worker_nodes-num_of_instances
            
            # if we don't have enough static, launch more
            if static_vms_to_start.need_more():
                self.provision_waiting_list.extend(static_vms_to_start.get_provision_list(config.cloud_resources[resource].flavor_objects[0],resource,config.location_properties))
        if len(self.starting_instances)>0:
            with self.write_lock:
                self.provisioning=True
        if len(self.provision_waiting_list):
            self.launch_instances()
                    
    def find_wn_from_vm(self, vm):
        return next((wn for wn in self.worker_nodes if wn['name'] == vm.hostname), None)

    def find_vm_from_wn(self, wn):
        return next((vm for vm in self.existing_instances if vm.hostname==wn['name']), None)
        
    def collect_cluster_information(self):
        """ check job queue and nodes list, find difference"""
        self.pbs_server_up, self.total_number_of_idle_jobs, self.idle_jobs, self.running_jobs = commands.job_query()
        if not self.pbs_server_up:
            return
        self.prioritise_jobs()
        self.pbs_server_up, self.worker_nodes = commands.wn_query()
        if not self.pbs_server_up:
            return
        self.number_of_wn = len(self.worker_nodes)
        self.last_query = datetime.datetime.now()
        if self.sleep_mode or not self.pbs_server_up or not self.maui_server_up:
            return
        if not self.provisioning:
            log.verbose("checking existing worker nodes")
            self.check_existing_worker_nodes()
            if not self.has_available_cores():
                return
            self.determine_required_instances_numbers()
        
    def has_available_cores(self):
        for resource in config.cloud_resources:
            if config.cloud_resources[resource].available_number_of_nodes>0:
                return True
        return False
    
    
    def prioritise_jobs(self):
        """ give each job a priority """
        self.maui_server_up, job_priorities=commands.get_job_priorities()
        if not self.maui_server_up:
            return
        log.verbose("job_priorities %d %s" % (len(job_priorities),job_priorities))
        if len(job_priorities)>0:
            idx=0
            for job in self.idle_jobs:
                job_id=int(job["Job_Id"].split(".")[0].split("[")[0])
                log.verbose("compare %d %d %d"  % (job_id, idx, job_priorities[idx]["Job_Id"]))
                while job_id>job_priorities[idx]["Job_Id"] and idx<len(job_priorities)-1:
                    idx+=1
                if job_id==job_priorities[idx]["Job_Id"]:
                    job["job_priority"]=job_priorities[idx]["priority"]
                    idx+=1
                elif job_id>job_priorities[idx]["Job_Id"] and idx==len(job_priorities)-1:
                    break
                if idx>=len(job_priorities):
                    break
                else:
                    continue
        self.idle_jobs.sort(key=lambda job: job["job_priority"], reverse=True)
        log.verbose("self.idle_jobs %d" % len(self.idle_jobs))
        
    def check_existing_worker_nodes(self):
        """
        check if there needs more worker nodes, or less
        case 1: there are idle jobs, no free worker nodes:
                launch more worker nodes based on job's priority
        case 2: there are idle jobs and free worker nodes:
                free worker nodes cannot be used to run idle jobs
                shut down those worker nodes and launch new ones
        case 3: there are idle jobs and free static worker nodes
                not corresponding with the base flavor for static
                nodes. Then launch a new static instance with the
                base flavor and shut down the bigger one
        case 4: there are no idle jobs but free worker nodes:
                shut down those worker nodes
        """
        for wn in self.worker_nodes:
            to_delete=False
            the_vm = self.find_vm_from_wn(wn)
            if the_vm is not None:
                state=commands.check_node(wn["name"])
                if the_vm.state != state:
                    the_vm.state_time=0
                else:
                    the_vm.state_time+=config.job_poller_interval
                the_vm.state = state
                if the_vm.image_id!=config.cloud_resources[the_vm.cloud_resource_name].image_uuid:
                    log.info("vm %s is launched from a different image than the current one in config, hold it from running more jobs" % the_vm)
                    commands.hold_node_in_torque(the_vm)
                if "jobs" not in wn:
                    if state=="free" and the_vm.state_time > config.max_idle_time:
                        if the_vm.dynamic:
                            log.info("wn %s has been idle for %i seconds, shutting down..." % (wn["name"], the_vm.state_time))
                            log.info("killing existing vm %s"%the_vm.hostname)
                            the_vm.force_off=True
                            log.info("removing it from the torque cluster")
                            commands.remove_node_from_torque(the_vm)
                            log.info("removing it from the /etc/hosts file")
                            commands.remove_node_from_hosts_file(the_vm)
                            log.info("removing it from the known_hosts file")
                            commands.remove_node_from_known_hosts_file(the_vm)
                            log.info("destroying the vm")
                            self.cloud_manager.cloud_backend.vm_destroy(the_vm)
                            if the_vm in self.existing_instances:
                                log.verbose("instance to be deleted present in existing_instances")
                                with self.write_lock:
                                    self.existing_instances.remove(the_vm)
                            self.update_available_cores()
                            self.provisioning=False
                        else: 
                            # if there are running jobs, and the static node is idle, the job may be running in a dynamic vm, 
                            # then change that dynamic vm to be static and make this static vm to be dynamic and shut it down 
                            if len(self.running_jobs)>0:
                                for another_wn in self.worker_nodes:
                                    if another_wn['name']!=wn['name'] and "jobs" in another_wn:
                                        another_vm = self.find_vm_from_wn(another_wn)
                                        if another_vm and another_vm.dynamic and another_vm.vcpu_number==the_vm.vcpu_number and another_vm.availability_zone==the_vm.availability_zone and another_vm.cloud_resource_name==the_vm.cloud_resource_name:
                                            # swap
                                            log.info("%s has jobs running, swap it with %s" % (another_vm, the_vm))
                                            the_vm.dynamic=True
                                            another_vm.dynamic=False
                                            log.info("killing existing vm %s"%the_vm.hostname)
                                            the_vm.force_off=True
                                            log.info("removing it from the torque cluster")
                                            commands.remove_node_from_torque(the_vm)
                                            log.info("removing it from the /etc/hosts file")
                                            commands.remove_node_from_hosts_file(the_vm)
                                            log.info("removing it from the known_hosts file")
                                            commands.remove_node_from_known_hosts_file(the_vm)
                                            log.info("destroying the vm")
                                            self.cloud_manager.cloud_backend.vm_destroy(the_vm)
                                            if the_vm in self.existing_instances:
                                                log.verbose("instance to be deleted present in existing_instances")
                                                with self.write_lock:
                                                    self.existing_instances.remove(the_vm)
                                            self.update_available_cores()
                                            self.provisioning=False
                                            break
                                        elif not another_vm:
                                            log.error("can't find WN %s from the cloud" % another_wn)
                            # check if the static node flavor that has no jobs assigned
                            # is not the base flavor
                            if the_vm.flavor.name != config.cloud_resources[the_vm.cloud_resource_name].worker_node_flavors[0]:
                                log.verbose("the_vm.hostname: %s became static and it should not remain as static because is not using the base flavor: %s"%(the_vm.hostname, config.cloud_resources[the_vm.cloud_resource_name].flavor_objects[0].name))
                    elif state=="drained":
                        to_delete=True
                    elif state and "down" in wn['state'].lower() and "down" in state and the_vm.state_time > config.max_down_time:
                        # TODO: may need to remove jobs too
                        log.info("wn %s has been down for %i seconds, shutting down..." % (wn["name"], the_vm.state_time))
                        to_delete=True
            else:
                log.verbose("wn %s is not found in the cloud" % wn["name"])
            if to_delete:
                with self.write_lock:
                    self.deleting_instances.append(the_vm)
                    self.existing_instances.remove(the_vm)

        self.update_available_cores()
        
    def determine_required_instances_numbers(self):
        flavor_list=[]
        log.debug("Calculating the new number of required instances")
        if len(self.idle_jobs)>0:
            #log.debug("worker_nodes %s"%self.worker_nodes)
            log.debug("Calculating the new number of required instances")
            flavor_list=calculate_new_instances(self.idle_jobs, self.number_of_wn)
        if len(flavor_list)>0 and not self.provisioning:
            log.info("to_launch_flavor_list %s" % flavor_list)
            with self.write_lock:
                self.provision_waiting_list.extend(flavor_list)
            #self.launch_instances()
                self.provisioning=True
            
    def update_available_cores(self):
        with self.write_lock:
            for res in config.cloud_resources:
                num_used=sum(1 for vm in self.existing_instances if vm.dynamic and vm.cloud_resource_name==res)+sum(1 for vm in self.deleting_instances if vm.dynamic and vm.cloud_resource_name==res)
                config.cloud_resources[res].available_number_of_nodes=config.cloud_resources[res].number_of_dynamic_worker_nodes-num_used
        
    def launch_instances(self):
        log.verbose("launch_instances %s %s"%(self.provision_waiting_list,self.starting_instances))
        if len(self.provision_waiting_list)>0 and len(self.starting_instances)<config.vm_creation_batch_number:
            with self.write_lock:
                self.provisioning=True
            vm_number=config.vm_creation_batch_number-len(self.starting_instances)
            to_remove_from_list=[]
            log.debug("launch VMs by provision_waiting_list %s"%self.provision_waiting_list)
            starting_cores=0
            for vm in self.provision_waiting_list:
                if vm_number==0:
                    if not vm.static:
                        to_remove_from_list.append(vm)
                    continue
                log.debug("provision vm %s"% (vm) )
                new_vm=self.cloud_manager.cloud_backend.vm_start(vm.flavor,vm.zone,vm.resource_name)
                if new_vm is not None:
                    with self.write_lock:
                        self.starting_instances.append(new_vm)
                    to_remove_from_list.append(vm)
                    starting_cores+=new_vm.vcpu_number
                    vm_number-=1
                else:
                    log.error("Cannot create VM due to cloud problem, wait for next try...")
                    break
            # clean the list because requirements may have changed
            with self.write_lock:
                for f in to_remove_from_list:
                    self.provision_waiting_list.remove(f)
                

    def update_provision_status(self):
        """ 
        update states of starting instances
        start new ones if some starting ones are done, and there are waiting ones
        """
        to_delete=[]
        ready_to_use=[]
        for vm in self.starting_instances:
            if not vm.cloud_ready:
                state = self.cloud_manager.cloud_backend.vm_check(vm)
                creation_time=datetime.datetime.strptime(vm.start_time, "%Y-%m-%dT%H:%M:%SZ")
                if state == 0:
                    log.info("vm %s is ready in the cloud, add it to torque..." % vm.ip)
                    #hostname=commands.hostname_lookup(vm.ip)
                    hostname=vm.hostname
                    if hostname is not None:
                        log.debug("vm %s has hostname %s"%(vm.ip, hostname))
                        vm.hostname=hostname
                    vm.cloud_ready=True
                    # add the worker node to torque
                    retry=5
                    while retry>0:
                        ret=commands.add_node_to_torque(vm)
                        if ret:
                            break
                        retry-=1
                        time.sleep(1)
                    if not ret:
                        log.error("cannot add %s to torque, delete it" % vm.hostname)
                        to_delete.append(vm)
                        continue
                    #check if the new VM is added to torque
                    retry=60
                    while retry>0:
                        node_state = commands.check_node(vm.hostname)
                        if node_state is not None:
                            break
                        retry-=1
                        log.debug("vm %s is not showing in maui yet" % vm.hostname)
                        time.sleep(1)
                    if node_state is None:
                        log.error("cannot see %s in maui, delete it" % vm.hostname)
                        commands.remove_node_from_torque(vm)
                        to_delete.append(vm)
                        continue
                    # update local list
                    self.pbs_server_up, self.worker_nodes = commands.wn_query()
                    # set account string to wn
                    cloud_res=config.cloud_resources[vm.cloud_resource_name]
                    if cloud_res and cloud_res.account_string and cloud_res.reservation_type:
                        commands.set_res_for_node(vm, cloud_res.reservation_type, cloud_res.account_string)
                    commands.post_add_node_action(vm)
                    if config.node_property:
                        commands.set_node_property(vm, config.node_property)
                        time.sleep(2)
                    if cloud_res and cloud_res.account_string:
                        commands.add_node_property(vm, cloud_res.account_string)
                        time.sleep(2)
                    for loc in config.location_properties:
                        if config.location_properties[loc]==vm.availability_zone:
                            commands.add_node_property(vm, loc)
                            time.sleep(2)
                    commands.set_np(vm, vm.vcpu_number)
                    time.sleep(2)
                    commands.set_node_online(vm)
                    time.sleep(2)
                    #ready, add to torque
                elif state == 1:
                    if not vm.post_provision_command_executed:
                        commands.post_vm_provision_action(vm)
                        # open firewall for nfs
                        if vm.cloud_resource_name=="default":
                            #open firewall for it to access other nfs servers
                            for res in config.cloud_resources.keys():
                                if res!="default" and config.cloud_resources[res].has_volume:
                                    self.cloud_manager.cloud_backend.add_security_group_rule(res,config.cloud_security_groups[0]+"-nfs","TCP",vm.ip+"/32",2049,2049)
                        vm.post_provision_command_executed=True
                    log.info("vm %s: cloud-init is running..." % vm.name)
                    length=(datetime.datetime.utcnow()-creation_time).seconds
                    if length>config.max_inaccessible_time:
                        log.debug("datetime.datetime.utcnow() %s vm.start_time %s"%(datetime.datetime.utcnow(),creation_time))
                        log.info("vm %s: it takes too long (%i seconds) to run cloud-init, delete it and try again" % (vm.name,length))
                        to_delete.append(vm)
                elif state == 2:
                    log.info("vm %s: the cloud is building the vm" % vm.name)
                    length=(datetime.datetime.utcnow()-creation_time).seconds
                    if length>config.max_inaccessible_time:
                        log.debug("datetime.datetime.utcnow() %s vm.start_time %s"%(datetime.datetime.utcnow(),creation_time))
                        log.info("vm %s: it takes too long (%i seconds) to build, delete it and try again" % (vm.name,length))
                        to_delete.append(vm)
                elif state == 3:
                    log.info("vm %s: has gone" % vm.name)
                    to_delete.append(vm)
                elif state == 4:
                    log.info("vm %s: is in error state, going to destroy it and start a new one" % vm.name)
                    to_delete.append(vm)
            else:
                wn = commands.get_wn_in_torque(vm)
                if wn and len(wn) > 0:
                    vm_state_in_torque = wn['state']
                    log.debug("vm %s is in state %s in torque"%(vm.hostname,vm_state_in_torque))
                    if vm_state_in_torque=="free" or vm_state_in_torque=="job-exclusive":
                        log.info("vm %s: is ready in torque" % vm.name)
                        ready_to_use.append(vm)
                    else:
                        #vm_state_in_maui, length=commands.check_node(vm.hostname)
                        #vm.state_time=length
                        log.debug("vm %s is in %s in torque" % (vm.hostname, vm_state_in_torque))
                        # why need this?
                        # commands.set_node_online(vm)
                        if vm.state_time>config.max_inaccessible_time:
                            log.info("vm is %s in torque, it doesn't come up properly, going to destroy it" % vm_state_in_torque)
                            to_delete.append(vm)
        if len(ready_to_use)>0:
            dump_nodes=True
        else:
            dump_nodes=False
        with self.write_lock:
            for vm in ready_to_use:
                self.starting_instances.remove(vm)
                static_vms_to_start=config.cloud_resources[vm.cloud_resource_name].static_vms_to_start
                if static_vms_to_start.need_vm(vm,config.location_properties):
                    vm.dynamic=False
                vm.ready_time=datetime.datetime.utcnow()
                self.existing_instances.append(vm)
        for vm in to_delete:
            if vm.flavor is not None and vm.availability_zone is not None:
                self.provision_waiting_list.append(ProvisionVM(vm.flavor,vm.availability_zone,vm.cloud_resource_name,not vm.dynamic))
            self.cloud_manager.cloud_backend.vm_destroy(vm)
            with self.write_lock:
                self.starting_instances.remove(vm)
                self.deleting_instances.append(vm)
        self.update_available_cores()
        if dump_nodes:
            commands.dump_nodes_to_persistent_file(self.existing_instances)
        #if self.available_cores>0 or self.static_vms_to_start.need_more():
        if len(self.starting_instances)==0 and len(self.provision_waiting_list)==0:
            with self.write_lock:
                self.provisioning=False
        else:
            self.launch_instances()

        
    def check_cleanup(self):
        """
        This method checks deletion status by going through each item in self.deleting_instances
        """
        if len(self.deleting_instances)==0:
            return
        vm_deleted=[]
        vm_executing=[]
        for vm in self.deleting_instances:
            state=self.cloud_manager.cloud_backend.vm_check(vm)
            log.info("cloud state of vm %s is %d."%(vm,state))
            if not vm.hostname:
                if state==3:
                    log.info("vm %s has never been used by torque and has been destroyed from the cloud."%vm)
                    vm_deleted.append(vm)
            else:
                wn = commands.get_wn_in_torque(vm)
                log.info("torque state of vm %s is %s."%(vm,wn))
                if wn is not None and len(wn) == 0:
                    log.info("vm %s is not in torque, check the cloud" % vm)
                    if state==3:
                        log.info("vm %s has been destroyed from the cloud"%vm)
                        vm_deleted.append(vm)
                    else:
                        if vm.delete_time is None or (vm.delete_time-datetime.datetime.utcnow()).seconds>config.max_delete_retry_time:
                            log.info("vm %s can't be deleted from the cloud, try again..."%vm)
                            self.cloud_manager.cloud_backend.vm_destroy(vm)
                elif wn is not None and len(wn) > 0:
                    if state==3:
                        log.debug("vm %s is in torque, but not in the cloud, remove it from torque" % vm)
                        commands.release_res_for_node(vm)
                        commands.remove_node_from_torque(vm)
                    else:
                        vm_state_in_torque = wn['state']
                        if "jobs" in wn:
                            if not vm.force_off:
                                log.info("vm %s has jobs running again, cancel destroying" % vm)
                                vm_executing.append(vm)
                            else:
                                log.debug("vm %s has jobs running, but its force-off value is %s" % (vm, vm.force_off))
                        else:
                            #vm_state_in_maui, length=commands.check_node(vm.hostname)
                            #vm.state_time=length
                            log.info("vm is %s in torque, destroy it in the cloud" % vm_state_in_torque)
                            commands.release_res_for_node(vm)
                            commands.remove_node_from_torque(vm)
                            self.cloud_manager.cloud_backend.vm_destroy(vm)
                            vm.delete_time = datetime.datetime.utcnow()
        if len(vm_deleted)>0 or len(vm_executing)>0:
            dump_nodes=True
        else:
            dump_nodes=False
        with self.write_lock:
            for vm in vm_deleted:
                self.deleting_instances.remove(vm)
                commands.post_vm_destroy_action(vm)
                commands.post_remove_node_action(vm)
                if vm.cloud_resource_name=="default":
                    #close firewall for it to access other nfs servers
                    for res in config.cloud_resources.keys():
                        if res!="default" and config.cloud_resources[res].has_volume and vm.ip is not None:
                            self.cloud_manager.cloud_backend.remove_security_group_rule(res,config.cloud_security_groups[0]+"-nfs","TCP",vm.ip+"/32",2049,2049)
                if not vm.dynamic:
                    log.debug("vm %s is static and deleted, need to launch another one to replace it" % vm)
                    location_property=None
                    for loc in config.location_properties:
                        if config.location_properties[loc]==vm.availability_zone:
                            location_property=loc
                            break
                    if not location_property:
                        continue
                    config.cloud_resources[vm.cloud_resource_name].static_vms_to_start.add_static_req(location_property, 1)
                    if vm.flavor:
                        self.provision_waiting_list.append(ProvisionVM(vm.flavor,vm.availability_zone,vm.cloud_resource_name,not vm.dynamic))
                    else:
                        for f in self.flavors:
                            if f.vcpus==vm.vcpu_number:
                                self.provision_waiting_list.append(ProvisionVM(f.id,vm.availability_zone,vm.cloud_resource_name,not vm.dynamic))
                                break
            for vm in vm_executing:
                self.existing_instances.append(vm)
                self.deleting_instances.remove(vm)
                commands.release_node_in_torque(vm)
        self.update_available_cores()
        if dump_nodes:
            commands.dump_nodes_to_persistent_file(self.existing_instances)
        if len(self.provision_waiting_list)>0 and not self.provisioning:
            self.launch_instances()
