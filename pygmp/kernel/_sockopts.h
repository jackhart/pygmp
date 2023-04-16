//
// Created by jack on 4/14/23.
//

#ifndef PYGMP__SOCKOPTS_H
#define PYGMP__SOCKOPTS_H

#include <Python.h>

PyObject *kernel_add_mfc(PyObject *self, PyObject *args);
PyObject *kernel_del_mfc(PyObject *self, PyObject *args);
PyObject *kernel_add_vif(PyObject* self, PyObject* args, PyObject* kwargs);
PyObject *kernel_del_vif(PyObject *self, PyObject *args);


static PyObject* del_vif(int sockfd, int vifi);
static PyObject* add_vif(int sockfd, int vifi, int thresh, int rate_limit, char *lcl_addr_str, char *rmt_addr_str);
static PyObject *add_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif, PyObject *ttls_list);
static PyObject *del_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif);


#endif //PYGMP__SOCKOPTS_H
