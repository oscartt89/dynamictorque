# redis-collectd-plugin - redis_info.py
#
# Copyright (C) 2014 eResearch SA
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 27/10/2014.
#
# About this plugin:
#   This plugin uses collectd's Python plugin to record dynamic torque information.
#
# collectd:
#   http://collectd.org
# Dynamic Torque:
#   https://github.com/shundezhang/dynamictorque
# collectd-python:
#   http://collectd.org/documentation/manpages/collectd-python.5.shtml

import collectd
import xmlrpclib
import socket
import sys

# Verbose logging on/off. Override in config by specifying 'Verbose'.
VERBOSE_LOGGING = False
DT_HOSTNAME = "localhost"
DT_PORT = 8113

def configure_callback(conf):
    """Receive configuration block"""
    global DT_HOSTNAME, DT_PORT, VERBOSE_LOGGING
    for node in conf.children:
        if node.key == 'Host':
            DT_PORT = node.values[0]
        elif node.key == 'Port':
            DT_PORT = int(node.values[0])
        elif node.key == 'Verbose':
            VERBOSE_LOGGING = bool(node.values[0])
        else:
            collectd.warning('dt_info plugin: Unknown config key: %s.'
                             % node.key)
    log_verbose('Configured with host=%s, port=%s' % (DT_HOSTNAME, DT_PORT))

def fetch_info():
    data={}
    try:
        s = xmlrpclib.ServerProxy("http://%s:%s" %
                                  (DT_HOSTNAME, DT_PORT))
        info = s.info()
        data["total_pbs_cores"]= sum(int(vm['np']) for vm in info["worker_nodes"])
        data["idle_jobs_num"]= info["total_number_of_idle_jobs"]
        data["running_cores"]= sum(len(job['exec_host'].split('+')) for job in info["running_jobs"] if 'exec_host' in job)
        data["active_cores"]= sum(vm['vcpu_number'] for vm in info["existing_instances"])
        data["active_dynamic_cores"]= sum(vm['vcpu_number'] for vm in info["existing_instances"] if vm['dynamic']==True)
        data["active_static_cores"]= sum(vm['vcpu_number'] for vm in info["existing_instances"] if vm['dynamic']==False)
        data["deleting_cores"]= sum(vm['vcpu_number'] for vm in info["deleting_instances"])
        data["starting_cores"]= sum(vm['vcpu_number'] for vm in info["starting_instances"])
        data["total_cloud_cores"]= (sum(vm['vcpu_number'] for vm in info["existing_instances"])+sum(vm['vcpu_number'] for vm in info["deleting_instances"])+sum(vm['vcpu_number'] for vm in info["starting_instances"]))
        data["total_cloud_vms"]= (len(info["existing_instances"])+len(info["deleting_instances"])+len(info["starting_instances"]))
        zone_stat={}
        for vm in info["existing_instances"]:
            if vm["availability_zone"] in zone_stat.keys():
                zone_stat[vm["availability_zone"]]+=int(vm['vcpu_number'])
            else:
                zone_stat[vm["availability_zone"]]=int(vm['vcpu_number'])
        data["zone_stat"] = zone_stat
        tenant_stat={}
        for vm in info["existing_instances"]:
            if vm["cloud_resource_name"] in tenant_stat.keys():
                tenant_stat[vm["cloud_resource_name"]]+=int(vm['vcpu_number'])
            else:
                tenant_stat[vm["cloud_resource_name"]]=int(vm['vcpu_number'])
        data["tenant_stat"] = tenant_stat

    except socket.error:
        collectd.error("couldn't connect to dynamic torque at %s on port %s."\
               % (DT_HOSTNAME, DT_PORT))
        return None
    except:
        collectd.error("Unexpected error: ", sys.exc_info()[0], sys.exc_info()[1])
        return None
    return data

def dispatch_value(info, key, type, plugin_instance="dynamic_torque"):
    """Read a key from info response data and dispatch a value"""
    if key not in info:
        collectd.warning('dt_info plugin: Info key not found: %s' % key)
        return

    value = int(info[key])
    log_verbose('Sending value (plugin_instance=%s): %s=%s' % (plugin_instance, key, value))

    val = collectd.Values(plugin='dynamic_torque')
    val.type = type
    val.type_instance = key
    val.plugin_instance=plugin_instance
    val.values = [value]
    val.dispatch()


def read_callback():
    log_verbose('Read callback called')
    info = fetch_info()

    if not info:
        collectd.error('dt_plugin: No info received')
        return

    # send high-level values
    dispatch_value(info, 'total_pbs_cores','gauge')
    dispatch_value(info, 'idle_jobs_num', 'gauge')
    dispatch_value(info, 'running_cores', 'gauge')
    dispatch_value(info, 'active_cores', 'gauge')
    dispatch_value(info, 'active_dynamic_cores', 'gauge')
    dispatch_value(info, 'active_static_cores', 'gauge')
    dispatch_value(info, 'deleting_cores', 'gauge')
    dispatch_value(info, 'starting_cores', 'gauge')
    dispatch_value(info, 'total_cloud_cores', 'gauge')
    dispatch_value(info, 'total_cloud_vms', 'gauge')

    # database and vm stats
    for key in info['zone_stat']:
        dispatch_value(info['zone_stat'], key, 'gauge', 'zone')
    for key in info['tenant_stat']:
        dispatch_value(info['tenant_stat'], key, 'gauge', 'tenant')

def log_verbose(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('dt plugin [verbose]: %s' % msg)

# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(read_callback, 60)