IF_NAME=eth0
TARGET_IP=172.17.0.1

tc qdisc del dev ${IF_NAME} root
tc qdisc add dev ${IF_NAME} root handle 1: htb
tc class add dev ${IF_NAME} parent 1: classid 1:1 htb rate 100kbit
tc qdisc add dev ${IF_NAME} parent 1:1 netem delay 75ms 0ms
tc filter add dev ${IF_NAME} protocol ip prio 1 u32 match ip dst ${TARGET_IP} flowid 1:1
