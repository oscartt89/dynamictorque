#!/bin/bash

LOG_FILE=/var/log/dynamictorque/restart_maui.log
if [ ! -f $LOG_FILE ]; then
  touch $LOG_FILE
fi

for s in `diagnose -n | grep -v -i drain | grep -v -i warning | head -n -4 | tail -n +4 | awk '{print $3 $13}'`; do
#  echo s $s
  s1=`echo $s|cut -d '[' -f 1`
  s2=`echo $s|cut -d '[' -f 2`
#  echo s1 $s1 s2 $s2
  real_n=`echo $s1|cut -d ':' -f 2`
  current_n=`echo $s2|cut -d ':' -f 2|cut -d ']' -f 1`
#  echo $real_n $current_n
  if [ $real_n -ne $current_n ]; then
    echo $(date) $s - need to restart maui >> $LOG_FILE
    #/etc/init.d/maui restart
    /etc/init.d/maui stop; killall -9 maui; sleep 5; /etc/init.d/maui start
    exit 0
  fi
done