#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque main script
## This script starts dynamic torque and sets up all functionalities
##
## Using optparse for command line options (http://docs.python.org/library/optparse.html)

from __future__ import with_statement
import sys
import time
import logging
import logging.handlers
import signal
import ConfigParser
from optparse import OptionParser

import dynamictorque.__version__ as version
import dynamictorque.info_server as info_server
import dynamictorque.utilities as utilities
import dynamictorque.config as config
from dynamictorque.cloud_tools import ICloud
import dynamictorque.res_management as res_management
from dynamictorque.cluster_management import JobPoller
from dynamictorque.cloud_management import CloudPoller

log = utilities.get_logger()

def main(argv=None):
    
    version_str = "Dynamic Torque " + version.version
    
    parser = OptionParser(version=version_str)
    set_options(parser)
    
    (cli_options, args) = parser.parse_args()
    # Look for global configuration file, and initialize config
    if (cli_options.config_file):
        config.setup(path=cli_options.config_file)
    else:
        config.setup()
    
    # Set up logging
    logging._srcfile = None 
    logging.logProcesses = 0
    log.setLevel(utilities.LEVELS[config.log_level])
    log_formatter = logging.Formatter(config.log_format)
    if config.log_stdout:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        log.addHandler(stream_handler)

    if config.log_location:
        file_handler = None
        if config.log_max_size:
            file_handler = logging.handlers.RotatingFileHandler(
                                            config.log_location,
                                            maxBytes=config.log_max_size)
        else:
            try:
                file_handler = logging.handlers.WatchedFileHandler(
                                            config.log_location,)
            except AttributeError:
                # Python 2.5 doesn't support WatchedFileHandler
                file_handler = logging.handlers.RotatingFileHandler(
                                            config.log_location,)

        file_handler.setFormatter(log_formatter)
        log.addHandler(file_handler)

    if not config.log_location and not config.log_stdout:
        null_handler = utilities.NullHandler()
        log.addHandler(null_handler)
    # Log entry message (for timestamp in log)
    log.info("Dynamic Torque starting...")
    if config.log_level == 'VERBOSE':
        log.warning("WARNING - using VERBOSE logging will result is poor performance with more than a few hundred jobs in the queue")
    if config.log_level == 'DEBUG':
        log.warning("WARNING - using DEBUG logging can result in poor performance with more than a few thousand jobs in the queue")


    service_threads = []
    server_threads = []
    
    log.info("Dynamic Torque is configured with the following resources:")
    for res in config.cloud_resources:
        log.info("  %s: %s"%(res, config.cloud_resources[res]))
    log.info("locations %s" % config.location_properties)
    # Create a job pool
    res_center = res_management.ResourceCenter("Resource Center")
    # Create the Job Polling thread
    job_poller = JobPoller(res_center)
    service_threads.append(job_poller)
    # Create the Cloud Polling thread
    cloud_poller = CloudPoller(res_center)
    service_threads.append(cloud_poller)
    # Start the vm server for RPCs
    info_serv = info_server.InfoServer(res_center)
    info_serv.daemon = True
    server_threads.append(info_serv)
    
    # Set SIGTERM (kill) handler
    signal.signal(signal.SIGTERM, term_handler)

    # Set SIGUSR1 (reconfig) handler
    #reconfig_handler = make_reconfig_handler(cloud_resources)
    #signal.signal(signal.SIGUSR1, reconfig_handler)

    # Set SIGUSR2 (reload_ban) handler
    #reload_ban_handler = make_banned_job_fileload_handler(cloud_resources)
    #signal.signal(signal.SIGUSR2, reload_ban_handler)

    # Set SIGUSR2 (quick_exit) handler
    #quick_exit_handler = make_quick_exit_handler(scheduler)
    #signal.signal(signal.SIGUSR2, quick_exit_handler)

    
    # Start all the threads
    for thread in server_threads:
        thread.start()

    for thread in service_threads:
        thread.start()

    should_be_running = True
    
    # Wait for keyboard input to exit the cloud scheduler
    try:
        die = False
        while not die:
            for thread in service_threads:
                if not thread.isAlive():
                    log.error("%s thread died!" % thread.name)
                    die = True
            time.sleep(1)
    except (SystemExit, KeyboardInterrupt):
        log.info("Caught a signal that someone wants me to quit!")
        should_be_running = False

    if should_be_running:
        log.error("Whoops. Wasn't expecting to exit. Did a thread crash?")
       

    log.info("Dynamic Torque quitting normally. (It might take a while, don't panic!)")

    log.info("Deleting the created instances.")
    res_center.forceoff()

    # Kill all the service threads, then the info_server
    for thread in service_threads:
        thread.stop()

    for thread in service_threads:
        thread.join()

    for thread in server_threads:
        thread.stop()

    for thread in server_threads:
        thread.join()

    log.info("Dynamic Torque stopped. Bye!")

    sys.exit()

def term_handler(signal, handler):
    """Custom SIGTERM handler."""
    log.info("Recieved SIGTERM signal")
    sys.exit()

def set_options(parser):
    """Sets the command-line options for a passed in OptionParser object (via optparse)."""
    # Option attributes: action, type, dest, help. See optparse documentation.
    # Defaults: action=store, type=string, dest=[name of the option] help=none
    parser.add_option("-f", "--config-file", dest="config_file",
                      metavar="FILE",
                      help="Designate a config file for VM Pool")

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

