#!/bin/bash
# $1 hostname
# $2 IP

NAGIOS_HOST=/etc/nagios/nagios_host.cfg
NAGIOS_SERVICE=/etc/nagios/nagios_service.cfg
IP=$2
echo removing $IP from nagios

sed -i "/#Start $IP/,/#End $1/d" $NAGIOS_HOST
sed -i "/#Start $IP/,/#End $1/d" $NAGIOS_SERVICE

/sbin/service nagios restart