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
import tempfile
import sys


def get_logger(name) -> logging.Logger:
    """Assures that the logger is configured."""
    logging.config.fileConfig(fname=Path(inspect.getfile(pygmp)).parent.joinpath("log_config.ini"))
    return logging.getLogger(name)


class DaemonContext(contextlib.ContextDecorator):
    def __init__(self, working_dir='/var/opt/smcrouted', pid_dir="/var/run", umask=0o002):
        self.working_dir = working_dir
        self.umask = umask
        self.pid_dir = pid_dir
        self.pid_file = None

    def __enter__(self):
        _daemon_fork(self.working_dir, self.umask)
        self.pid_file = tempfile.NamedTemporaryFile(dir=self.pid_dir, suffix=".pid", delete=False)
        self.pid_file.write(bytes(os.getpid()))
        return self

    def __exit__(self, *exc):
        self.pid_file.close()
        return False


def search_dict_lists(d: dict[Any, list[Any]], key: Any, value: Any) -> int | None:
    """Searches a dictionary of lists for an item in list of key. Returns index of item if found, else None."""
    if key in d:
        if value in d[key]:
            return d[key].index(value)
    return None


def _daemon_fork(working_dir: str, umask: int):
    """Follow the double fork pattern to daemonize a process."""
    try:
        if os.fork() > 0:
            exit(0)
    except OSError as err:
        print(f"fork #1 failed: {err}", file=sys.stderr)
        exit(1)

    # decouple from parent environment
    # TODO - additional steps (e.g., close file descriptors, set uid and gid, etc.)
    os.chdir(working_dir)
    os.setsid()  # process becomes new session and process group leader + no controlling terminal
    os.umask(umask)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            exit(0)
    except OSError as err:
        print(f"fork #2 failed: {err}", file=sys.stderr)
        exit(1)


def _register_signals(signal_map: dict):
    """Register signal handlers."""
    for sig, action in signal_map.items():
        signal.signal(sig, action)

