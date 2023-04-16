from setuptools import setup, Extension


def main():
    module1 = Extension('pygmp.kernel._kernel',
                        sources=["./pygmp/kernel/_kernel.c", "./pygmp/kernel/_net.c", "./pygmp/kernel/_sockopts.c"],
                        include_dirs=["/home/jack/Documents/projects/pygmp/pygmp/kernel/"],
                        libraries=["python3.10"])


    setup(name="pygmp",
          packages=['pygmp'],
          version="1.0.0",
          description="Python tools for working with the Multicast Routing Table in Linux.",
          author="Jack Hart",
          author_email="jackhart0508@gmail.com",
          ext_modules=[module1])


if __name__ == "__main__":
    main()
