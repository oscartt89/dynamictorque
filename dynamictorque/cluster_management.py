#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque cluster management class
## This is the class to keep cluster states, including state of jobs, worker nodes, pbs/maui status
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
from fractions import gcd

log = logging.getLogger("dynamictorque")

class JobPoller(threading.Thread):
    """
    JobPoller - Polls the Torque queue for job status, and new jobs
    """

    def __init__(self, job_pool):
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.job_pool = job_pool
        self.quit = False
        self.polling_interval = config.job_poller_interval

    def stop(self):
        log.debug("Waiting for job polling loop to end")
        self.quit = True

    def run(self):
        try:
            sleep_tics=0
            log.info("Starting job polling at interval %i ..." % self.polling_interval)
            while not self.quit:
                if sleep_tics==0:
                    log.verbose("Polling job state")
                    self.job_pool.collect_cluster_information()
                time.sleep(1)
                sleep_tics += 1
                if sleep_tics>=self.polling_interval:
                    sleep_tics=0

            log.info("Dumping current nodes to persistent file")
            commands.dump_nodes_to_persistent_file(self.job_pool.existing_instances)
            log.info("Exiting job polling thread")
        except:
            log.error(traceback.format_exc())

