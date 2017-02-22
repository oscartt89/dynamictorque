#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2014 eResearch SA
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 21/05/2014.
##
## a class to work out how many new instances need to launch

import dynamictorque.utilities as utilities
import dynamictorque.config as config
from dynamictorque.cloud_tools import ResAllocation
from dynamictorque.cloud_tools import ProvisionVM
from dynamictorque.config import convert_location_property_to_availability_zone

log = utilities.get_logger()

def calculate_new_instances(idle_jobs, number_of_wn):
    log.debug("number_of_wn %d"%number_of_wn)
    req_list={}
    for job in idle_jobs:
        log.verbose("idle_job %s"%job)
        if job['job_priority']==-1 and number_of_wn>0:
            continue
        vcpu_requirement, location_property, account_string = _get_vcpu_requirement(job)
        #if account_string is None:
        #    account_string="default"
        if account_string not in config.cloud_resources:
            account_string="default"
        if not vcpu_requirement:
            continue
        log.debug("vcpu_requirement %s location_property %s account_string %s "%(vcpu_requirement,location_property,account_string))
        # if only one node, check mem requirement
        #if len(vcpu_requirement)==1:
        #    mem_requirement=_get_mem_requirement(job)
            # to-do, if mem_reqirement exceeds 4G per core, do something
        if account_string!="default" and have_enough_cores(req_list, account_string, vcpu_requirement):
            log.debug("%s has enough cores" % account_string)
            add_new_requirement_to_list(req_list, vcpu_requirement,location_property, account_string)
        elif have_enough_cores(req_list, "default", vcpu_requirement) and account_string!=location_property:
            log.debug("%s doesn't have enough cores, but default has, use default's cores" % account_string)
            add_new_requirement_to_list(req_list, vcpu_requirement,location_property, "default")
        log.debug("req_list %s"%req_list)
    if len(req_list)>0:
        return convert_req_list_to_flavor(req_list)
    return []

def have_enough_cores(req_list, account_string, vcpu_requirement):
    total_num_vcpus=0
    if account_string in req_list:
        total_num_vcpus=sum(i.get_total_num_cores() for i in req_list[account_string])
    num_vcpus_to_add=sum(i for i in vcpu_requirement)
    if total_num_vcpus+num_vcpus_to_add>config.cloud_resources[account_string].available_cores():
        return False
    log.verbose("max vcpus: %d"%config.cloud_resources[account_string].flavor_objects[0].vcpus)
    if vcpu_requirement[0] > config.cloud_resources[account_string].flavor_objects[0].vcpus:
        return False
    return True

def add_new_requirement_to_list(req_list, vcpu_requirement, location_property, account_string):
    if account_string not in req_list:
        node_list=[]
        for v in vcpu_requirement:
            node_list.append(ResAllocation(v,location_property))
        req_list[account_string]=node_list
    else:
        node_list=req_list[account_string]
        node_list.sort(key=lambda res:res.get_total_num_cores(), reverse=True)
        idx=0
        for res in node_list:
            if res.location_property!=location_property:
                continue
            if res.get_total_num_cores()+vcpu_requirement[idx]<=config.cloud_resources[account_string].flavor_objects[0].vcpus and res.location_property==location_property:
                res.vcpu_list.append(vcpu_requirement[idx])
                idx+=1
        if idx<len(vcpu_requirement):
            for v in vcpu_requirement[idx:]:
                node_list.append(ResAllocation(v,location_property))

def convert_req_list_to_flavor(req_list):
    flavor_list=[]
    for resource in req_list:
        for node in req_list[resource]:
            flavor_id = best_flavor_from_node(resource, node)
            flavor_list.append(ProvisionVM(flavor_id,convert_location_property_to_availability_zone(node.location_property),resource))
    return flavor_list

def best_flavor_from_node(resource, res_alloc):
    ncpus = sum(res_alloc.vcpu_list)
    tmp = []
    tmp.extend(config.cloud_resources[resource].flavor_objects)
    tmp.sort(key=lambda flavor:flavor.vcpus, reverse=False)
    for flavor in tmp:
        if flavor.vcpus >= ncpus:
            return flavor.id
    log.verbose("Any flavor fitting the required number of cpus: %d. Using flavor: %s"%(ncpus, tmp[0].name))
    return tmp[0].id

def _get_vcpu_requirement(job):
    account_string = None
    if "Account_Name" in job:
        account_string=job["Account_Name"]
    else:
        account_string=job["queue"]
    if "Resource_List.neednodes" in job and "Resource_List.ncpus" in job:
        num_cores=1
        num_nodes=1
        if job["Resource_List.neednodes"].isdigit():
            num_nodes=int(job["Resource_List.neednodes"])
        if job["Resource_List.ncpus"].isdigit():
            num_cores=int(job["Resource_List.ncpus"])
        log.verbose("num_cores: %s num_nodes: %s"%(num_cores, num_nodes))
        return [num_cores]*num_nodes, config.get_default_node_location(), account_string
    if "Resource_List.nodes" in job:
        return [int(job["Resource_List.nodes"])], config.get_default_node_location(), account_string
    if ("Resource_List.ncpus" not in job) and ("Resource_List.neednodes" not in job):
        return [1], config.get_default_node_location(), account_string
    return None, None, account_string

# to-do
def _get_mem_requirement(job):
    #if "Resource_List.mem" in job:
    #    if job["Resource_List.mem"].lower().endswith("tb"):
    #        break
    return None
