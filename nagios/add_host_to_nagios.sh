#!/bin/bash
# $1 hostname
# $2 IP

NAGIOS_HOST=/etc/nagios/nagios_host.cfg
NAGIOS_SERVICE=/etc/nagios/nagios_service.cfg
IP=$2

echo adding $IP to nagios

if [ ! -f $NAGIOS_HOST ]; then
	touch $NAGIOS_HOST
fi
if [ ! -f $NAGIOS_SERVICE ]; then
	touch $NAGIOS_SERVICE
fi

sed -e "s/IP_ADDRESS/$IP/" $(dirname $0)/host.template >> $NAGIOS_HOST
sed -e "s/IP_ADDRESS/$IP/" $(dirname $0)/service.template >> $NAGIOS_SERVICE

/sbin/service nagios restart