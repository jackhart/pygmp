//
// Created by jack on 4/14/23.
//

#ifndef PYGMP__NET_H
#define PYGMP__NET_H

#include <Python.h>

PyObject *kernel_parse_igmp_control(PyObject *self, PyObject *args);
PyObject *kernel_parse_ip_header(PyObject *self, PyObject *args);
PyObject *kernel_parse_igmp(PyObject *self, PyObject *args);
PyObject *kernel_network_interfaces(PyObject *self, PyObject *args);


static PyObject *parse_igmp(unsigned char *buffer, Py_ssize_t len);
static PyObject *parse_igmp_control(unsigned char *buffer, Py_ssize_t len);
static PyObject *parse_ip_header(unsigned char *buffer, Py_ssize_t len);
static PyObject *get_network_interfaces(void);
static PyObject *get_network_interface_info(const struct ifaddrs *ifa);
static PyObject* get_address(const struct ifaddrs *ifa);

#endif //PYGMP__NET_H
