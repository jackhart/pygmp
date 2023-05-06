
CC = gcc
EXTENSION_NAME = _kernel
CFLAGS = -DNDEBUG -g -O3 -Wall -Wstrict-prototypes -fPIC -DMAJOR_VERSION=1 -DMINOR_VERSION=0 -I/usr/local/include -I/usr/include/python3.10
.PHONY: all clean


all: $(EXTENSION_NAME).so

util.o: util.c util.h
	$(CC) $(CFLAGS) -c util.c -o util.o

$(EXTENSION_NAME).o: $(EXTENSION_NAME).c util.h
	$(CC) $(CFLAGS) -c $(EXTENSION_NAME).c -o $(EXTENSION_NAME).o

$(EXTENSION_NAME).so: $(EXTENSION_NAME).o util.o
	gcc -shared $(EXTENSION_NAME).o util.o -L/usr/local/lib -lpython3.10 -o $(EXTENSION_NAME).so


clean:
	rm -f $(EXTENSION_NAME).so $(EXTENSION_NAME).o