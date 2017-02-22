#!/usr/bin/env python
# vim: set expandtab ts=4 sw=4:

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## Dynamic Torque job management class
# this is only for passive mode. it provides a way for admins to get information, control worker nodes

import logging
import threading
import time
import socket
import sys
import platform
import re
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

import dynamictorque.config as config

log = None

class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class InfoServer(threading.Thread,):
    job_pool = None
    def __init__(self, j_pool):

        global log
        log = logging.getLogger("dynamictorque")

        #set up class
        threading.Thread.__init__(self, name=self.__class__.__name__)
        self.done = False
        job_pool = j_pool
        host_name = "0.0.0.0"
        #set up server
        try:
            self.server = SimpleXMLRPCServer((host_name,
                                              config.info_server_port),
                                              requestHandler=RequestHandler,
                                              allow_none=True,
                                              logRequests=False)
            self.server.register_introspection_functions()
            self.server.socket.settimeout(1)
            #self.server.register_introspection_functions()
        except:
            log.error("Couldn't start vm server: %s" % sys.exc_info()[0])
            sys.exit(1)

        # Register an instance; all the methods of the instance are
        # published as XML-RPC methods
        class externalFunctions:
            def info(self):
                return job_pool.get_info()
            def kill(self, vm_name):
                try:
                    job_pool.kill_vm(vm_name)
                    return 0, ""
                except Exception,e:
                    return 1, str(e)
            def get_detail(self, vm_name):
                return job_pool.get_detail(vm_name)
            def forceoff(self):
                job_pool.forceoff()
            def toggle_sleep_mode(self):
                job_pool.toggle_sleep_mode()

        self.server.register_instance(externalFunctions())

    def run(self):

        # Run the server's main loop
        log.info("Started info server on port %s" % config.info_server_port)
        while self.server:
            try:
                self.server.handle_request()
                if self.done:
                    log.debug("Killing info server...")
                    self.server.socket.close()
                    break
            except socket.timeout:
                log.warning("info server's socket timed out. Don't panic!")

    def stop(self):
        self.done = True
