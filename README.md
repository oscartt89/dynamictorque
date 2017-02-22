Dynamic Torque (BITLAB)
======
Code of the dynamictorque implementation working with TORQUE/MAUI and OpenStack

Installation
======

Dynamic Torque can run in active mode (Dynamic Torque queries Torque for new jobs) or passive mode (Torque requests VMs when a job comes in). 
However, active mode is the current recommended mode to use.

To configure Dynamic Torque to work in active mode, follow the steps:

    $ pip install python-novaclient
    # git clone code
    # put dynamic_torque.conf under /etc/dynamictorque
    # Copy init.d script, e.g.
    $ cp scripts/dynamictorque /etc/init.d/
    $ mkdir /var/log/dynamictorque

Torque/Maui
======

It is necessary to turn on "auto_np" so that Torque can figure out how many cores a new VM has:

    $ qmgr -c 'set server auto_node_np = True'

Dynmaic Torque can monitor all jobs in Torque, or only jobs submitted to one or several queues. This can be set in the config, e.g.

    torque_queue_to_monitor: cloud
    
A typical use case is to monitor a specific queue, e.g. named 'cloud', and fire up worker nodes for it. This can be done via the use of node property.

On Torque, set the queue to require nodes with a specific property.

    $ qmgr -c 'set queue cloud resources_default.neednodes = CLOUD'
    
In Dynamic Torque's config, tell Dynamic Torque to add that property when launch a new worker node

    node_property: CLOUD
    
You may also want to restart Maui periodically, e.g. once or twice a day, to refresh the dynamic information. You can set up a cron job to do this.

Configuration
======
Edit dynamic_torque.conf. Minimum changes include:

  * max number of cores that can be used
  * all parameters in cloud section
  * logging

Admin Tool
======
admin.py is the main tool for sysdamins to manage Dynamic Torque

  * admin.py -i: list all current information, including existing worker nodes, nodes in start progress, nodes in delete progress, jobs, etc 
  * admin.py -i -c S: as above, but runs continuously and refreshes every S seconds
  * admin.py -s: put Dynamic Torque in sleep mode, under sleep mode it will not fire up new worker nodes, but can delete existing nodes
  * admin.py -k NODE_HOSTNAME: delete a worker node whose hostname is NODE_HOSTNAME, but it has to be idle without running jobs
  * admin.py -f: delete all worker nodes. They will be set to offline in Torque to prevent getting new jobs, then wait for current jobs to finish, then shut down.

In a scenario where you need to remove all current worker nodes and launch new ones, e.g. because the image has changed, you can use -s to put Dynamic Torque in sleep mode, then use -f to gracefully shutdown all worker nodes, then restart the service to pick up new configurations.

Logrotate
======
If you want to use logrotate to restrict the size of log file, logrotate/dynamictorque is an example

Prevent Timeouts in SSH
======
Add the following two lines to /etc/ssh/ssh_config. This will make the client poll for server every 30 seconds. If the servers fails to respond for 4 times (i.e., 2 mins), the client will close the connection. Note that this applies to version 2 of OpenSSH only.

    ServerAliveInterval 30
    ServerAliveCountMax 4

    
License
======
This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; either version 3, or (at your option) any later version.

You should have received a copy of the GNU General Public License along with this program in the file named "LICENSE". If not, write to the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA or visit their web page on the internet at http://www.gnu.org/copyleft/gpl.html.
