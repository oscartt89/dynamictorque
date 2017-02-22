#!/bin/bash

/bin/sed -i 's/^SELINUX=.*$/SELINUX=disabled/' /etc/selinux/config
/usr/sbin/setenforce Permissive

PBS_SERVER=vm-115-146-93-106.melbourne.rc.nectar.org.au

cat << EOF >> /etc/hosts
115.146.93.106 vm-115-146-93-106.melbourne.rc.nectar.org.au
EOF

# figure out correct hostname
IP=$(/sbin/ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | cut -d' ' -f1)
NAME=$(nslookup $IP | grep "name =" | cut -d" " -f3)
HOSTNAME=$(echo $NAME | sed - -e "s/\.$//")
if [ ! "$(hostname)" = "$HOSTNAME" ]; then
    # set hostname in system files
    /bin/hostname $HOSTNAME
    echo "$IP $HOSTNAME" >> /etc/hosts
    /bin/sed -i -e "s/^HOSTNAME=.*$/HOSTNAME=$HOSTNAME/" /etc/sysconfig/network
fi

if [ ! -f /etc/munge/munge.key ]; then
cat << EOF > /etc/munge/munge.key
VOwB5qJrGNQt0tpNhPOn0usDhg531SBGOJEnU2l0XmmjqCq7CrpfzWaf0vins0ohjoc8hKuqT6Ev9TNXhPYQnOCW9FCR5beAOkv6ywgRBIlCQgS3P04Kh9REOepSJTiFwEWx878ACKUWntFNzi6SkV2v8kNdBmoCfbDHgCFhlWPR2sGZqHma5UZOUTysGTVCHYeJbVajcFoVhEdwwLXnuGk2ZHOlQTXDDRVZ7vYZDlDw7Yo3ANJ3C4l2sAKEFdYIlmRpqc53t6SscybIrwUmag7FQzVS3x2VTWykCwkqBkuB80cRuwQDEKpS9qJa9iiLMOoOjAYadZvlWdwFXdAsoiqaJQr4uMLed6JY5sf9gzsxSyrPpK6NzmkHMMrOdlf8XjQBuMAsNd0WbGQWJGOy0Z3GoY2o0eFBMbxNFYSUAOKGQRtEI42Ii9y2dlPq4ok1c9FzZh1RQPoduLUPIoHfYftLbR9P6Dun61FJ7CFRRkEoNW8PIcTUUQG4UnZ7dDSTAyc8Mko2fZz8ARgqMhEt2eojtWghxyBYYDgtp2BZfTiEf0id7vg37cfUDyX8LmjUmDAgJhDbHoK4UQ3yxUbUQyCaAkebebn8rXvU4wqcWfTotrKZA796tJe7G6ROBHOzWbNAmO0ZOBS8Oetmwtklt4L2jDxTeuSaqGJEHLn1Qz9iHkim1VWOeAc7megU26ePrOGoBr9Cn8ugusdwhk4XFuBKkTJVg0TUXPdfvBkPiXNHsLuxje6hqP8lp7EibMTvFnC8CUJMhEcKwABSPzi187fJxaiwIzDDE7sM334OFtcc2Q96g1wCaumfDEf67GXYCGMPVITm4XrMekrRR0BZR3KeEZj0LlKtgtgL5PvheVMXyfqRNzNbCrrZ17vtzL79aYtB9FxTMA2rUtMR3RU77yMTqq0xMgwhdSJ2ClH52XFI3lhQ9XfS9jYTsVh3AfUjtVVfghgmLh2JRXMPO2wSaydPMPbhf2JeIzKRyiZSng2lGrbOD6ByAg0eo1CiiSR9
EOF
	chown munge:munge /etc/munge/munge.key
	chmod 600 /etc/munge/munge.key
	/etc/init.d/munge start
	/sbin/chkconfig munge on
fi

echo "export PATH=\$PATH:/usr/local/bin" > /etc/profile.d/env.sh

cat << EOF > /usr/local/bin/setupATLAS
#!/bin/bash

source \$ATLAS_LOCAL_ROOT_BASE/user/atlasLocalSetup.sh "\$@"
EOF
chown root:root /usr/local/bin/setupATLAS
chmod 755 /usr/local/bin/setupATLAS

yum install -y python-devel fio openssl098e gsl compat-libgfortran-41
yum upgrade libxml2 -y
yum install -y libxml2.i686

#mount -t xtreemfs -o allow_other tg5.tev.unimelb.edu.au/datavol /data
#mount.xtreemfs --enable-async-writes --linger-timeout 86400 -o allow_other,kernel_cache,user_xattr --no-default-permissions rcs1.mel.coepp.org.au/home /data
if [ ! -f /etc/idmapd.conf ]; then
		yum install -y nfs-utils
        sed -i '/Domain/c\Domain = COEPP.ORG.AU' /etc/idmapd.conf
        service rpcidmapd restart
fi
mount -t nfs4 -o rsize=32768,wsize=32768,noatime rcs3.mel.coepp.org.au:/home /data

if [ ! -d /ceph ]; then
cat << EOF > /etc/yum.repos.d/ceph.repo
[ceph]
name=Ceph dumpling repository
baseurl=http://ceph.com/rpm-dumpling/el6/x86_64/
enabled=1
gpgcheck=1
gpgkey=https://ceph.com/git/?p=ceph.git;a=blob_plain;f=keys/release.asc
priority=5
EOF
yum install -y ceph-fuse
cat << EOF > /etc/ceph/ceph.conf
[global]
mon initial members = tg4, tg5
osd journal size = 1024
mon host = 192.43.208.54,192.43.208.55
filestore xattr use omap = true
fsid = 1987ba73-bf96-46b0-8ee1-aabdf6d96703
auth supported = cephx
EOF
cat << EOF > /etc/ceph/ceph.client.admin.keyring
[client.admin]
        key = AQC0+xtSKJRNMhAA32CyZmEWAX2GyTmefidu9w==
EOF
mkdir /ceph
fi
ceph-fuse /ceph

if [ ! -d /pvfs ]; then
cd /opt
wget --no-check-certificate "https://swift.rc.nectar.org.au:8888/v1/AUTH_376/orangefs/orangefs?temp_url_sig=556f01af64d41c1292edff7e4013794e1d888dd3&temp_url_expires=1411191186" -O orangefs.tar.gz
tar xfvz orangefs.tar.gz
insmod `find /opt/orangefs -name pvfs2.ko`
/opt/orangefs/sbin/pvfs2-client
cat << EOF > /etc/pvfs2tab
tcp://rcs1:3334/pvfs2-fs /pvfsrcs1 pvfs2 defaults,noauto 0 0
EOF
cat << EOF >> /etc/hosts
192.231.127.226 rcs1
192.231.127.227 rcs2
192.231.127.229 rcs4
EOF
mkdir /pvfs
mount -t pvfs2 tcp://rcs1:3334/pvfs2-fs /pvfs
fi

if [ ! -d /fhgfs ]; then
wget http://www.fhgfs.com/release/latest-stable/dists/fhgfs-rhel6.repo -O /etc/yum.repos.d/fhgfs-rhel6.repo
yum install -y fhgfs-client fhgfs-helperd fhgfs-utils kernel-devel-2.6.32-358.el6.x86_64 perl
cat << EOF >> /etc/hosts
115.146.86.3	fs1
115.146.86.41	fs2
115.146.86.52	fs3
115.146.85.117	admon
EOF
/bin/sed -i -e "s/^sysMgmtdHost.*$/sysMgmtdHost=admon/" /etc/fhgfs/fhgfs-client.conf
mkdir /fhgfs
cat << EOF > /etc/fhgfs/fhgfs-mounts.conf
/fhgfs /etc/fhgfs/fhgfs-client.conf
EOF
/etc/init.d/fhgfs-helperd start
/etc/init.d/fhgfs-client start
fi

if grep -qF localhost /etc/torque/server_name; then
	echo "$PBS_SERVER" > /etc/torque/server_name
cat << EOF > /etc/torque/mom/config
# Configuration for pbs_mom.
\$pbsserver $PBS_SERVER
\$logevent    255
\$usecp *:/data/ /data/
EOF
cat << EOF > /var/lib/torque/mom_priv/prologue
#!/bin/sh

# Check the home directory of the user exists before job starts
if [ ! -d /home/\$2 ]
then
mkdir -p /home/\$2
chown \$2:\$3 /home/\$2
fi

exit 0
EOF
cat << EOF >> /var/lib/torque/pbs_environment
PBSCOREDUMP=yes
EOF
    chmod 500 /var/lib/torque/mom_priv/prologue
	/etc/init.d/pbs_mom start
	/sbin/chkconfig pbs_mom on
fi

mkdir /mnt/cvmfs-cache

# temp user
#useradd -u 32258 shunde

# nsca
yum install -y nsca-client
yum install -y nagios-plugins-load nagios-plugins-disk
/bin/sed -i -e "s/^#password=/password=coepp_12qwER/" /etc/nagios/send_nsca.cfg
cat << EOF > /usr/lib64/nagios/plugins/check_mountpoints.py
#!/usr/bin/python

import string
import sys

fstab_content=open('/etc/fstab','r')
mountlist = list()
i=0
exitstatus=1
mounted=False
mountstate='Mounts not OK'


for line in fstab_content:
 if '#' not in line and len(line) > 2 and 'nfs' in line:
        (fstabfs,fstabmountpt,fstabtype,fstaboptions,fstabdump,fstabpass)=line.strip().split()
        procmounts_content=open('/proc/mounts','r')
        for line in procmounts_content:
                ((procfs,procmountpt,proctype,procoptions,procdump,procpass))=line.strip().split()
                if fstabtype == 'nfs4' and proctype == 'nfs4':
                        if fstabmountpt == procmountpt:
                                mounted=True
        procmounts_content.close()
        if mounted:
                exitstatus=0
                mountstate='Mounts OK'
        else:
                exitstatus=1
                mountstate="Mounts not OK"
                print mountstate
                sys.exit(exitstatus)
        mounted=False

print mountstate
sys.exit(exitstatus)
EOF
chmod +x /usr/lib64/nagios/plugins/check_mountpoints.py
cat << EOF > /usr/lib64/nagios/plugins/check_pbsmom
#!/bin/bash
# SYNOPSIS
#       check_pbsmom [<TCP port>] [<TCP port>] ...
#
# DESCRIPTION
#       This NAGIOS plugin checks whether: 1) pbs_mom is running and
#       2) the host is listening on the given port(s).  If no port
#       number is specified TCP ports 15002 and 15003 are checked.
#
# AUTHOR
#       Wayne.Mallett@jcu.edu.au

OK=0
WARN=1
CRITICAL=2
PATH="/bin:/sbin:/usr/bin:/usr/sbin"

# Default listening ports are TCP 15004 and 42559.
if [ \$# -lt 1 ] ; then
  list="15002 15003"
else
  list="\$*"
fi

if [ `ps -C pbs_mom | wc -l` -lt 2 ]; then
  echo "PBS_MOM CRITICAL:  Daemon is NOT running!"
  exit \$CRITICAL
else
  for port in \$list ; do
    if [ `netstat -ln | grep -E "tcp.*:\$port" | wc -l` -lt 1 ]; then
      echo "PBS_MOM CRITICAL:  Host is NOT listening on TCP port \$port!"
      exit \$CRITICAL
    fi
  done
  echo "PBS_MOM OK:  Daemon is running.  Host is listening."
  exit \$OK
fi
EOF
chmod +x /usr/lib64/nagios/plugins/check_pbsmom
cat << EOF > /usr/lib64/nagios/plugins/check_cvmfs.sh
#!/bin/bash
# CernVM-FS check for Nagios
# Version 1.5, last modified: 08.06.2012
# Bugs and comments to Jakob Blomer (jblomer@cern.ch)
#
# ChangeLog
# 1.5:
#    - return STATUS_UNKNOWN if extended attribute cannot be read
#    - return immediately if transport endpoint is not connected
#    - start of ChangeLog

VERSION=1.5

STATUS_OK=0          
STATUS_WARNING=1     # CernVM-FS resource consumption high or 
                     # previous error status detected
STATUS_CRITICAL=2    # CernVM-FS not working
STATUS_UNKNOWN=3     # Internal or usage error

BRIEF_INFO="OK"
RETURN_STATUS=\$STATUS_OK


usage() {
   /bin/echo "Usage:   \$0 [-n] <repository name> [expected cvmfs version]"
   /bin/echo "Example: \$0 -n atlas.cern.ch 2.0.4"
   /bin/echo "Options:"
   /bin/echo "  -n  run extended network checks"
}

version() {
   /bin/echo "CernVM-FS check for Nagios, version: \$VERSION"
}

help() {
   version
   usage
}

# Make a version in the format RELEASE.MAJOR.MINOR.PATCH
sanitize_version() {
   local version; version=\$1
   
   ndots=\`/bin/echo \$version | /usr/bin/tr -Cd . | /usr/bin/wc -c\`
   while [ \$ndots -lt 3 ]; do
      version="\${version}.0"
      ndots=\`/bin/echo \$version | /usr/bin/tr -Cd . | /usr/bin/wc -c\`
   done
   
   echo \$version
}

# Appends information to the brief output string
append_info() {
   local info; info=\$1
   
   if [ "x\$BRIEF_INFO" == "xOK" ]; then
      BRIEF_INFO=\$info
   else
      BRIEF_INFO="\${BRIEF_INFO}; \$info"
   fi
}

# Read xattr value from current directory into XATTR_VALUE variable
get_xattr() {
   XATTR_NAME=\$1
   
   XATTR_VALUE=\`/usr/bin/attr -q -g \$XATTR_NAME .\`
   if [ \$? -ne 0 ]; then
      /bin/echo "SERVICE STATUS: failed to read \$XATTR_NAME attribute"
      exit \$STATUS_UNKNOWN
   fi
}




# Option handling
OPT_NETWORK_CHECK=0
while getopts "hVvn" opt; do
  case \$opt in
    h)
      help
      exit \$STATUS_OK
    ;;
    V)
      version
      exit \$STATUS_OK
    ;;  
    v)
      /bin/echo "verbose mode"
    ;;  
    n)
      OPT_NETWORK_CHECK=1
    ;;
    *)
      /bin/echo "SERVICE STATUS: Invalid option: \$1"
      exit \$STATUS_UNKNOWN 
      ;;
  esac
done
shift \$[\$OPTIND-1]

REPOSITORY=\$1
VERSION_EXPECTED=\$2

if [ -z "\$REPOSITORY" ]; then
   usage
   exit \$STATUS_UNKNOWN    
fi


# Read repository config
if [ -f /etc/cvmfs/config.sh ]
then
  . /etc/cvmfs/config.sh
else
  /bin/echo "SERVICE STATUS: /etc/cvmfs/config.sh missing"
  exit \$STATUS_UNKNOWN
fi
cvmfs_readconfig
if [ \$? -ne 0 ]; then
  /bin/echo "SERVICE STATUS: failed to read CernVM-FS configuration"
  exit \$STATUS_CRITICAL
fi
FQRN=\`cvmfs_mkfqrn \$REPOSITORY\`
ORG=\`cvmfs_getorg \$FQRN\`
cvmfs_readconfig \$FQRN
if [ \$? -ne 0 ]; then
  /bin/echo "SERVICE STATUS: failed to read \$FQRN configuration"
  exit \$STATUS_CRITICAL
fi



# Grab mountpoint / basic availability
cd "\${CVMFS_MOUNT_DIR}/\$FQRN" && ls . > /dev/null
if [ \$? -ne 0 ]; then
  /bin/echo "SERVICE STATUS: failed to access \$FQRN"
  exit \$STATUS_CRITICAL
fi


# Gather information
get_xattr version; VERSION_LOADED=\`sanitize_version \$XATTR_VALUE\`
VERSION_INSTALLED=\`/usr/bin/cvmfs2 --version 2>&1 | /bin/cut -d" " -f3\`
VERSION_INSTALLED=\`sanitize_version \$VERSION_INSTALLED\`
get_xattr nioerr; NIOERR=\$XATTR_VALUE
get_xattr usedfd; NFDUSE=\$XATTR_VALUE
get_xattr maxfd; NFDMAX=\$XATTR_VALUE
get_xattr nclg; NCATALOGS=\$XATTR_VALUE
get_xattr revision; REVISION=\$XATTR_VALUE
get_xattr pid; PID=\$XATTR_VALUE
MEMKB=\`/bin/ps -p \$PID -o rss= | /bin/sed 's/ //g'\`
if [ \$PIPESTATUS -ne 0 ]; then
   /bin/echo "SERVICE STATUS: failed to read memory consumption"
   exit \$STATUS_UNKNOWN
fi


# Network settings;  TODO: currently configured values required
if [ \$OPT_NETWORK_CHECK -eq 1 ]; then
   if [ ! -z "\$CVMFS_HTTP_PROXY" -a ! -z "\$CVMFS_SERVER_URL"  ]; then
      CVMFS_HOSTS=\`/bin/echo "\$CVMFS_SERVER_URL" | /bin/sed 's/,\|;/ /g' \
         | sed s/@org@/\$ORG/g | sed s/@fqrn@/\$FQRN/g\`
      CVMFS_PROXIES=\`/bin/echo "\$CVMFS_HTTP_PROXY" | /bin/sed 's/;\||/ /g'\`
   else
      /bin/echo "SERVICE STATUS: CernVM-FS configuration error"
      exit \$STATUS_UNKNOWN
   fi
                   
   get_xattr timeout; CVMFS_TIMEOUT_PROXY=\$XATTR_VALUE
   get_xattr timeout_direct; CVMFS_TIMEOUT_DIRECT=\$XATTR_VALUE
fi


# Check for CernVM-FS version
if [ "\$VERSION_INSTALLED" != "\$VERSION_LOADED" ]; then
   append_info "version mismatch (loaded \$VERSION_LOADED, installed \$VERSION_INSTALLED)"
   RETURN_STATUS=\$STATUS_WARNING
fi

if [ "x\$VERSION_EXPECTED" != "x" ]; then
   VERSION_EXPECTED=\`sanitize_version \$VERSION_EXPECTED\`
   if [ "\$VERSION_EXPECTED" != "\$VERSION_INSTALLED" ]; then
      append_info "version mismatch (expected \$VERSION_EXPECTED, installed \$VERSION_INSTALLED)"
      RETURN_STATUS=\$STATUS_WARNING
   fi
fi

# Check for previously detected I/O errors
if [ \$NIOERR -gt 0 ]; then
   append_info "\$NIOERR I/O errors detected"
   RETURN_STATUS=\$STATUS_WARNING
fi

# Check for number of open file descriptors
FDRATIO=\$[\$NFDUSE*100/\$NFDMAX]
if [ \$FDRATIO -gt 80 ]; then
   append_info "low on open file descriptors (\${FDRATIO}%)"
   RETURN_STATUS=\$STATUS_WARNING
fi

# Check for memory footprint (< 50M or < 1% of available memory?)
MEM=\$[\$MEMKB/1024]
if [ \$MEM -gt 50 ]; then
   MEMTOTAL=\`/bin/grep MemTotal /proc/meminfo | /bin/awk '{print \$2}'\`
   # More than 1% of total memory?
   if [ \$[\$MEMKB*100] -gt \$MEMTOTAL ]; then
      append_info "high memory consumption (\${MEM}m)"
      RETURN_STATUS=\$STATUS_WARNING
   fi
fi

# Check for number of loaded catalogs (< 10% of FDMAX?)
if [ \$[\$NCATALOGS*10] -gt \$NFDMAX ]; then
   append_info "high no. loaded catalogs (\${NCATALOGS})"
   RETURN_STATUS=\$STATUS_WARNING
fi

# Check for free space on cache partition
DF_CACHE=\`/bin/df -P "\$CVMFS_CACHE_BASE"\`
if [ \$? -ne 0 ]; then
   append_info "failed to run /bin/df -P \$CVMFS_CACHE_BASE"
   RETURN_STATUS=\$STATUS_CRITICAL
else
   FILL_RATIO=\`/bin/echo "\$DF_CACHE" | /usr/bin/tail -n1 | \
               /bin/awk '{print \$5}' | /usr/bin/tr -Cd [:digit:]\`
   if [ \$FILL_RATIO -gt 95 ]; then
      append_info "space on cache partition low"
      RETURN_STATUS=\$STATUS_WARNING
   fi
fi

# Network connectivity, all proxy / host combinations
if [ \$OPT_NETWORK_CHECK -eq 1 ]; then
   for HOST in \$CVMFS_HOSTS
   do
      for PROXY in \$CVMFS_PROXIES
      do
         if [ \$PROXY != "DIRECT" ]; then
            PROXY_ENV="env http_proxy=\$PROXY"
            TIMEOUT=\$CVMFS_TIMEOUT
         else
            PROXY_ENV=
            TIMEOUT=\$CVMFS_TIMEOUT_DIRECT
         fi
         URL="\${HOST}/.cvmfspublished"
         \$PROXY_ENV /usr/bin/curl -f --connect-timeout \$TIMEOUT \$URL > \
           /dev/null 2>&1
         if [ \$? -ne 0 ]; then
            append_info "offline (\$HOST via \$PROXY)"
            RETURN_STATUS=\$STATUS_WARNING
         fi
      done
   done
fi

if [ -f "/cvmfs/\${REPOSITORY}/.cvmfsdirtab" ]; then
   cat "/cvmfs/\${REPOSITORY}/.cvmfsdirtab" > /dev/null 2>&1
   if [ \$? -ne 0 ]; then
      append_info "failed to read .cvmfsdirtab from repository"
      RETURN_STATUS=\$STATUS_CRITICAL
   fi
fi


/bin/echo "SERVICE STATUS: \$BRIEF_INFO; repository revision \$REVISION"
exit \$RETURN_STATUS
EOF
chmod +x /usr/lib64/nagios/plugins/check_cvmfs.sh
cat << EOF > /usr/local/bin/send_passive_message 
#!/bin/bash

IP=\$(/sbin/ifconfig eth0 | grep 'inet addr:' | cut -d: -f2 | cut -d' ' -f1)
NSCA_SERVER=115.146.84.146

OUTPUT=\$(eval \$2)
RETURN_CODE=\$?
printf "%s\t%s\t%s\t%s\n" "\$IP" "\$1_\$IP" "\$RETURN_CODE" "\$OUTPUT" | /usr/sbin/send_nsca -H \$NSCA_SERVER
EOF
chmod +x /usr/local/bin/send_passive_message
cat << EOF > /etc/cron.d/nsca
*/1 * * * * root /usr/local/bin/send_passive_message check_disk "/usr/lib64/nagios/plugins/check_disk -w 10\% -c 5\% -p /tmp -p /var -C -w 100000 -c 50000 -p /"
*/1 * * * * root /usr/local/bin/send_passive_message check_load "/usr/lib64/nagios/plugins/check_load -w 15,10,5 -c 30,25,20"
*/5 * * * * root /usr/local/bin/send_passive_message check_mount_points "/usr/lib64/nagios/plugins/check_mountpoints.py"
*/3 * * * * root /usr/local/bin/send_passive_message check_pbs_mom "/usr/lib64/nagios/plugins/check_pbsmom"
*/5 * * * * root /usr/local/bin/send_passive_message check_cvmfs_coepp "/usr/lib64/nagios/plugins/check_cvmfs.sh -n experimental.cloud.coepp.org.au"
*/5 * * * * root /usr/local/bin/send_passive_message check_cvmfs_atlas "/usr/lib64/nagios/plugins/check_cvmfs.sh -n atlas.cern.ch"
*/5 * * * * root /usr/local/bin/send_passive_message check_cvmfs_belle "/usr/lib64/nagios/plugins/check_cvmfs.sh -n belle.cern.ch"
EOF

if [ ! -d /var/run/vmpool ]; then
	mkdir -p /var/run/vmpool
fi
touch /var/run/vmpool/alive