#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque admin script
## for active mode
## This script provides a bunch of admin functions
##

import xmlrpclib
import sys
import socket
from optparse import OptionParser
import logging
import platform
import string
import time
from datetime import datetime
import os

#import vmpool.utilities as utilities 
#log = utilities.get_logger()

import dynamictorque.config as config

def main(argv=None):

    # Parse command line options
    parser = OptionParser()
    parser.add_option("-n", "--hostname", dest="hostname",
                      metavar="HOSTNAME",
                      help="The Dynamic Torque info server")
    parser.add_option("-p", "--port", dest="port", metavar="PORT",
                      help="Pick a custom port to connect to info server")
    parser.add_option("-i", "--info", dest="info", action="store_true", 
                      default=False, help="Show usage info.")
    parser.add_option("-m", "--method", dest="method", action="store_true", 
                      default=False, help="Show VM server method help.")
    parser.add_option("-c", "--continuous", dest="continuous", metavar="SECONDS", 
                      default=False, help="Show usage info continuously every X seconds.")
    parser.add_option("-k", "--kill", dest="kill", metavar="VM_HOSTNAME", 
                      default=False, help="Kill a worker node.")
    parser.add_option("-d", "--detail", dest="detail", metavar="VM_HOSTNAME", 
                      default=False, help="Show details of a worker node.")
    parser.add_option("-f", "--forceoff", dest="forceoff", action="store_true", 
                      default=False, help="Shut down all current worker nodes (if they have jobs running, mark them as offline and wait for jobs to finish, then shut them down).")
    parser.add_option("-l", "--list", dest="list", action="store_true", 
                      default=False, help="List all dynamic worker nodes for Torque nodes file.")
    parser.add_option("-w", "--listnew", dest="listnew", action="store_true", 
                      default=False, help="List all worker nodes including new (starting) nodes.")
    parser.add_option("-t", "--tenant", dest="tenant", metavar="TENANT_ACCOUNT_STRING", 
                      default=False, help="List worker nodes of this tenant only.")
    parser.add_option("-g", "--ganglia", dest="ganglia", action="store_true", 
                      default=False, help="Get ganglia metric values.")
    parser.add_option("-s", "--sleep", dest="sleep", action="store_true", 
                      default=False, help="Toggle sleep mode (In sleep mode dynamic torque will not query Torque to start or stop worker nodes.)")

    (cli_options, args) = parser.parse_args()

    # Initialize config
#    if cli_options.config_file:
#        config.setup(cli_options.config_file)
#    else:
#     config.setup()


    # Get port to connect to info server.
    #   Precedence: -p argument, then from config module
    if cli_options.port:
        server_port = cli_options.port
    else:
        server_port = config.info_server_port

    if cli_options.hostname:
        server_hostname = cli_options.hostname
    else:
        server_hostname = platform.node()

    # Connect to info server
    try:
        s = xmlrpclib.ServerProxy("http://%s:%s" %
                                  (server_hostname, server_port))
        if cli_options.info:
            if cli_options.continuous:
                while True:
                    try:
                        os.system("clear")
                        print_info(s)
                        time.sleep(int(cli_options.continuous))
                    except KeyboardInterrupt:
                        print "Bye"
                        return 0
            else:
                print_info(s)
        elif cli_options.kill:
            print("killing %s"%cli_options.kill)
            rt, msg = s.kill(cli_options.kill)
            if rt>0:
                print('ERROR: %s' % msg)
                return 1
            else:
                print "Done"
        elif cli_options.detail:
            vm, wn = s.get_detail(cli_options.detail)
            template_r = "{0:25}{1}"
            print "VM information:"
            for item in vm:
                print template_r.format(item.upper(), vm[item])
            print "WN information:"
            for item in wn:
                print template_r.format(item.upper(), wn[item])
        elif cli_options.method:
            methods=s.system.listMethods()
            print methods
            for method in methods:
                print s.system.methodHelp(method)
                print s.system.methodSignature(method)
        elif cli_options.list:
            info = s.info()
            worker_nodes=info['worker_nodes']
            for vm in info["existing_instances"]:
                worker_node=next((wn for wn in worker_nodes if wn['name'] == vm['hostname']), None)
                wn_property = ""
                if worker_node is not None:
                    wn_property=worker_node['properties']
                print ("%s np=%d %s"%(vm['hostname'], vm['vcpu_number'], wn_property))
        elif cli_options.listnew:
            info = s.info()
            for vm in info["existing_instances"]:
                if cli_options.tenant is not False and vm['cloud_resource_name'] != cli_options.tenant:
                    continue
                if vm['ip'] is not None:
                    print vm['ip']
            for vm in info["starting_instances"]:
                if cli_options.tenant is not False and vm['cloud_resource_name'] != cli_options.tenant:
                    continue
                if vm['ip'] is not None:
                    print vm['ip']
        elif cli_options.forceoff:
            print("Trying to shut down all worker nodes")
            s.forceoff() 
            print "Done"
        elif cli_options.ganglia:
            info = s.info()
            print "total_pbs_cores %d" % sum(int(vm['np']) for vm in info["worker_nodes"])
            print "idle_jobs_num %d" % info["total_number_of_idle_jobs"]
            print "running_cores %d" % sum(len(job['exec_host'].split('+')) for job in info["running_jobs"] if 'exec_host' in job)
            print "active_cores %d" % sum(vm['vcpu_number'] for vm in info["existing_instances"])
            print "active_dynamic_cores %d" % sum(vm['vcpu_number'] for vm in info["existing_instances"] if vm['dynamic']==True)
            print "active_static_cores %d" % sum(vm['vcpu_number'] for vm in info["existing_instances"] if vm['dynamic']==False)
            print "deleting_cores %d" % sum(vm['vcpu_number'] for vm in info["deleting_instances"])
            print "starting_cores %d" % sum(vm['vcpu_number'] for vm in info["starting_instances"])
            print "total_cloud_cores %d" % (sum(vm['vcpu_number'] for vm in info["existing_instances"])+sum(vm['vcpu_number'] for vm in info["deleting_instances"])+sum(vm['vcpu_number'] for vm in info["starting_instances"]))
            print "total_cloud_vms %d" % (len(info["existing_instances"])+len(info["deleting_instances"])+len(info["starting_instances"]))
            zone_stat={}
            for vm in info["existing_instances"]:
                if vm["availability_zone"] in zone_stat.keys():
                    zone_stat[vm["availability_zone"]]+=int(vm['vcpu_number'])
                else:
                    zone_stat[vm["availability_zone"]]=int(vm['vcpu_number'])
            print "zone_stat %s" % ",".join(key+":"+str(val) for key,val in zone_stat.items())
        elif cli_options.sleep:
            s.toggle_sleep_mode()
            print 'Done'
        else:
            print "Run info.py -h for help."
        return 0

    except socket.error:
        print "%s: couldn't connect to vm pool at %s on port %s."\
               % (sys.argv[0], server_hostname, server_port)
        print "Is the vm pool running on port %s?" % server_port
    except:
        print "Unexpected error: ", sys.exc_info()[0], sys.exc_info()[1]
        print "Is the vm pool running on port %s?" % server_port
    return 1

def print_info(s):
    info = s.info()
    print "In sleep mode: %r; PBS OK: %r; MAUI OK: %r; Provisioning: %r; Total number of idle jobs: %d; waiting list: %s" % (info['sleep_mode'], info['pbs_server_up'], info['maui_server_up'], info['provisioning'], info['total_number_of_idle_jobs'], info['provision_waiting_list'])
    template_r = "{0:10}{1:30}{2:16}{3:46}{4:7}{5:13}{6:15}{7:}"
    internal_worker_nodes=[]
    for res in info["cloud_resources"]:
        print "****** Resource Information of Tenant %s ******" % res
        print "Image UUID: %s Account String: %s Flavor: %s Number Of Available Nodes: %i" % (info["cloud_resources"][res]["image_uuid"],info["cloud_resources"][res]["account_string"],info["cloud_resources"][res]["worker_node_flavor"],info["cloud_resources"][res]["available_number_of_nodes"])
        print template_r.format("Type", "Instance name", "Host IP", "Hostname", "VCPUS", "State(Cloud)", "State(Torque)", "Running Jobs")
        print '='*200
        worker_nodes=info['worker_nodes']
        for vm in info["existing_instances"]:
            if vm["cloud_resource_name"]!=res:
                continue
            worker_node=next((wn for wn in worker_nodes if wn['name'] == vm['hostname']), None)
            wn_state = "---"
            running_jobs = "---"
            node_type = "Dynamic"
            if not vm['dynamic']:
                node_type = "Static"
            if worker_node is not None:
                internal_worker_nodes.append(worker_node)
                wn_state=worker_node['state']
                if str(vm['state_time']).isdigit() and ((worker_node['state']=="free" and "jobs" not in worker_node) or worker_node['state']=="down") and vm['dynamic']:
                    wn_state = worker_node['state']+"("+str(vm['state_time'])+"s)"
                job_numbers=[]
                if "jobs" in worker_node:
                    jobs=worker_node['jobs'].split(",")
                    for j in jobs:
                        job_numbers.append((j.strip().split(".")[0]).split("/")[1])
                    if len(job_numbers)>0:
                        running_jobs=string.join(job_numbers, " ")
            print template_r.format(node_type, vm['name'], vm['ip'], vm['hostname'], str(vm['vcpu_number']).ljust(5), vm['state'], wn_state, running_jobs)
        for vm in info["starting_instances"]:
            if vm["cloud_resource_name"]!=res:
                continue
            worker_node=next((wn for wn in worker_nodes if wn['name'] == vm['hostname']), None)
            wn_state = "---"
            if worker_node is not None:
                internal_worker_nodes.append(worker_node)
                wn_state=worker_node['state']
            print template_r.format("Starting", vm['name'], vm['ip'], vm['hostname'], str(vm['vcpu_number']).ljust(5), vm['state'], wn_state, "---")
        for vm in info["deleting_instances"]:
            if vm["cloud_resource_name"]!=res:
                continue
            worker_node=next((wn for wn in worker_nodes if wn['name'] == vm['hostname']), None)
            wn_state = "---"
            running_jobs = "---"
            if worker_node is not None:
                if 'state_time' in vm:
                    wn_state = worker_node['state']+"("+str(vm['state_time'])+"s)"
                job_numbers=[]
                if "jobs" in worker_node:
                    jobs=worker_node['jobs'].split(",")
                    for j in jobs:
                        job_numbers.append((j.strip().split(".")[0]).split("/")[1])
                    if len(job_numbers)>0:
                        running_jobs=string.join(job_numbers, " ")
                internal_worker_nodes.append(worker_node)
                wn_state=worker_node['state']
            print template_r.format("Deleting", vm['name'], vm['ip'], vm['hostname'], str(vm['vcpu_number']).ljust(5), vm['state'], wn_state, running_jobs)
        print
    for wn in worker_nodes:
        if wn not in internal_worker_nodes:
            running_jobs = "---"
            if "jobs" in wn:
                job_numbers=[]
                jobs=wn['jobs'].split(",")
                for j in jobs:
                    job_numbers.append((j.strip().split(".")[0]).split("/")[1])
                if len(job_numbers)>0:
                    running_jobs=string.join(job_numbers, " ")
            print template_r.format("Physical", "---", "---", wn['name'], str(wn['np']).ljust(5), "---", wn['state'], running_jobs)
    print
    print "****** Idle Job Information ******"
    template_j = "{0:50}{1:30}{2:15}{3:10}{4:9}{5:7}{6:12}"
    print template_j.format("Id", "Name", "User", "queue", "priority", "ncpus", "walltime")
    print '='*200
    for job in info["idle_jobs"]:
        if 'Resource_List.ncpus' in job:
            ncpus=job['Resource_List.ncpus']
        elif 'Resource_List.nodes' in job:
            ncpus=job['Resource_List.nodes']
        else:
            ncpus="--"
        if 'Resource_List.walltime' in job:
            walltime=job['Resource_List.walltime']
        else:
            walltime="--"
        print template_j.format(job['Job_Id'], job['Job_Name'], job['euser'], job['queue'], str(job['job_priority']).ljust(7), str(ncpus).ljust(5), walltime)
    print
    print '-'*100
    print "Queried at %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print
    print

if __name__ == "__main__":
    sys.exit(main())