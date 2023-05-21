#!/bin/bash

OVERWRITE=false

set -e

[ "$(id -u)" != 0 ] && {
    echo "ERROR - Must run as root." >&2
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]
do
  key="$1"
  case $key in
    --overwrite)
      OVERWRITE=true
      shift # past argument
      ;;
    *)
      echo "Unknown option: $key"
      exit 1
      ;;
  esac
done


summary () {
  name=$1

  echo "Summary for $name"
  printf "================\n"
  printf "\nDevices:\n"
  ip netns exec "$name" ip -br link show
  printf "\nAddresses:\n"
  ip netns exec "$name" ip -br addr show
  printf "\nNeighbors:\n"
  ip netns exec "$name" ip -br neigh show
  printf "\nRoutes:\n"
  ip netns exec "$name" ip -br route show

}

basic () {
  printf "\nCreating basic network...\n"
  ip netns add basic

  # setup veth pair for REST API access
  ip link add veth0 type veth peer name veth1
  ip link set veth1 netns basic
  ip addr add 172.20.0.1/24 dev veth0
  ip link set veth0 up
  ip netns exec basic ip addr add 172.20.0.2/24 dev veth1
  ip netns exec basic ip link set veth1 up

  # setup iptables for veth pair
  iptables -t nat -A PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 172.20.0.2:8000
  ip netns exec basic iptables -t nat -A POSTROUTING -p tcp --sport 8000 -j MASQUERADE

  ip netns exec basic ip link add a1 type dummy
  ip netns exec basic ip link set a1 up
  ip netns exec basic ip link set a1 multicast on

  ip netns exec basic ip link add a2 type dummy
  ip netns exec basic ip link set a2 up
  ip netns exec basic ip link set a2 multicast on

  ip netns exec basic ip link add a3 type dummy
  ip netns exec basic ip link set a3 up
  ip netns exec basic ip link set a3 multicast on

  ip netns exec basic ip addr add 10.0.0.1/24 dev a1
  ip netns exec basic ip addr add 20.0.0.1/24 dev a2
  ip netns exec basic ip addr add 30.0.0.1/24 dev a3

  ip netns exec basic ip link set lo up

  summary basic

}

main () {

  # a basc network setup =============================================
  if [ "$OVERWRITE" == true ] && [ "$(ip netns list | grep -wc "basic")" -eq 1 ]; then
    echo "Deleting existing basic namespace and iptable rules..."
    iptables -t nat -D PREROUTING -p tcp --dport 8080 -j DNAT --to-destination 172.20.0.2:8000
    ip netns delete basic
    ip link del veth0
  fi

  [[ $(ip netns list | grep -wc "basic") -eq 0 ]] && {
    basic

  # a more complex network setup =============================================
  # TODO

  }

}

main