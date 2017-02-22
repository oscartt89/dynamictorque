import subprocess
import re
import logging as log

sp = subprocess.Popen(["/usr/bin/pbsnodes", "dynamictorque-worker"], shell=False,
           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(cmd_out, cmd_err) = sp.communicate(input=None)
returncode = sp.returncode
if returncode != 0:
    log.error("checknode returns error, probably the node does not exist: cmd_out %s" % cmd_out)
    log.error("cmd_err %s" % cmd_err)
m1=re.search("state = (.*)",cmd_out)
m2=re.search("rectime=([0-9]*)",cmd_out)
if m1 is not None and len(m1.groups())>0 and m2 is not None and len(m2.groups())>0:

    state=m1.groups()[0].strip().lower()
    length=m2.groups()[0].strip()
    log.error("wn is in current state %s for %s"%(state, length))
#    numbers=list(reversed(length.split(":")))
#    total_seconds=int(numbers[0])
else:
    log.error("can't find node's state from")
    log.error("cmd_out %s" % cmd_out)
    log.error("cmd_err %s" % cmd_err)
    log.error("returncode %s" % returncode)
    log.error("m1 %s" % m1)
    log.error("m2 %s" % m2)
