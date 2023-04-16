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
  ip netns exec basic ip link add a1 type dummy
  ip netns exec basic ip link set a1 up
  ip netns exec basic ip link set a1 multicast on

  ip netns exec basic ip link add a2 type dummy
  ip netns exec basic ip link set a2 up
  ip netns exec basic ip link set a2 multicast on

  ip netns exec basic ip addr add 10.0.0.1/24 dev a1
  ip netns exec basic ip addr add 20.0.0.1/24 dev a2
  summary basic

}

main () {

  # a basc network setup =============================================
  if [ "$OVERWRITE" == true ] && [ "$(ip netns list | grep -wc "basic")" -eq 1 ]; then
    echo "Deleting existing basic namespace..."
    ip netns delete basic
  fi

  [[ $(ip netns list | grep -wc "basic") -eq 0 ]] && {
    basic

  # a more complex network setup =============================================
  # TODO

  }

}

main