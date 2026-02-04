#  MIT License
#
#  Copyright (c) 2023 Jack Hart
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
from __future__ import annotations
from pathlib import Path
import logging
import logging.config
import inspect
from typing import Any

import pygmp
import os
import signal
import contextlib
import sys


def get_logger(name) -> logging.Logger:
    """Get a configured logger instance.

    Loads the logging configuration from the package's ``log_config.ini`` file
    and returns a logger with the given name.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        Configured Logger instance.
    """
    logging.config.fileConfig(fname=Path(inspect.getfile(pygmp)).parent.joinpath("log_config.ini"))
    return logging.getLogger(name)


class DaemonContext(contextlib.ContextDecorator):
    """Context manager for daemonizing a process.

    Follows the double-fork pattern to properly detach from the controlling
    terminal and run as a background daemon. Creates a PID file for process
    management and sets up signal handlers for graceful shutdown.

    Usage::

        with DaemonContext() as ctx:
            # daemon code here
            run_server()

    Args:
        working_dir: Working directory for the daemon process.
        pid_dir: Directory for the PID file.
        umask: File creation mask for the daemon process.
        signal_map: Optional dictionary mapping signals to handler functions.
            Defaults to SIGTERM -> sys.exit.
    """

    def __init__(self, working_dir='/var/opt/smcrouted', pid_dir="/var/run",
                 umask=0o002, signal_map=None):
        self.working_dir = working_dir
        self.umask = umask
        self.pid_dir = pid_dir
        self.pid_file_path = None
        self.signal_map = signal_map or {signal.SIGTERM: _default_signal_handler}

    def __enter__(self):
        _daemon_fork(self.working_dir, self.umask)
        _register_signals(self.signal_map)
        _redirect_standard_streams()

        # Write PID file
        pid = os.getpid()
        self.pid_file_path = os.path.join(self.pid_dir, f"pygmp-{pid}.pid")
        with open(self.pid_file_path, 'w') as f:
            f.write(str(pid))
        return self

    def __exit__(self, *exc):
        if self.pid_file_path and os.path.exists(self.pid_file_path):
            os.unlink(self.pid_file_path)
        return False


def search_dict_lists(d: dict[Any, list[Any]], key: Any, value: Any) -> int | None:
    """Search a dictionary of lists for an item in the list at key.

    Args:
        d: Dictionary mapping keys to lists.
        key: Key to look up.
        value: Value to search for in the list.

    Returns:
        Index of the value in the list, or None if not found.
    """
    if key in d:
        if value in d[key]:
            return d[key].index(value)
    return None


def _daemon_fork(working_dir: str, umask: int):
    """Follow the double fork pattern to daemonize a process.

    First fork detaches from the parent. ``os.setsid()`` makes the process a
    new session leader. Second fork ensures the daemon cannot reacquire a
    controlling terminal.

    Args:
        working_dir: Directory to chdir into after forking.
        umask: File creation mask.
    """
    try:
        if os.fork() > 0:
            os._exit(0)
    except OSError as err:
        print(f"fork #1 failed: {err}", file=sys.stderr)
        sys.exit(1)

    # Decouple from parent environment
    os.chdir(working_dir)
    os.setsid()
    os.umask(umask)

    # Second fork
    try:
        if os.fork() > 0:
            os._exit(0)
    except OSError as err:
        print(f"fork #2 failed: {err}", file=sys.stderr)
        sys.exit(1)


def _redirect_standard_streams():
    """Redirect stdin, stdout, and stderr to /dev/null.

    This prevents the daemon from holding references to the original
    terminal file descriptors.
    """
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, sys.stdin.fileno())
    os.dup2(devnull, sys.stdout.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    os.close(devnull)


def _default_signal_handler(signum, frame):
    """Default signal handler that performs a clean exit."""
    sys.exit(0)


def _register_signals(signal_map: dict):
    """Register signal handlers.

    Args:
        signal_map: Dictionary mapping signal numbers to handler callables.
    """
    for sig, action in signal_map.items():
        signal.signal(sig, action)
