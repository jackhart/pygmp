//
// Created by jack on 4/16/23.
//

#ifndef PYGMP__KERNEL_H
#define PYGMP__KERNEL_H


#define ADDR_BUF_LEN 128  // TODO - is this adequate?


PyObject *kernel_parse_igmp_control(PyObject *self, PyObject *args);
PyObject *kernel_parse_ip_header(PyObject *self, PyObject *args);
PyObject *kernel_parse_igmp(PyObject *self, PyObject *args);
PyObject *kernel_network_interfaces(PyObject *self, PyObject *args);
PyObject *kernel_add_mfc(PyObject *self, PyObject *args);
PyObject *kernel_del_mfc(PyObject *self, PyObject *args);
PyObject *kernel_add_vif(PyObject* self, PyObject* args, PyObject* kwargs);
PyObject *kernel_del_vif(PyObject *self, PyObject *args);


static PyObject *parse_igmp(unsigned char *buffer, Py_ssize_t len);
static PyObject *parse_igmp_control(unsigned char *buffer, Py_ssize_t len);
static PyObject *parse_ip_header(unsigned char *buffer, Py_ssize_t len);
static PyObject *get_network_interfaces(void);
static PyObject *get_network_interface_info(const struct ifaddrs *ifa);
static PyObject* get_address(const struct ifaddrs *ifa);
static PyObject* del_vif(int sockfd, int vifi);
static PyObject* add_vif(int sockfd, int vifi, int thresh, int rate_limit, char *lcl_addr_str, char *rmt_addr_str);
static PyObject *add_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif, PyObject *ttls_list);
static PyObject *del_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif);


#endif //PYGMP__KERNEL_H
