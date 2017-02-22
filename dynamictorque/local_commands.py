#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2014 eResearch SA
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 21/05/2014.
##
## a class to execute cli commands, e.g. torque commands, maui commands, shell commands

import subprocess
import dynamictorque.utilities as utilities
import re
import shlex
import dynamictorque.config as config
import string
import xml.etree.ElementTree as ET
import socket
import os

log = utilities.get_logger()

def wn_query():
    """ query worker nodes """
    log.verbose("Querying Torque with %s" % config.pbsnodes_command.format("-x", ""))
    try:
        pbsnodes = shlex.split(config.pbsnodes_command.format("-x", ""))
        sp = subprocess.Popen(pbsnodes, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (query_out, query_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(pbsnodes, " "))
        return False, []

    if returncode != 0:
        if "No nodes found" not in query_err:
            log.error("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                          (returncode, string.join(pbsnodes, " "), query_err))
            pbs_server_up = False
        else:
            pbs_server_up = True
        return pbs_server_up, []

    return True, _pbsnodes_to_node_list(query_out)

def get_wn_in_torque(vm):
    """ query worker node """
    log.verbose("Querying Torque with %s" % config.pbsnodes_command.format("-x", vm.hostname))
    try:
        pbsnodes = shlex.split(config.pbsnodes_command.format("-x", vm.hostname))
        sp = subprocess.Popen(pbsnodes, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (query_out, query_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(pbsnodes, " "))
        return None

    if returncode != 0:
        if "cannot locate specified node" in query_err:
            return {}
        log.error("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                          (returncode, string.join(pbsnodes, " "), query_err))
        return None
    nodes = _pbsnodes_to_node_list(query_out)
    for node in nodes:
        if node["name"]==vm.hostname:
            return node
    return None

def job_query():
    """job_query_local -- query and parse condor_q for job information."""
    log.verbose("Querying Torque with %s" % config.qstat_command)
    try:
        qstat = shlex.split(config.qstat_command)
        sp = subprocess.Popen(qstat, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (query_out, query_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(qstat, " "))
        return False, 0, [], []

    if returncode != 0:
        log.error("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                          (returncode, string.join(qstat, " "), query_err))
        return False, 0, [], []

    if query_out.strip()=="":
        return True, 0, [], []
    total_number_of_idle_jobs, idle_jobs, running_jobs = _qstat_to_job_list(query_out)
    return True, total_number_of_idle_jobs, idle_jobs, running_jobs

def get_job_priorities():
    """ give each job a priority """
    log.verbose("Querying Maui with %s" % config.diagnose_p_command)
    try:
        diagnose = shlex.split(config.diagnose_p_command)
        sp = subprocess.Popen(diagnose, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (query_out, query_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(diagnose, " "))
        return False, []

    if returncode != 0:
        log.error("Got non-zero return code '%s' from '%s'. stderr was: %s" %
                          (returncode, string.join(diagnose, " "), query_err))
        return False, [] 
    return True, _get_job_priorities(query_out)

def check_node(node_name):
    try:
        maui_check_node = shlex.split(config.check_node_command.format(node_name))
        sp = subprocess.Popen(maui_check_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
        state = "unknown"
        if returncode != 0:
            log.error("checknode returns error, probably the node does not exist: cmd_out %s" % cmd_out)
            log.error("cmd_err %s" % cmd_err)
            return None
        m1=re.search("state = (.*)",cmd_out)
        if m1 is not None and len(m1.groups())>0:
            state=m1.groups()[0].strip().lower()
        else:
            log.error("can't find node's state")
            log.error("cmd_out %s" % cmd_out)
            log.error("cmd_err %s" % cmd_err)
            log.error("returncode %s" % returncode)
            log.debug("m1 %s" % m1)
        log.verbose("wn %s is in state %s"%(node_name, state))
        return state
    except:
        log.exception("Problem running %s, unexpected error" % string.join(maui_check_node, " "))
        return None
    
def add_node_to_torque(vm):
    log.debug("adding %s to torque"%vm.hostname)
    with open("/etc/hosts", "a") as hosts_file:
        hosts_file.write("%s\t%s\n"%(vm.ip,vm.hostname))
    cmd=config.add_node_command.format( vm.hostname)
    log.verbose("cmd %s"%cmd)
    try:
        add_node = shlex.split(config.add_node_command.format(vm.hostname))
        sp = subprocess.Popen(add_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error adding node %s to torque"%vm.hostname)
            log.error("cmd_out %s" % cmd_out)
            log.error("cmd_err %s" % cmd_err)
            log.error("returncode %s" % returncode)
            return False
        return True
    except:
        log.exception("Problem running %s, unexpected error" % string.join(add_node, " "))
        return False

def post_vm_provision_action(vm):
    if not config.post_vm_provision_command:
        return
    cmd=config.post_vm_provision_command.format(vm.hostname, vm.ip, vm.name)
    log.debug("post vm-provision action (%s): %s"%(vm.hostname,cmd))
    try:
        post_action = shlex.split(cmd)
        sp = subprocess.Popen(post_action, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
        if returncode != 0:
            log.error("Error running post-vm-provision script for %s"%vm.hostname)
            log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
    except:
        log.exception("Problem running %s, unexpected error" % string.join(post_action, " "))
        return 

def post_vm_destroy_action(vm):
    if not config.post_vm_destroy_command:
        return
    cmd=config.post_vm_destroy_command.format(vm.hostname, vm.ip, vm.name)
    log.debug("post vm-destroy action (%s): %s"%(vm.hostname,cmd))
    try:
        post_action = shlex.split(cmd)
        sp = subprocess.Popen(post_action, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
        if returncode != 0:
            log.error("Error running post-vm-destroy script for %s"%vm.hostname)
            log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
    except:
        log.exception("Problem running %s, unexpected error" % string.join(post_action, " "))
        return 

def post_add_node_action(vm):
    if not config.post_add_node_command:
        return
    cmd=config.post_add_node_command.format(vm.hostname, vm.ip)
    log.debug("post add-node action (%s): %s"%(vm.hostname,cmd))
    try:
        post_action = shlex.split(cmd)
        sp = subprocess.Popen(post_action, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
        if returncode != 0:
            log.error("Error running post-add-node script for %s"%vm.hostname)
            log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
    except:
        log.exception("Problem running %s, unexpected error" % string.join(post_action, " "))
        return 

def post_remove_node_action(vm):
    if not config.post_remove_node_command:
        return
    cmd=config.post_remove_node_command.format(vm.hostname, vm.ip)
    log.debug("post remove-node action (%s): %s"%(vm.hostname,cmd))
    try:
        post_action = shlex.split(cmd)
        sp = subprocess.Popen(post_action, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
        if returncode != 0:
            log.error("Error running post-remove-node script for %s"%vm.hostname)
            log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
    except:
        log.exception("Problem running %s, unexpected error" % string.join(post_action, " "))
        return 

def set_np(vm, np):
    log.debug("setting np=%s to node %s"%(np,vm.hostname))
    cmd=config.set_node_command.format(vm.hostname,"np","=",str(np))
    log.verbose("cmd %s"%cmd)
    try:
        add_node = shlex.split(config.set_node_command.format(vm.hostname,"np","=",str(np)))
        sp = subprocess.Popen(add_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error setting np to node %s"%vm.hostname)
    except:
        log.exception("Problem running %s, unexpected error" % string.join(add_node, " "))
        return 

def set_node_property(vm, node_property):
    log.debug("setting %s to node %s"%(node_property,vm.hostname))
    cmd=config.set_node_command.format(vm.hostname,"properties","=",node_property)
    log.verbose("cmd %s"%cmd)
    try:
        add_node = shlex.split(config.set_node_command.format(vm.hostname,"properties","=",node_property))
        sp = subprocess.Popen(add_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error setting property to node %s"%vm.hostname)
    except:
        log.exception("Problem running %s, unexpected error" % string.join(add_node, " "))
        return 

def add_node_property(vm, node_property):
    log.debug("adding %s to node %s"%(node_property,vm.hostname))
    cmd=config.set_node_command.format(vm.hostname,"properties","+=",node_property)
    log.verbose("cmd %s"%cmd)
    try:
        add_node = shlex.split(config.set_node_command.format(vm.hostname,"properties","+=",node_property))
        sp = subprocess.Popen(add_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error adding property to node %s"%vm.hostname)
    except:
        log.exception("Problem running %s, unexpected error" % string.join(add_node, " "))
        return 

def set_node_online(vm):
    log.debug("setting node %s online"%(vm.hostname))
    try:
        add_node = shlex.split(config.set_node_command.format(vm.hostname,"state","=","free"))
        sp = subprocess.Popen(add_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error setting node %s online"%vm.hostname)
            return
        #log.verbose("Restarting /etc/init.d/torque-scheduler")
        #restart_scheduler = shlex.split("/etc/init.d/torque-scheduler restart")
        #sp = subprocess.Popen(restart_scheduler, shell=False,
        #           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #(cmd_out, cmd_err) = sp.communicate(input=None)
        #returncode = sp.returncode
        #if returncode != 0:
        #    log.error("Error restarting torque-scheduler")
        #    return
    except:
        log.exception("Problem running %s, unexpected error" % string.join(add_node, " "))
        return

def hold_node_in_torque(vm):
    try:
        hold_node = shlex.split(config.pbsnodes_command.format("-o", vm.hostname))
        sp = subprocess.Popen(hold_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(hold_node, " "))
        return 

def release_node_in_torque(vm):
    try:
        release_node = shlex.split(config.pbsnodes_command.format("-c", vm.hostname))
        sp = subprocess.Popen(release_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(release_node, " "))
        return 

def remove_node_from_torque(vm):
    try:
        remove_node = shlex.split(config.remove_node_command.format(vm.hostname))
        sp = subprocess.Popen(remove_node, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running %s, unexpected error" % string.join(remove_node, " "))
        return 

def remove_node_from_hosts_file(vm):
    try:
        sed_command = shlex.split("sed -i '/{0}/d' /etc/hosts".format(vm.hostname))
        sp = subprocess.Popen(sed_command, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running (%s) command to delete the host %s from the /etc/hosts file"%(string.join(sed_command, " "),vm.hostname))
        return

def remove_node_from_known_hosts_file(vm):
    try:
        sed_command = shlex.split("ssh-keygen -R {0}".format(vm.hostname))
        sp = subprocess.Popen(sed_command, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
    except:
        log.exception("Problem running (%s) command to delete the host %s from the known_hosts file"%(string.join(sed_command, " "),vm.hostname))
        return

def set_res_for_node(vm, res_type, account_string):
    log.debug("setting reservation (type=%s) for node %s"%(res_type, vm.hostname))
    res_opt={"account":"-a","queue":"-q"}.get(res_type)
    if res_opt is None:
        log.error("res_type %s is not supported"%res_type)
        return
    log.debug("cmd %s"%config.setres_command.format(res_opt,account_string,vm.hostname))
    try:
        set_res = shlex.split(config.setres_command.format(res_opt,account_string,vm.hostname))
        sp = subprocess.Popen(set_res, shell=False,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (cmd_out, cmd_err) = sp.communicate(input=None)
        returncode = sp.returncode
#           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
        if returncode != 0:
            log.error("Error reservation for node %s"%vm.hostname)
            log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
    except:
        log.exception("Problem running %s, unexpected error" % string.join(set_res, " "))
        return

def release_res_for_node(vm):
    cloud_res=config.cloud_resources[vm.cloud_resource_name]
    if cloud_res is not None and cloud_res.account_string is not None:
        log.debug("releasing reservation for node %s"%(vm.hostname))
        release_node = config.releaseres_command.format(vm.hostname)
        log.debug("cmd %s"%release_node)
        try:
            sp = subprocess.Popen(release_node, shell=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (cmd_out, cmd_err) = sp.communicate(input=None)
            returncode = sp.returncode
    #           log.verbose("%s: %s %s"%(string.join(add_node, " ")%cmd_out%cmd_err))
            if returncode != 0:
                log.error("Error releasing reservation for node %s"%vm.hostname)
                log.debug("cmd_out %s cmd_err %s"%(cmd_out, cmd_err))
        except:
            log.exception("Problem running %s, unexpected error" % release_node)
            return

def hostname_lookup(ip):
    if hasattr(socket, 'setdefaulttimeout'):
        # Set the default timeout on sockets to 10 seconds
        socket.setdefaulttimeout(10)
    return socket.gethostbyaddr(ip)[0]

def dump_nodes_to_persistent_file(existing_instances):
    d = os.path.dirname(config.persistent_file_location)
    if not os.path.exists(d):
        os.makedirs(d)
    content=[]
    for vm in existing_instances:
        content.append(vm.hostname+' np='+str(vm.vcpu_number) +" "+config.node_property+ os.linesep)
    with open(config.persistent_file_location, 'w') as the_file:
        the_file.write("".join(content))
    
def read_nodes_from_persistent_file():
    nodes=[]
    if os.path.exists(config.persistent_file_location) and os.path.isfile(config.persistent_file_location):
        with open(config.persistent_file_location) as the_file:
            content = the_file.readlines()
        for line in content:
            nodes.append(line.split(" ")[0].strip())
    return nodes

def _pbsnodes_to_node_list(pbsnodes_output):
    try:
        nodes = []
        root = ET.fromstring(pbsnodes_output)

        for raw_node in root.findall('Node'):
            node = {}
            for child in raw_node:
                if child.text is None:
                    parent_name=child.tag
                    for grand_child in child:
                        node[parent_name+'.'+grand_child.tag]=grand_child.text
                else:
                    node[child.tag]=child.text
            #if not config.node_property or ('properties' in node and node['properties'].find(config.node_property)>-1):
            nodes.append(node)
        if len(nodes)>0:
            log.verbose("nodes %d" % len(nodes))
        return nodes
    except:
        log.exception("can't parse pbsnodes output: %s"%pbsnodes_output)
        return []

def _qstat_to_job_list(qstat_output):
    """
    _qstat_to_job_list - Converts the output of qstat to a list of Job objects

            returns [] if there are no jobs
    """
    try:
        idle_jobs = []
        running_jobs = []
        num_of_jobs = 0
        total_number_of_idle_jobs = 0

        root = ET.fromstring(qstat_output)

        for raw_job in root.findall('Job'):
            job = {}
            for child in raw_job:
                if child.text is None:
                    parent_name=child.tag
                    for grand_child in child:
                        job[parent_name+'.'+grand_child.tag]=grand_child.text
                else:
                    job[child.tag]=child.text
            if job['job_state']=="Q" and (len(config.torque_queue_to_monitor)==0 or job['queue'] in config.torque_queue_to_monitor):
                job['Priority']=-1
                total_number_of_idle_jobs+=1
                if config.max_number_of_jobs < 1 or (config.max_number_of_jobs > 0 and num_of_jobs<config.max_number_of_jobs):
                    idle_jobs.append(job)
                    num_of_jobs+=1
            elif job['job_state']=="R":
                running_jobs.append(job)

        idle_jobs.sort(key=lambda job: int(job["Job_Id"].split(".")[0].split("[")[0]), reverse=False)
        if len(idle_jobs)>0:
            log.verbose("idle_jobs %d" % len(idle_jobs))
            
        return total_number_of_idle_jobs, idle_jobs, running_jobs
    except:
        log.exception("cannot parse qstat output: %s" % qstat_output)
        return 0, [], []

def _get_job_priorities(diagnose_output):
    job_priorities=[]
    if not diagnose_output:
        return job_priorities
    root = ET.fromstring(diagnose_output)
    for job in root:
        job_id = int(job.find('Job_Id').text.split(".")[0])
        #log.verbose("Job_Id %s"%job_id)
        priority=int(job.find('Priority').text)
        #log.verbose("priority %s"%priority)
        job_priorities.append({"Job_Id":job_id, "priority":int(priority)})
    job_priorities.sort(key=lambda job_priority: job_priority["Job_Id"], reverse=False)
    return job_priorities
