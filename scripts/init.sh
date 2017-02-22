#!/bin/bash

yum install -y gcc gcc-c++

cat << EOF > /etc/yum.repos.d/cernvm.repo
[cernvm]
name=CernVM packages
baseurl=http://cvmrepo.web.cern.ch/cvmrepo/yum/cvmfs/EL/5/x86_64/
gpgcheck=0
enabled=1
protect=1
EOF

yum install -y cvmfs cvmfs-init-scripts cvmfs-auto-setup

cat << EOF > /etc/cvmfs/default.local
CVMFS_CACHE_BASE=/opt/cvmfs-cache
CVMFS_QUOTA_LIMIT=4000
CVMFS_REPOSITORIES=atlas.cern.ch,experimental.cloud.coepp.org.au,belle,atlas-condb.cern.ch,atlas-nightlies.cern.ch
#CVMFS_QUOTA_LIMIT=27000
CVMFS_HTTP_PROXY="http://rcsquid1.atlas.unimelb.edu.au:3128|http://rcsquid2.atlas.unimelb.edu.au:3128;http://cernvm-webfs.atlas-canada.ca:3128"
EOF

cat << EOF > /etc/cvmfs/default.conf
CVMFS_CACHE_BASE=/opt/cache/cvmfs
CVMFS_QUOTA_LIMIT=4000
CVMFS_DEFAULT_DOMAIN=cern.ch
CVMFS_TIMEOUT=5
CVMFS_TIMEOUT_DIRECT=10
CVMFS_STRICT_MOUNT=yes
CVMFS_FORCE_SIGNING=yes
CVMFS_NFILES=65536

# Don't touch the following values unless you're absolutely
# sure what you do.  Don't copy them to default.local either.
if [ "x\$CVMFS_BASE_ENV" == "x" ]; then
readonly CVMFS_USER=cvmfs
readonly CVMFS_MOUNT_DIR=/cvmfs
readonly CVMFS_OPTIONS=allow_other,entry_timeout=60,attr_timeout=60,negative_timeout=60,use_ino
readonly CVMFS_BASE_ENV=1
fi
EOF

cat << EOF > /etc/cvmfs/domain.d/cern.ch.local
CVMFS_SERVER_URL="http://cvmfs.fnal.gov:8000/opt/@org@;http://cvmfs.racf.bnl.gov:8000/opt/@org@;http://cernvmfs.gridpp.rl.ac.uk:8000/opt/@org@;http://cvmfs-stratum-one.cern.ch:8000/opt/@org@;http://cvmfs02.grid.sinica.edu.tw:8000/opt/@org@"
EOF

cat << EOF > /etc/cvmfs/config.d/belle.cern.ch.local
CVMFS_SERVER_URL="http://cvmfs-stratum-one.cern.ch/opt/belle"
#CVMFS_SERVER_URL="http://cvmfs-stratum-one.cern.ch/cvmfs/belle"
EOF

cat << EOF > /etc/cvmfs/domain.d/cloud.coepp.org.au.local
CVMFS_DEBUGLOG=/var/log/cvmfs/cxcvmfs.cloud.coepp.org.au.log
CVMFS_HTTP_PROXY=DIRECT
EOF

cat << EOF > /etc/cvmfs/domain.d/cloud.coepp.org.au.conf
CVMFS_SERVER_URL="http://cxcvmfs.cloud.coepp.org.au/@org@"
CVMFS_PUBLIC_KEY=/etc/cvmfs/keys/experimental.cloud.coepp.org.au.pub
CVMFS_MAX_TTL=30
EOF

cat << EOF > /etc/profile.d/cvmfs.sh
export ATLAS_LOCAL_ROOT_BASE=/cvmfs/atlas.cern.ch/repo/ATLASLocalRootBase
EOF

cat << EOF > /etc/cvmfs/keys/experimental.cloud.coepp.org.au.pub
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0engIVoPrKL2JUlUOAmx
G8Eba9do9o1jWDB9arF9eGcv24Jeg28WHLrMxWIq6RyqxJPSV3wmAILEc3E9b6o+
tdO7CezbcDg38FQHKnLgzAjk234lqySdKrvrM5lUIzOosvv0hloXBhFIJJTYDtRU
mwYEfqQLtsRcGSSHngXyS4pwkO+9XyFirSkxV4ZOqpapFb1p27PhTI+qe0YhyKEL
wfBdn95dBdo2C1X1OdsDnCJ/ndtIvV2m97NrHYEmlogDtaO9fJ7ruimws9A8MliT
pz9CkJYWQKxTkW935lgAoLq/jkCffpNN0qExZdLrvI/u5aIf8oUJOePkAC55TkFz
cQIDAQAB
-----END PUBLIC KEY-----
EOF

mkdir -p /var/log/cvmfs
service cvmfs start

cat << EOF > /etc/yum.repos.d/glusterfs-epel.repo
# Place this file in your /etc/yum.repos.d/ directory

[glusterfs-epel]
name=GlusterFS is a clustered file-system capable of scaling to several petabytes.
baseurl=http://download.gluster.org/pub/gluster/glusterfs/3.3/3.3.1/EPEL.repo/epel-5/\$basearch/
enabled=1
skip_if_unavailable=1
gpgcheck=0

[glusterfs-swift-epel]
name=GlusterFS is a clustered file-system capable of scaling to several petabytes.
baseurl=http://download.gluster.org/pub/gluster/glusterfs/3.3/3.3.1/EPEL.repo/epel-5/noarch
enabled=1
skip_if_unavailable=1
gpgcheck=0

[glusterfs-source-epel]
name=GlusterFS is a clustered file-system capable of scaling to several petabytes. - Source
baseurl=http://download.gluster.org/pub/gluster/glusterfs/3.3/3.3.1/EPEL.repo/epel-5/SRPMS
enabled=0
skip_if_unavailable=1
gpgcheck=0
EOF

yum install -y glusterfs{-fuse,-rdma}
mkdir /scratch
#mount -t glusterfs vm-115-146-93-106.rc.melbourne.nectar.org.au:/gv0 /scratch


## MUST HAVE
touch /var/run/vmpool/initiated