#!/usr/bin/env python

# Copyright (C) 2013 eResearch SA, CoEPP
# You may distribute under the terms of either the GNU General Public
# License or the Apache v2 License, as specified in the README file.
## Auth: Shunde Zhang. 30/10/2013.
##
## utility class


import logging
import string
import random

LEVELS = {'DEBUG': logging.DEBUG,
          'VERBOSE': logging.DEBUG-1,
          'INFO': logging.INFO,
          'WARNING': logging.WARNING,
          'ERROR': logging.ERROR,
          'CRITICAL': logging.CRITICAL,}

def get_logger():
    """Gets a reference to the 'vmpool' log handle."""
    logging.VERBOSE = LEVELS["VERBOSE"]
    logging.addLevelName(logging.VERBOSE, "VERBOSE")
    log = logging.getLogger("dynamictorque")
    setattr(log, "verbose", lambda *args: log.log(logging.VERBOSE, *args))
    log.addHandler(NullHandler())
    return log

class NullHandler(logging.Handler):
    def emit(self, record):
        pass
    
def get_or_none(config, section, value):
    """Return the value of a config option if it exists, none otherwise."""
    if config.has_option(section, value):
        return config.get(section, value)
    else:
        return None
    
def get_unique_string():
    return ''.join(random.choice(string.ascii_letters + string.digits) for letter in xrange(8))