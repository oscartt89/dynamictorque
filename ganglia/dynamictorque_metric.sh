#!/bin/bash

GMETRIC="/usr/bin/gmetric"

/opt/dynamictorque/admin.py -g | while read line;
do
PX=($(echo "${line}"|cut -d " " -f 1,2 ))
pxname=$(echo ${PX[0]} )
pxvalue=$(echo ${PX[1]} )
#echo [$pxname][$pxvalue]
$GMETRIC --group "dynamic_torque" --name $pxname --value $pxvalue --type int16
done
