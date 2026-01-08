Daemons
=======

Simple daemon
-------------

The **simple** daemon is a small static multicast routing daemon with a REST API.
It consumes a config file (default: ``/etc/simple.ini``), programs multicast VIFs
and static MFC entries into the Linux kernel, and optionally installs dynamic
entries on-demand when the kernel sends ``IGMPMSG_NOCACHE`` control messages.

Configuration
~~~~~~~~~~~~~

Config is INI format:

- ``[phyints]``: comma-separated list of interface names to register as multicast VIFs.
- ``[mroute_<name>]`` blocks: each block defines an incoming interface, a multicast group,
  and one or more outgoing interfaces with optional TTL thresholds.

``to`` syntax
^^^^^^^^^^^^^

The ``to`` field is a **comma-separated** list of outgoing interfaces. Each entry can be either:

- ``IFACE``: defaults TTL threshold to **1**
- ``IFACE=TTL``: sets TTL threshold explicitly

Example (from tests):

.. code-block:: ini

   to = a2,a3=2

This means forward out ``a2`` with TTL threshold 1 and out ``a3`` with TTL threshold 2.

Example:

.. code-block:: ini

   [phyints]
   names=eth0,br0

   [mroute_1]
   from = eth0
   # either a single group:
   # group = 239.1.0.1
   # or a prefix:
   group = 239.1.0.0/24
   to = br0=1
   # optional:
   # source = 0.0.0.0

Running
~~~~~~~

Install the optional daemon dependencies:

.. code-block:: bash

   pip install "py-gmp[daemons]"

Run the daemon (root is required to configure multicast routing):

.. code-block:: bash

   sudo python3 -m pygmp simple --config /etc/simple.ini --host 0.0.0.0 --port 8000

Then browse the API docs at ``/docs`` on the configured host/port.

API
~~~

The daemon exposes endpoints for listing VIFs and MFC entries:

- ``GET /vifs``
- ``GET /static_mfc``
- ``GET /dynamic_mfc``

The daemon also accepts basic route updates:

- ``POST /mfc`` and ``DELETE /mfc`` with a JSON body:

.. code-block:: json

   {
     "from": "a1",
     "group": "239.0.0.4",
     "to": "a2,a3=2",
     "source": "0.0.0.0"
   }

