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

import sys
from setuptools import setup, Extension
from pathlib import Path
import sysconfig


def main(args):
    """This is used to build the C extension.  All metadata is in pyproject.toml.  Do not run this directly."""

    python_lib = sysconfig.get_config_var('LDLIBRARY').replace('lib', '').replace('.a', '').replace('.so', '')
    include_dir = sysconfig.get_path('include')
    pygmp_dir = Path.cwd().joinpath("pygmp")

    module1 = Extension('pygmp._kernel',
                        sources=["pygmp/_kernel.c", "pygmp/util.c"],
                        include_dirs=[pygmp_dir, include_dir])

    if "--debug" in args:
        print("Debug mode")
        sys.argv.remove("--debug")
        module1.extra_compile_args = ["-g", "-O0"]
        module1.extra_link_args = ["-g"]

    setup(ext_modules=[module1])


if __name__ == "__main__":
    main(sys.argv)
