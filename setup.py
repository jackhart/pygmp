from setuptools import setup, Extension
from pathlib import Path

def main():
    module1 = Extension('pygmp._kernel',
                        sources=["./pygmp/_kernel.c"],
                        include_dirs=[Path.cwd().joinpath("pygmp")],
                        libraries=["python3.10"])

    setup(ext_modules=[module1])

if __name__ == "__main__":
    main()
