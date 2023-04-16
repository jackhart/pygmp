#!/bin/sh

# Set up a basic dummy interface topology

ip link add a1 type dummy
ip link set a1 up
ip link set a1 multicast on

ip link add a2 type dummy
ip link set a2 up
ip link set a2 multicast on

ip addr add 10.0.0.1/24 dev a1
ip addr add 20.0.0.1/24 dev a2
ip -br a
