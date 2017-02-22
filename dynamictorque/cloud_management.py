#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque cluster management class
## This is the class to keep cloud states, including state of instances
##

##
## IMPORTS
##
from __future__ import with_statement
import os
import logging
import dynamictorque.config as config
import dynamictorque.local_commands as commands
import threading
import time
import traceback

log = logging.getLogger("dynamictorque")

class CloudPoller(threading.Thread):
    def __init__(self, job_pool):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.job_pool = job_pool
        self.quit = False
        self.polling_interval = config.cloud_poller_interval

    def stop(self):
        log.debug("Waiting for cloud polling loop to end")
        self.quit = True

    def run(self):
        try:
            sleep_tics=0
            log.info("Starting cloud polling at interval %i ..." % self.polling_interval)
            while not self.quit:
                if sleep_tics==0:
                    if self.job_pool.provisioning==True:
                        log.verbose("Polling provisioning state")
                        self.job_pool.update_provision_status()
                    log.verbose("Polling cleanup state")
                    self.job_pool.check_cleanup()
                time.sleep(1)
                sleep_tics += 1
                if sleep_tics>=self.polling_interval:
                    sleep_tics=0

            log.info("Exiting cloud polling thread")
        except:
            log.error(traceback.format_exc())

class CloudManager(object):
    def __init__(self):
        self.cloud_backend=self._setup_cloud()
        self._init_cloud_resources()
    def _setup_cloud(self):
        """ create the cloud object, currently only Open Stack is supported """
        if config.cloud_type == "OpenStack":
            import openstack_cloud
            return openstack_cloud.OpenStackCloud(config)
        return None
    def _init_cloud_resources(self):
        log.info("getting flavors from the cloud")
        flavors=self.cloud_backend.get_flavor_list()
        flavors.sort(key=lambda flavor: flavor.vcpus)
        log.debug("flavors sorted %s" % flavors)
        for resource in config.cloud_resources:
            flavor_names=config.cloud_resources[resource].worker_node_flavors
            for flavor in flavors:
                if flavor.name in flavor_names:
                    config.cloud_resources[resource].flavor_objects.append(flavor)

    def load_all_existing_worker_nodes(self):
        existing_instaces=[]
        for resource in config.cloud_resources:
            existing_instaces.extend(self.cloud_backend.vm_list(resource))
        return existing_instaces
