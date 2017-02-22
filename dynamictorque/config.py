#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque config class

import os
import sys
from urlparse import urlparse
from cloud_tools import StaticVMs
from cloud_tools import CloudResource
from utilities import get_or_none
import ConfigParser
import logging
from random import choice

#import utilities

info_server_port = 8113

max_inaccessible_time = 900
max_idle_time = 600
max_down_time = 480
max_delete_retry_time = 600

# cloud config
cloud_type="OpenStack"
cloud_username=""
cloud_password=""
cloud_tenant_name=""
cloud_auth_url=""

cloud_vm_prefix = "pbsdynwn-"
cloud_image_uuid = "bf84de68-247e-443f-80ee-8db7edd38334"
cloud_vm_flavor = "0"
cloud_key_name = "nectarkey"
cloud_security_groups=[]
cloud_private_key_location = ""
cloud_availability_zone = "noblepark"
cloud_vm_init_file = ""
cloud_vm_userdata_file = ""
cloud_vm_init_finish_file = "/var/run/cloud-init/done"
cloud_shell_user = "root"

persistent_file_location = "/var/lib/dynamictorque/nodes"
ssh_connection_timeout_value = 10
vm_creation_batch_number = 5
job_poller_interval = 10
cloud_poller_interval = 20
qstat_command = "/usr/bin/qstat -x -t"
# -x get all nodes, -o hold a node, -c clear OFFLINE from a node
pbsnodes_command = "/usr/bin/pbsnodes {0} {1}"
add_node_command = "/usr/bin/qmgr -c \"create node {0}\""
check_node_command = "/usr/bin/checknode {0}"
node_property = ""
remove_node_command = "/usr/bin/qmgr -c \"delete node {0}\""
set_node_command = "/usr/bin/qmgr -c \"set node {0} {1} {2} {3}\""
#hold_node_command = "/usr/bin/pbsnodes -o {0}"
diagnose_p_command = "/usr/bin/diagnose -p"
post_add_node_command = ""
post_remove_node_command = ""
post_vm_provision_command = ""
post_vm_destroy_command = ""
setres_command = "/usr/bin/setres -a {0} {1}"
releaseres_command = "/usr/bin/releaseres `/usr/bin/showres -n | grep User | grep {0} | awk '{{print $3}}' `"
torque_queue_to_monitor = []
worker_node_flavor = "m1.small"
static_worker_nodes = ""
number_of_dynamic_worker_nodes = 2
static_vm_list = None
location_properties={}
default_location=0
max_number_of_jobs=-1
cloud_resources={}

log_level = "INFO"
log_location = None
log_stdout = False
log_max_size = None
log_format = "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"

log = None

def setup(path=None):
    
    global log
    log = logging.getLogger("dynamictorque")

    global pool_min_num
    global pool_max_num
    global max_idle_time
    global max_inaccessible_time
    global max_down_time
    global post_add_node_command
    global post_remove_node_command
    global post_vm_provision_command
    global post_vm_destroy_command
    
    global cloud_type
    global cloud_username
    global cloud_password
    global cloud_tenant_name
    global cloud_auth_url
    global cloud_key_name
    global cloud_security_groups
    global cloud_private_key_location
    global cloud_availability_zone
    global cloud_vm_init_file
    global cloud_image_uuid
    global cloud_vm_prefix
    global cloud_vm_userdata_file
    global cloud_vm_init_finish_file
    global cloud_shell_user
    
    global job_poller_interval
    global cloud_poller_interval
    global qstat_command
    global pbsnodes_command
    global add_node_command
    global check_node_command
    global remove_node_command
    global set_node_command
    #global hold_node_command
    global diagnose_p_command
    global setres_command
    global releaseres_command
    
    global torque_queue_to_monitor
    global worker_node_flavors
    global node_property
    global persistent_file_location
    global static_worker_nodes
    global number_of_dynamic_worker_nodes
    global static_vm_list
    global location_properties
    global default_location
    global max_number_of_jobs
    
    global cloud_resources
    
    global log_level
    global log_location
    global log_stdout
    global log_max_size
    global log_format
    
    homedir = os.path.expanduser('~')

    # Find config file
    if not path:
        if os.path.exists(homedir + "/.dynamictorque/dynamic_torque.conf"):
            path = homedir + "/.dynamictorque/dynamic_torque.conf"
        elif os.path.exists("/etc/dynamictorque/dynamic_torque.conf"):
            path = "/etc/dynamictorque/dynamic_torque.conf"
        else:
            print >> sys.stderr, "Configuration file problem: There doesn't " \
                  "seem to be a configuration file. " \
                  "You can specify one with the --config-file parameter, " \
                  "or put one in ~/.dynamictorque/dynamic_torque.conf or "\
                  "/etc/dynamictorque/dynamic_torque.conf"
            sys.exit(1)

    # Read config file
    config_file = ConfigParser.ConfigParser()
    try:
        config_file.read(path)
    except IOError:
        print >> sys.stderr, "Configuration file problem: There was a " \
              "problem reading %s. Check that it is readable," \
              "and that it exists. " % path
        raise
    except ConfigParser.ParsingError:
        print >> sys.stderr, "Configuration file problem: Couldn't " \
              "parse your file. Check for spaces before or after variables."
        raise
    except:
        print "Configuration file problem: There is something wrong with " \
              "your config file."
        raise

    if config_file.has_option("global", "pool_min_num"):
        pool_min_num = config_file.getint("global",
                                                "pool_min_num")
    if config_file.has_option("global", "pool_max_num"):
        pool_max_num = config_file.getint("global",
                                                "pool_max_num")
    if config_file.has_option("global", "max_idle_time"):
        max_idle_time = config_file.getint("global",
                                                "max_idle_time")
    if config_file.has_option("global", "max_down_time"):
        max_down_time = config_file.getint("global",
                                                "max_down_time")
    if config_file.has_option("global", "max_inaccessible_time"):
        max_inaccessible_time = config_file.getint("global",
                                                "max_inaccessible_time")
    if config_file.has_option("global", "job_poller_interval"):
        job_poller_interval = config_file.getint("global",
                                                "job_poller_interval")
    if config_file.has_option("global", "cloud_poller_interval"):
        cloud_poller_interval = config_file.getint("global",
                                                "cloud_poller_interval")
    if config_file.has_option("global", "persistent_file_location"):
        persistent_file_location = config_file.get("global",
                                                "persistent_file_location")
    if config_file.has_option("global", "post_add_node_command"):
        post_add_node_command = config_file.get("global",
                                                "post_add_node_command")
    if config_file.has_option("global", "post_remove_node_command"):
        post_remove_node_command = config_file.get("global",
                                                "post_remove_node_command")
    if config_file.has_option("global", "post_vm_provision_command"):
        post_vm_provision_command = config_file.get("global",
                                                "post_vm_provision_command")
    if config_file.has_option("global", "post_vm_destroy_command"):
        post_vm_destroy_command = config_file.get("global",
                                                "post_vm_destroy_command")
    if config_file.has_option("global", "qstat_command"):
        qstat_command = config_file.get("global",
                                                "qstat_command")
    if config_file.has_option("global", "pbsnodes_command"):
        pbsnodes_command = config_file.get("global",
                                                "pbsnodes_command")
    if config_file.has_option("global", "add_node_command"):
        add_node_command = config_file.get("global",
                                                "add_node_command")
    if config_file.has_option("global", "check_node_command"):
        check_node_command = config_file.get("global",
                                                "check_node_command")
    if config_file.has_option("global", "remove_node_command"):
        remove_node_command = config_file.get("global",
                                                "remove_node_command")
    if config_file.has_option("global", "set_node_command"):
        set_node_command = config_file.get("global",
                                                "set_node_command")
#    if config_file.has_option("global", "hold_node_command"):
#        hold_node_command = config_file.get("global",
#                                                "hold_node_command")
    if config_file.has_option("global", "diagnose_p_command"):
        diagnose_p_command = config_file.get("global",
                                                "diagnose_p_command")
    if config_file.has_option("global", "setres_command"):
        setres_command = config_file.get("global",
                                                "setres_command")
    if config_file.has_option("global", "releaseres_command"):
        releaseres_command = config_file.get("global",
                                                "releaseres_command")


    if config_file.has_option("cloud", "cloud_username"):
        cloud_username = config_file.get("cloud",
                                                "cloud_username")
    if config_file.has_option("cloud", "cloud_password"):
        cloud_password = config_file.get("cloud",
                                                "cloud_password")
    if config_file.has_option("cloud", "cloud_tenant_name"):
        cloud_tenant_name = config_file.get("cloud",
                                                "cloud_tenant_name")
    if config_file.has_option("cloud", "cloud_auth_url"):
        cloud_auth_url = config_file.get("cloud",
                                                "cloud_auth_url")
    if config_file.has_option("cloud", "cloud_key_name"):
        cloud_key_name = config_file.get("cloud",
                                                "cloud_key_name")
    if config_file.has_option("cloud", "cloud_security_groups"):
        cloud_security_groups = config_file.get("cloud",
                                                "cloud_security_groups")
        if cloud_security_groups:
            cloud_security_groups = cloud_security_groups.split(",")
    if config_file.has_option("cloud", "cloud_private_key_location"):
        cloud_private_key_location = config_file.get("cloud",
                                                "cloud_private_key_location")
    if config_file.has_option("cloud", "cloud_availability_zone"):
        cloud_availability_zone = config_file.get("cloud",
                                                "cloud_availability_zone")
    if config_file.has_option("cloud", "cloud_vm_init_file"):
        cloud_vm_init_file = config_file.get("cloud",
                                                "cloud_vm_init_file")
    if config_file.has_option("cloud", "cloud_vm_userdata_file"):
        cloud_vm_userdata_file = config_file.get("cloud",
                                                "cloud_vm_userdata_file")
    if config_file.has_option("cloud", "cloud_image_uuid"):
        cloud_image_uuid = config_file.get("cloud",
                                                "cloud_image_uuid")
    if config_file.has_option("cloud", "cloud_vm_prefix"):
        cloud_vm_prefix = config_file.get("cloud",
                                                "cloud_vm_prefix")
    if config_file.has_option("cloud", "worker_node_flavors"):
        _worker_node_flavors = config_file.get("cloud",
                                                "worker_node_flavors")
        if _worker_node_flavors:
            worker_node_flavors = _worker_node_flavors.split(",")
    if config_file.has_option("cloud", "cloud_vm_init_finish_file"):
        cloud_vm_init_finish_file = config_file.get("cloud",
                                                "cloud_vm_init_finish_file")
    if config_file.has_option("cloud", "number_of_dynamic_worker_nodes"):
        number_of_dynamic_worker_nodes = config_file.getint("cloud",
                                                "number_of_dynamic_worker_nodes")
    if config_file.has_option("cloud", "cloud_shell_user"):
        cloud_shell_user = config_file.get("cloud",
                                                "cloud_shell_user")
        
    if config_file.has_option("torque", "torque_queue_to_monitor"):
        torque_queue_to_monitor = config_file.get("torque",
                                                "torque_queue_to_monitor")
        if torque_queue_to_monitor:
            torque_queue_to_monitor = torque_queue_to_monitor.split(",")
    if config_file.has_option("torque", "node_property"):
        node_property = config_file.get("torque",
                                                "node_property")
    if config_file.has_option("torque", "node_location_property"):
        node_location_property = config_file.get("torque",
                                                "node_location_property")
        if node_location_property:
            node_location_property = node_location_property.split(",")
        for loc in node_location_property:
            strs=loc.split(":")
            if len(strs)==2:
                location_properties[strs[0]]=strs[1]
    if config_file.has_option("torque", "max_number_of_jobs"):
        max_number_of_jobs = config_file.getint("torque",
                                                "max_number_of_jobs")

    if config_file.has_option("cloud", "static_worker_nodes"):
        static_worker_nodes = config_file.get("cloud",
                                                "static_worker_nodes")
        static_vm_list=parse_static_worker_nodes(static_worker_nodes)
    else:
            static_vm_list=StaticVMs()
                
    if config_file.has_option("torque", "default_location"):
        default_location = config_file.getint("torque",
                                                "default_location")

    cloud_resources["default"]=CloudResource(cloud_username,cloud_password,cloud_tenant_name, cloud_image_uuid, cloud_vm_userdata_file, worker_node_flavors, static_worker_nodes, number_of_dynamic_worker_nodes, static_vm_list)
    
    if config_file.has_option("cloud", "cloud_resources_config"):
        cloud_resources.update(parse_cloud_resources_config_file(config_file.get("cloud", "cloud_resources_config")))

    # Default Logging options
    if config_file.has_option("logging", "log_level"):
        log_level = config_file.get("logging", "log_level")

    if config_file.has_option("logging", "log_location"):
        log_location = os.path.expanduser(config_file.get("logging", "log_location"))

    if config_file.has_option("logging", "log_stdout"):
        try:
            log_stdout = config_file.getboolean("logging", "log_stdout")
        except ValueError:
            print "Configuration file problem: log_stdout must be a" \
                  " Boolean value."

    if config_file.has_option("logging", "log_max_size"):
        try:
            log_max_size = config_file.getint("logging", "log_max_size")
        except ValueError:
            print "Configuration file problem: log_max_size must be an " \
                  "integer value in bytes."
            sys.exit(1)

    if config_file.has_option("logging", "log_format"):
        log_format = config_file.get("logging", "log_format")

def parse_static_worker_nodes(static_worker_nodes):
    static_vm_list = StaticVMs()
    default_location=None
    
    for loc in location_properties:
        if location_properties[loc]==cloud_availability_zone:
            default_location=loc
    if not default_location:
        return
    if static_worker_nodes.isdigit():
        static_vm_list.add_static_req(default_location, int(static_worker_nodes))
    else:
        reqs=static_worker_nodes.split("+")
        for req in reqs:
            strs=req.split(":")
            if not strs[0].isdigit():
                log.error("static_core_number is malformatted: %s" % static_worker_nodes)
                continue
            num_of_vm=int(strs[0])
            location=default_location
            if len(strs)>1:
                location=strs[1]
            static_vm_list.add_static_req(location, num_of_vm)
    return static_vm_list

def parse_cloud_resources_config_file(cloud_resources_config_location):
    global cloud_image_uuid
    global cloud_vm_userdata_file
    
    config_file_location = os.path.expanduser(cloud_resources_config_location)
    try:
        cloud_config = ConfigParser.ConfigParser()
        cloud_config.read(config_file_location)
    except ConfigParser.ParsingError:
        log.exception("Cloud config resources problem: Couldn't " \
              "parse your cloud resources config file. Check for spaces " \
              "before or after variables.")
        sys.exit(1)
    cloud_resources = {}
    for resource in cloud_config.sections():
        if cloud_config.has_option(resource, "cloud_username"):
            cloud_username = cloud_config.get(resource, "cloud_username")
        else:
            continue
        if cloud_config.has_option(resource, "cloud_password"):
            cloud_password = cloud_config.get(resource, "cloud_password")
        else:
            continue
        if cloud_config.has_option(resource, "cloud_tenant_name"):
            cloud_tenant_name = cloud_config.get(resource, "cloud_tenant_name")
        else:
            continue
        if cloud_config.has_option(resource, "cloud_image_uuid"):
            image_uuid = cloud_config.get(resource, "cloud_image_uuid")
        else:
            image_uuid = cloud_image_uuid
        if cloud_config.has_option(resource, "cloud_vm_userdata_file"):
            user_data_file = cloud_config.get(resource, "cloud_vm_userdata_file")
        else:
            user_data_file = cloud_vm_userdata_file
        if cloud_config.has_option(resource, "worker_node_flavor"):
            worker_node_flavor = cloud_config.get(resource, "worker_node_flavor")
        else:
            worker_node_flavor = "m1.small"
        if cloud_config.has_option(resource, "number_of_dynamic_worker_nodes"):
            number_of_dynamic_worker_nodes = cloud_config.getint(resource, "number_of_dynamic_worker_nodes")
        else:
            number_of_dynamic_worker_nodes = 1
        if cloud_config.has_option(resource, "static_worker_nodes"):
            static_worker_nodes = cloud_config.get(resource, "static_worker_nodes")
            static_vm_list=parse_static_worker_nodes(static_worker_nodes)
        else:
            static_vm_list=StaticVMs()
        if cloud_config.has_option(resource, "account_string"):
            account_string = cloud_config.get(resource, "account_string")
        has_volume=False
        if cloud_config.has_option(resource, "has_volume"):
            try:
                has_volume = cloud_config.getboolean(resource, "has_volume")
            except ValueError:
                print "Configuration file problem: has_volume must be a" \
                      " Boolean value."
        res_type="account"
        if cloud_config.has_option(resource, "reservation_type"):
            res_type = cloud_config.get(resource, "reservation_type")
        cloud_resources[resource]=CloudResource(cloud_username,cloud_password,cloud_tenant_name, image_uuid, user_data_file, worker_node_flavor, static_worker_nodes, number_of_dynamic_worker_nodes, static_vm_list, account_string, has_volume, res_type)
    return cloud_resources
            
def get_default_node_location():
    global default_location
    global location_properties
    global cloud_availability_zone
    if default_location==1:
        return choice(location_properties.keys())
    for loc in location_properties:
        if location_properties[loc]==cloud_availability_zone:
            return loc
    return None

def convert_location_property_to_availability_zone(location_property):
    global location_properties
    global default_location
    global cloud_availability_zone
    if location_properties and location_property in location_properties:
        return location_properties[location_property]
    else:
        if default_location==1:
            return choice(location_properties.keys())
        return cloud_availability_zone
