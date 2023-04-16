//
// Created by jack on 4/14/23.
//
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <sys/ioctl.h>
#include <linux/igmp.h>
#include <linux/ip.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <linux/mroute.h>
#include <ifaddrs.h>
#include <net/if.h>

#include "_net.h"


#define ADDR_BUF_LEN 128  // TODO - is this adequate?


PyObject *kernel_parse_igmp_control(PyObject *self, PyObject *args) {
    char *input;
    Py_ssize_t input_size;

    // Parse input arguments
    if (!PyArg_ParseTuple(args, "y#", &input, &input_size)) {
        return NULL;
    }

    // Call parse_igmp with the input buffer
    return parse_igmp_control((unsigned char *)input, input_size);
}


PyObject *kernel_parse_igmp(PyObject *self, PyObject *args) {
    const char *data;
    Py_ssize_t data_len;

    if (!PyArg_ParseTuple(args, "y#", &data, &data_len)) {
        return NULL;
    }

    return parse_igmp((unsigned char *)data, data_len);
}


PyObject *kernel_parse_ip_header(PyObject *self, PyObject *args) {
    char *packet;
    Py_ssize_t packet_len;

    if (!PyArg_ParseTuple(args, "y#", &packet, &packet_len)) {
        return NULL;
    }

    return parse_ip_header((unsigned char *)packet, packet_len);

}


PyObject *kernel_network_interfaces(PyObject *self, PyObject *args)
{
    return get_network_interfaces();
}


static PyObject *parse_igmp(unsigned char *buffer, Py_ssize_t len) {
    // TODO - support ipv6
    if (len < sizeof(struct igmphdr)) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for igmphdr");
        return NULL;
    }

    struct igmphdr *igmp = (struct igmphdr *) buffer;

    // Create a Python dictionary to store the fields
    PyObject *result = PyDict_New();
    if (result == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    char group_str[ADDR_BUF_LEN];
    inet_ntop(AF_INET, &(igmp->group), group_str, ADDR_BUF_LEN);

    // Add the fields to the dictionary
    PyDict_SetItemString(result, "type", PyLong_FromLong(igmp->type));
    PyDict_SetItemString(result, "code", PyLong_FromLong(igmp->code));
    PyDict_SetItemString(result, "checksum", PyLong_FromLong(ntohs(igmp->csum)));
    PyDict_SetItemString(result, "group", PyUnicode_FromString(group_str));

    return result;
}


static PyObject *parse_igmp_control(unsigned char *buffer, Py_ssize_t len) {
    // TODO - support ipv6
    if (len < sizeof(struct igmpmsg)) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for igmpmsg");
        return NULL;
    }

    struct igmpmsg *igmp = (struct igmpmsg *) buffer;

    // create dictionary to store IP header fields
    PyObject *result_dict = PyDict_New();
    if (result_dict == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    // convert address fields to string representations
    char src_addr_str[ADDR_BUF_LEN];
    char dst_addr_str[ADDR_BUF_LEN];
    inet_ntop(AF_INET, &(igmp->im_src), src_addr_str, ADDR_BUF_LEN);
    inet_ntop(AF_INET, &(igmp->im_dst), dst_addr_str, ADDR_BUF_LEN);

    // add IP header fields to dictionary
    PyDict_SetItemString(result_dict, "msgtype", PyLong_FromLong(igmp->im_msgtype));
    PyDict_SetItemString(result_dict, "mbz", PyLong_FromLong(igmp->im_mbz));
    PyDict_SetItemString(result_dict, "vif", PyLong_FromLong(igmp->im_vif));
    PyDict_SetItemString(result_dict, "vif_hi", PyLong_FromLong(igmp->im_vif_hi));
    PyDict_SetItemString(result_dict, "im_src", PyUnicode_FromString(src_addr_str));
    PyDict_SetItemString(result_dict, "im_dst", PyUnicode_FromString(dst_addr_str));

    // return result dictionary
    return result_dict;
}


static PyObject *parse_ip_header(unsigned char *buffer, Py_ssize_t len) {
    // TODO - support ipv6
    if (len < sizeof(struct iphdr)) {
        PyErr_SetString(PyExc_ValueError, "Packet too short for IP header");
        return NULL;
    }

    struct iphdr *ip_header = (struct iphdr *)buffer;

    // create dictionary to store IP header fields
    PyObject *result_dict = PyDict_New();
    if (result_dict == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    // convert address fields to string representations
    char src_addr_str[ADDR_BUF_LEN];
    char dst_addr_str[ADDR_BUF_LEN];
    inet_ntop(AF_INET, &(ip_header->saddr), src_addr_str, ADDR_BUF_LEN);
    inet_ntop(AF_INET, &(ip_header->daddr), dst_addr_str, ADDR_BUF_LEN);

    // add IP header fields to dictionary
    PyDict_SetItemString(result_dict, "version", PyLong_FromLong(ip_header->version));
    PyDict_SetItemString(result_dict, "ihl", PyLong_FromLong(ip_header->ihl));
    PyDict_SetItemString(result_dict, "tos", PyLong_FromLong(ip_header->tos));
    PyDict_SetItemString(result_dict, "tot_len", PyLong_FromLong(ntohs(ip_header->tot_len)));
    PyDict_SetItemString(result_dict, "id", PyLong_FromLong(ntohs(ip_header->id)));
    PyDict_SetItemString(result_dict, "frag_off", PyLong_FromLong(ntohs(ip_header->frag_off)));
    PyDict_SetItemString(result_dict, "ttl", PyLong_FromLong(ip_header->ttl));
    PyDict_SetItemString(result_dict, "protocol", PyLong_FromLong(ip_header->protocol));
    PyDict_SetItemString(result_dict, "check", PyLong_FromLong(ntohs(ip_header->check)));
    PyDict_SetItemString(result_dict, "src_addr", PyUnicode_FromString(src_addr_str));
    PyDict_SetItemString(result_dict, "dst_addr", PyUnicode_FromString(dst_addr_str));

    // return result dictionary
    return result_dict;
}


static PyObject *get_network_interfaces(void)
{
    struct ifaddrs *ifap, *ifa;
    PyObject *iface_list, *iface_info;
    int ret;

    // get linked list of interfaces
    ret = getifaddrs(&ifap);
    if (ret == -1) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    // create python list to store interface info
    iface_list = PyList_New(0);
    if (iface_list == NULL) {
        freeifaddrs(ifap);
        PyErr_NoMemory();
        return NULL;
    }

    // iterate through interfaces
    for (ifa = ifap; ifa != NULL; ifa = ifa->ifa_next) {
        // skip interfaces without addresses
        if (ifa->ifa_addr == NULL) {
            continue;
        }

        // create dict with interface info
        iface_info = get_network_interface_info(ifa);
        if (iface_info == NULL) {
            Py_DECREF(iface_list);
            freeifaddrs(ifap);
            return NULL;
        }

        // append to the list
        if (PyList_Append(iface_list, iface_info) != 0) {
            Py_DECREF(iface_list);
            Py_DECREF(iface_info);
            freeifaddrs(ifap);
            PyErr_NoMemory();
            return NULL;
        }
        Py_DECREF(iface_info);
    }

    freeifaddrs(ifap);
    return iface_list;
}


static PyObject *get_network_interface_info(const struct ifaddrs *ifa) {
    PyObject *iface_info;

    // create dictionary to store interface info
    iface_info = PyDict_New();
    if (iface_info == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    // TODO - edge case when ifa_name or flags are null?
    PyDict_SetItemString(iface_info, "name", PyUnicode_FromString(ifa->ifa_name));
    PyDict_SetItemString(iface_info, "index", PyLong_FromUnsignedLong(if_nametoindex(ifa->ifa_name)));
    PyDict_SetItemString(iface_info, "flags", PyLong_FromUnsignedLong(ifa->ifa_flags));
    PyDict_SetItemString(iface_info, "address", get_address(ifa));

    return iface_info;
}


static PyObject* get_address(const struct ifaddrs *ifa) {
    char addr_buf[ADDR_BUF_LEN] = {0};
    int family = ifa->ifa_addr->sa_family;
    if (family == AF_INET || family == AF_INET6) {
        // get address string
        if (family == AF_INET) {
            inet_ntop(family, &(((struct sockaddr_in *) ifa->ifa_addr)->sin_addr), addr_buf, INET_ADDRSTRLEN);
        } else {
            inet_ntop(family, &(((struct sockaddr_in6 *) ifa->ifa_addr)->sin6_addr), addr_buf, INET6_ADDRSTRLEN);
        }
    }
    return PyUnicode_FromString(addr_buf);
}
