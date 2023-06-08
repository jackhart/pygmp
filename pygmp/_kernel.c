// MIT License
//
// Copyright (c) 2023 Jack Hart
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

// TODO - IPV6 support

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <linux/igmp.h>
#include <linux/ip.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <linux/mroute.h>
#include <ifaddrs.h>
#include <net/if.h>

#include "_kernel.h"
#include "util.h"



static PyObject *parse_igmp(unsigned char *buffer, size_t len);
static PyObject *parse_igmp_control(unsigned char *buffer, size_t len);
static PyObject *parse_ip_header(unsigned char *buffer, size_t len);
static PyObject *get_network_interfaces(void);
static PyObject *get_network_interface_info(const struct ifaddrs *ifa);
static PyObject* del_vif(int sockfd, int vifi);
static PyObject* add_vif(int sockfd, int vifi, int thresh, int rate_limit, char *lcl_addr_str, char *rmt_addr_str);
static PyObject *add_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif, PyObject *ttls_list);
static PyObject *del_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif);
static PyObject* parse_membership_report(unsigned char *buffer, size_t len);
static PyObject* parse_query(unsigned char *buffer, size_t len);
static PyObject* parse_query_src_list(__be32* src_list, int nsrcs, size_t len);
static PyObject *parse_igmpv3_grec(unsigned char *buffer, size_t len);
static size_t next_igmpv3_grec(unsigned char *buffer);
static PyObject *parse_igmpv3_grec_list(unsigned char *buffer, size_t len);

/*
 * Function:  kernel_add_mfc
 * --------------------
 * Adds a multicast forwarding cache entry to the kernel.
 */
PyObject *kernel_add_mfc(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"sock", "src_str", "grp_str", "parent_vif", "ttls", NULL};

    // TODO - add expire flag
    const char *src_str, *grp_str;
    unsigned int parent_vif;
    PyObject *sock_obj;
    PyObject *ttls_obj;
    struct in_addr src_addr, grp_addr;
    int sockfd;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OssIO", keywords, &sock_obj, &src_str, &grp_str, &parent_vif, &ttls_obj))
        return NULL;

    // Convert source and group addresses from string to binary format
    if (!inet_pton_with_exception(AF_INET, src_str, &src_addr) || !inet_pton_with_exception(AF_INET, grp_str, &grp_addr))
        return NULL;

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    if (!PyList_Check(ttls_obj)) {
        PyErr_SetString(PyExc_TypeError, "Expected a list");
        return NULL;
    }

    // pass to add_mfc
    return add_mfc(sockfd, src_addr, grp_addr, parent_vif, ttls_obj);

}


/*
 * Function:  kernel_del_mfc
 * --------------------
 * Deletes a multicast forwarding cache entry from the kernel.
 */
PyObject *kernel_del_mfc(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"sock", "src_str", "grp_str", "parent_vif", NULL};

    const char *src_str, *grp_str;
    unsigned int parent_vif;
    PyObject *sock_obj;
    struct in_addr src_addr, grp_addr;
    int sockfd;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OssI", keywords, &sock_obj, &src_str, &grp_str, &parent_vif))
        return NULL;

    // Convert source and group addresses from string to binary format
    if (!inet_pton_with_exception(AF_INET, src_str, &src_addr) || !inet_pton_with_exception(AF_INET, grp_str, &grp_addr))
        return NULL;

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    // pass to del_mfc
    return del_mfc(sockfd, src_addr, grp_addr, parent_vif);

}

/*
 * Function:  kernel_add_vif
 * --------------------
 * Adds a multicast virtual interface to the kernel.
 */
PyObject *kernel_add_vif(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char* keywords[] = {"sock", "vifi", "threshold", "rate_limit", "lcl_addr", "rmt_addr", NULL};

    int vifi, thresh, rate_limit, sockfd;
    char* lcl_addr_str = NULL;
    char* rmt_addr_str = NULL;
    PyObject *sock_obj;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oiii|ss", keywords, &sock_obj, &vifi, &thresh, &rate_limit, &lcl_addr_str, &rmt_addr_str))
        return NULL;

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    return add_vif(sockfd, vifi, thresh, rate_limit, lcl_addr_str, rmt_addr_str);
}

/*
 * Function:  kernel_del_vif
 * --------------------
 * Deletes a multicast virtual interface from the kernel.
 */
PyObject *kernel_del_vif(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"sock", "vifi", NULL};

    int vifi, sockfd;
    PyObject *sock_obj;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oi", keywords, &sock_obj, &vifi))
        return NULL;

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    return del_vif(sockfd, vifi);
}


/*
 * Function:  kernel_parse_igmp_control
 * --------------------
 * Parses a control message from the kernel on the multicast routing socket.
 */
PyObject *kernel_parse_igmp_control(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"buffer", NULL};

    char *input;
    Py_ssize_t input_size;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y#", keywords, &input, &input_size))
        return NULL;

    if (input_size < 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid buffer length");
        return NULL;
    }


    return parse_igmp_control((unsigned char *)input, (size_t)input_size);
}

/*
 * Function:  kernel_parse_igmp
 * --------------------
 * Parses an IGMP packet.
 */
PyObject *kernel_parse_igmp(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"buffer", NULL};

    const char *data;
    Py_ssize_t data_len;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y#", keywords, &data, &data_len))
        return NULL;

    if (data_len < 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid buffer length");
        return NULL;
    }

    return parse_igmp((unsigned char *)data, (size_t)data_len);
}

/*
 * Function:  kernel_parse_ip_header
 * --------------------
 * Parses header of an IP packet.
 */
PyObject *kernel_parse_ip_header(PyObject *self, PyObject *args, PyObject* kwargs) {
    static char* keywords[] = {"buffer", NULL};

    char *packet;
    Py_ssize_t packet_len;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "y#", keywords, &packet, &packet_len))
        return NULL;

    if (packet_len < 0) {
        PyErr_SetString(PyExc_ValueError, "Invalid buffer length");
        return NULL;
    }


    return parse_ip_header((unsigned char *)packet, (size_t)packet_len);

}

/*
 * Function:  kernel_parse_ip_header
 * --------------------
 * Get the network interfaces on the system.  These are not the multicast virtual interfaces.
 */
PyObject *kernel_network_interfaces(PyObject *self, PyObject *args)
{
    return get_network_interfaces();
}


static PyObject *parse_igmp(unsigned char *buffer, size_t len) {
    if (len < sizeof(struct igmphdr)) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for igmphdr");
        return NULL;
    }

    struct igmphdr *igmp = (struct igmphdr *) buffer;

    // IGMPv3 membership report
    if (igmp->type == IGMPV3_HOST_MEMBERSHIP_REPORT)
        return parse_membership_report(buffer, len);

    // IGMPv3 membership query
    if ((len > sizeof(struct igmphdr)) && (igmp->type == IGMP_HOST_MEMBERSHIP_QUERY))
        return parse_query(buffer, len);

    // IGMP v2 and v1 messages  -- TODO - different fields by msg type?
    PyObject *result = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(result);

    ADD_ITEM_AND_CHECK(result, "type", PyLong_FromLong(igmp->type));
    ADD_ITEM_AND_CHECK(result, "max_response_time", PyLong_FromLong(igmp->code));
    ADD_ITEM_AND_CHECK(result, "checksum", PyLong_FromLong(ntohs(igmp->csum)));
    ADD_ITEM_AND_CHECK(result, "group", inet_ntop_with_exception(AF_INET, &(igmp->group)));
    return result;
}


static PyObject* parse_membership_report(unsigned char *buffer, size_t len) {
    struct igmpv3_report *report = (struct igmpv3_report *) buffer;

    PyObject *result = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(result);

    ADD_ITEM_AND_CHECK(result, "type", PyLong_FromLong(report->type));
    ADD_ITEM_AND_CHECK(result, "checksum", PyLong_FromLong(ntohs(report->csum)));
    ADD_ITEM_AND_CHECK(result, "num_records", PyLong_FromLong(ntohs(report->ngrec)));

    if ((ntohs(report->ngrec) > 0) ) {
        if (len < sizeof(struct igmpv3_report) + (sizeof(struct igmpv3_grec) * ntohs(report->ngrec))) {
            PyErr_SetString(PyExc_ValueError, "Buffer too short for group records");
            Py_DecRef(result);
            return NULL;
        }
        unsigned char *grec_buffer = buffer + sizeof(struct igmpv3_report);
        ADD_ITEM_AND_CHECK(result, "grec_list", parse_igmpv3_grec_list(grec_buffer, len - sizeof(struct igmpv3_report)));
    } else {
        ADD_ITEM_AND_CHECK(result, "grec_list", Py_None);
    }

    return result;
}


static PyObject* parse_query(unsigned char *buffer, size_t len) {
    if (len < sizeof(struct igmpv3_query)) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for igmpv3_query");
        return NULL;
    }

    struct igmpv3_query *query = (struct igmpv3_query *) buffer;

    PyObject *result = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(result);


    // IGMPv3 Max Resp Time = (mant | 0x10) << (exp + 3)
    unsigned int max_resp_time = query->code;
    if (max_resp_time >= 128) {
        unsigned char exp = max_resp_time >> 5;
        unsigned char mant = max_resp_time & 0x1F;
        max_resp_time = (mant | 0x10) << (exp - 3);
    }

    ADD_ITEM_AND_CHECK(result, "type", PyLong_FromLong(query->type));
    ADD_ITEM_AND_CHECK(result, "max_response_time", PyLong_FromLong(max_resp_time));
    ADD_ITEM_AND_CHECK(result, "checksum", PyLong_FromLong(ntohs(query->csum)));
    ADD_ITEM_AND_CHECK(result, "group", inet_ntop_with_exception(AF_INET, &(query->group)));
    ADD_ITEM_AND_CHECK(result, "qqic", PyLong_FromLong(query->qqic));
    ADD_ITEM_AND_CHECK(result, "suppress", PyBool_FromLong(query->suppress));
    ADD_ITEM_AND_CHECK(result, "querier_robustness", PyLong_FromLong(query->qrv));
    ADD_ITEM_AND_CHECK(result, "querier_query_interval", PyLong_FromLong(query->qqic));
    ADD_ITEM_AND_CHECK(result, "num_sources", PyLong_FromLong(ntohs(query->nsrcs)));
    ADD_ITEM_AND_CHECK(result, "src_list", parse_query_src_list(query->srcs, ntohs(query->nsrcs), len - sizeof(struct igmpv3_query)));

    return result;
}


// Helper function to parse source address list in igmpv3_query
static PyObject* parse_query_src_list(__be32* src_list, int nsrcs, size_t len) {

    if (len < (nsrcs * sizeof(__be32))) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for source list");
        return NULL;
    }

    PyObject* src_list_obj = PyList_New(nsrcs);
    CHECK_NULL_AND_RAISE_NOMEMORY(src_list_obj);

    for (int i = 0; i < nsrcs; i++) {

        PyObject *src_str_obj = inet_ntop_with_exception(AF_INET, &(src_list[i]));
        if (!src_str_obj) {
            Py_DECREF(src_list_obj);
            return NULL;
        }

        if (PyList_SetItem(src_list_obj, i, src_str_obj) == -1) {
            Py_DECREF(src_str_obj);
            Py_DECREF(src_list_obj);
            return NULL;
        }
    }

    return src_list_obj;
}


static PyObject *parse_igmpv3_grec_list(unsigned char *buffer, size_t len) {
    PyObject *grec_list = PyList_New(0);
    if (grec_list == NULL) {
        PyErr_NoMemory();
        return NULL;
    }

    while (len > 0) {
        if (len < sizeof(struct igmpv3_grec)) {
            PyErr_SetString(PyExc_ValueError, "Buffer too short for igmpv3_grec");
            Py_DECREF(grec_list);
            return NULL;
        }

        PyObject *grec_dict = parse_igmpv3_grec(buffer, len);
        if (grec_dict == NULL) {
            Py_DECREF(grec_list);
            return NULL;
        }

        // Add grec_dict to grec_list
        if (PyList_Append(grec_list, grec_dict) == -1) {
            Py_DECREF(grec_list);
            Py_DECREF(grec_dict);
            return NULL;
        }

        Py_DECREF(grec_dict);  // append does not steal the reference.

        size_t grec_size = next_igmpv3_grec(buffer);
        buffer += grec_size;
        len -= grec_size;
    }

    return grec_list;
}


static PyObject *parse_igmpv3_grec(unsigned char *buffer, size_t len) {
    struct igmpv3_grec *grec = (struct igmpv3_grec *) buffer;

    PyObject *grec_dict = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(grec_dict);

    ADD_ITEM_AND_CHECK(grec_dict, "type", PyLong_FromLong(grec->grec_type));
    ADD_ITEM_AND_CHECK(grec_dict, "auxwords", PyLong_FromLong(grec->grec_auxwords));  // should always be 0
    ADD_ITEM_AND_CHECK(grec_dict, "nsrcs", PyLong_FromLong(ntohs(grec->grec_nsrcs)));
    ADD_ITEM_AND_CHECK(grec_dict, "mca", inet_ntop_with_exception(AF_INET, &(grec->grec_mca)));
    ADD_ITEM_AND_CHECK(grec_dict, "src_list", parse_query_src_list(grec->grec_src, ntohs(grec->grec_nsrcs), len - sizeof(struct igmpv3_grec)));

    return grec_dict;
}


static size_t next_igmpv3_grec(unsigned char *buffer) {
    struct igmpv3_grec *grec = (struct igmpv3_grec *) buffer;
    unsigned int nsrcs = ntohs(grec->grec_nsrcs);
    return sizeof(struct igmpv3_grec) + nsrcs * sizeof(__be32);
}


static PyObject *parse_igmp_control(unsigned char *buffer, size_t len) {
    if (len < sizeof(struct igmpmsg)) {
        PyErr_SetString(PyExc_ValueError, "Buffer too short for igmpmsg");
        return NULL;
    }

    struct igmpmsg *igmp = (struct igmpmsg *) buffer;

    // create dictionary to store IP header fields
    PyObject *result_dict = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(result_dict);

    ADD_ITEM_AND_CHECK(result_dict, "msgtype", PyLong_FromLong(igmp->im_msgtype));
    ADD_ITEM_AND_CHECK(result_dict, "mbz", PyLong_FromLong(igmp->im_mbz));
    ADD_ITEM_AND_CHECK(result_dict, "vif", PyLong_FromLong(igmp->im_vif));
    // FIXME - doesn't always exist ADD_ITEM_AND_CHECK(result_dict, "vif_hi", PyLong_FromLong(igmp->im_vif_hi));
    ADD_ITEM_AND_CHECK(result_dict, "im_src", inet_ntop_with_exception(AF_INET, &(igmp->im_src)));
    ADD_ITEM_AND_CHECK(result_dict, "im_dst", inet_ntop_with_exception(AF_INET, &(igmp->im_dst)));

    return result_dict;
}


static PyObject *parse_ip_header(unsigned char *buffer, size_t len) {
    // TODO - support ipv6
    if (len < sizeof(struct iphdr)) {
        PyErr_SetString(PyExc_ValueError, "Packet too short for IP header");
        return NULL;
    }

    struct iphdr *ip_header = (struct iphdr *)buffer;

    // create dictionary to store IP header fields
    PyObject *result_dict = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(result_dict);

    // add IP header fields to dictionary
    ADD_ITEM_AND_CHECK(result_dict, "version", PyLong_FromLong(ip_header->version));
    ADD_ITEM_AND_CHECK(result_dict, "ihl", PyLong_FromLong(ip_header->ihl));
    ADD_ITEM_AND_CHECK(result_dict, "tos", PyLong_FromLong(ip_header->tos));
    ADD_ITEM_AND_CHECK(result_dict, "tot_len", PyLong_FromLong(ntohs(ip_header->tot_len)));
    ADD_ITEM_AND_CHECK(result_dict, "id", PyLong_FromLong(ntohs(ip_header->id)));
    ADD_ITEM_AND_CHECK(result_dict, "frag_off", PyLong_FromLong(ntohs(ip_header->frag_off)));
    ADD_ITEM_AND_CHECK(result_dict, "ttl", PyLong_FromLong(ip_header->ttl));
    ADD_ITEM_AND_CHECK(result_dict, "protocol", PyLong_FromLong(ip_header->protocol));
    ADD_ITEM_AND_CHECK(result_dict, "check", PyLong_FromLong(ntohs(ip_header->check)));
    ADD_ITEM_AND_CHECK(result_dict, "src_addr", inet_ntop_with_exception(AF_INET, &(ip_header->saddr)));
    ADD_ITEM_AND_CHECK(result_dict, "dst_addr", inet_ntop_with_exception(AF_INET, &(ip_header->daddr)));

    return result_dict;
}


static PyObject *get_network_interfaces(void)
{
    struct ifaddrs *ifap, *ifa;
    PyObject *iface_list, *iface_info;

    // get linked list of interfaces
    if (getifaddrs(&ifap) == -1) {
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
        Py_DECREF(iface_info);  // append does not steal the reference
    }

    freeifaddrs(ifap);
    return iface_list;
}

/*
 * Put ifaddrs fields into new dict.  Returns NULL on error and sets exception.
 */
static PyObject *get_network_interface_info(const struct ifaddrs *ifa) {
    PyObject *iface_info;

    // create dictionary to store interface info
    iface_info = PyDict_New();
    CHECK_NULL_AND_RAISE_NOMEMORY(iface_info);

    ADD_ITEM_AND_CHECK(iface_info, "index", PyLong_FromUnsignedLong(if_nametoindex(ifa->ifa_name)));
    ADD_ITEM_AND_CHECK(iface_info, "name", PyUnicode_FromString(ifa->ifa_name));
    ADD_ITEM_AND_CHECK(iface_info, "flags", PyLong_FromUnsignedLong(ifa->ifa_flags));
    ADD_ITEM_AND_CHECK(iface_info, "address", sin_addr_with_exception(ifa));

    return iface_info;
}


static PyObject* del_vif(int sockfd, int vifi) {
    struct vifctl vif;

    memset(&vif, 0, sizeof(vif));
    vif.vifc_vifi = vifi;

    if (setsockopt(sockfd, IPPROTO_IP, MRT_DEL_VIF, &vif, sizeof(vif)) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }
    Py_RETURN_NONE;
}


static PyObject* add_vif(int sockfd, int vifi, int thresh, int rate_limit, char *lcl_addr_str, char *rmt_addr_str) {
    struct vifctl vif;
    struct in_addr lcl_addr, rmt_addr;

    if (inet_pton_with_exception(AF_INET, rmt_addr_str, &rmt_addr) < 0) {
        return NULL;
    }

    memset(&vif, 0, sizeof(vif));
    vif.vifc_vifi = vifi;
    vif.vifc_threshold = thresh;
    vif.vifc_rate_limit = rate_limit;
    vif.vifc_rmt_addr = rmt_addr;

    // check if lcl_addr_str is a valid IP address
    if (inet_pton_with_exception(AF_INET, lcl_addr_str, &lcl_addr) > 0) {
        vif.vifc_lcl_addr.s_addr = lcl_addr.s_addr;
    } else {
        if (!PyErr_ExceptionMatches(PyExc_ValueError)) {
            return NULL;
        }
        // assume lcl_addr_str is an interface index
        PyErr_Clear();
        vif.vifc_lcl_ifindex = atoi(lcl_addr_str);  // FIXME - error handling
        vif.vifc_flags |= VIFF_USE_IFINDEX;
    }

    if (setsockopt(sockfd, IPPROTO_IP, MRT_ADD_VIF, &vif, sizeof(vif)) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    Py_RETURN_NONE;
}


static PyObject *add_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif, PyObject *ttls_list)
{
    struct mfcctl mfc;
    int i;
    PyObject *item;

    // Fill in the multicast forwarding cache control structure
    memset(&mfc, 0, sizeof(mfc));
    mfc.mfcc_origin = src_addr;
    mfc.mfcc_mcastgrp = grp_addr;
    mfc.mfcc_parent = parent_vif;
    if (ttls_list != Py_None) {
        Py_ssize_t list_size = PyList_Size(ttls_list);
        if (list_size < 0) {
            PyErr_SetString(PyExc_TypeError, "Expected a list object for ttls_list");
            return NULL;
        }

        for (i = 0; i < list_size && i < MAXVIFS; i++) {
            item = PyList_GetItem(ttls_list, i);
            if (!item) {
                PyErr_Format(PyExc_IndexError, "Failed to get item at index %d in ttls_list", i);
                return NULL;
            }
            if (!PyLong_Check(item)) {
                PyErr_Format(PyExc_TypeError, "Expected an integer value at index %d in ttls_list", i);
                return NULL;
            }
            mfc.mfcc_ttls[i] = PyLong_AsUnsignedLong(item);
        }
    }

    // Add the multicast forwarding cache entry with the MRT_ADD_MFC flag
    if (setsockopt(sockfd, IPPROTO_IP, MRT_ADD_MFC, &mfc, sizeof(mfc)) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    Py_RETURN_NONE;
}


static PyObject *del_mfc(int sockfd, struct in_addr src_addr, struct in_addr grp_addr, unsigned int parent_vif) {
    struct mfcctl mfc;

    // Fill in the multicast forwarding cache control structure
    memset(&mfc, 0, sizeof(mfc));
    mfc.mfcc_origin = src_addr;
    mfc.mfcc_mcastgrp = grp_addr;
    mfc.mfcc_parent = parent_vif;

    // Delete the multicast forwarding cache entry with the MRT_DEL_MFC flag
    if (setsockopt(sockfd, IPPROTO_IP, MRT_DEL_MFC, &mfc, sizeof(mfc)) < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    Py_RETURN_NONE;
}


// TODO - add metadata for args
static PyMethodDef kernel_methods[] = {
        {"network_interfaces", kernel_network_interfaces, METH_NOARGS, "Get basic info on network interface devices."},
        {"add_mfc", (PyCFunction)kernel_add_mfc, METH_VARARGS | METH_KEYWORDS, "Add a multicast forwarding cache entry."},
        {"del_mfc", (PyCFunction)kernel_del_mfc, METH_VARARGS | METH_KEYWORDS, "Delete a multicast forwarding cache entry."},
        {"add_vif", (PyCFunction)kernel_add_vif, METH_VARARGS | METH_KEYWORDS, "Add a virtual interface to the multicast routing table."},
        {"del_vif", (PyCFunction)kernel_del_vif, METH_VARARGS | METH_KEYWORDS, "Delete a virtual interface from the multicast routing table."},
        {"parse_igmp_control", (PyCFunction)kernel_parse_igmp_control, METH_VARARGS | METH_KEYWORDS, "Parse an IGMP control message."},
        {"parse_ip_header", (PyCFunction)kernel_parse_ip_header, METH_VARARGS | METH_KEYWORDS, "Parse an IP header."},
        {"parse_igmp", (PyCFunction)kernel_parse_igmp, METH_VARARGS | METH_KEYWORDS, "Parse an IGMP message.  Only the payload of the IP packet."},
        {NULL, NULL, 0, NULL}
};


static struct PyModuleDef kernel_module = {
        PyModuleDef_HEAD_INIT,
        "_kernel",
        "C methods for interfacing with the Linux kernel for multicast routing.",
        -1,
        kernel_methods
};


PyMODINIT_FUNC PyInit__kernel(void) {

    PyObject *m = PyModule_Create(&kernel_module);
    if (m == NULL)
        return NULL;

#ifdef  MRT_INIT
    PyModule_AddIntMacro(m, MRT_INIT);   /* Activate the kernel mroute code 	*/
#endif
#ifdef  MRT_DONE
    PyModule_AddIntMacro(m, MRT_DONE);   /* Shutdown the kernel mroute		*/
#endif
#ifdef  MRT_ADD_VIF
    PyModule_AddIntMacro(m, MRT_ADD_VIF);    /* Add a virtual interface		*/
#endif
#ifdef  MRT_DEL_VIF
    PyModule_AddIntMacro(m, MRT_DEL_VIF);    /* Delete a virtual interface		*/
#endif
#ifdef  MRT_ADD_MFC
    PyModule_AddIntMacro(m, MRT_ADD_MFC);    /* Add a multicast forwarding entry	*/
#endif
#ifdef  MRT_DEL_MFC
    PyModule_AddIntMacro(m, MRT_DEL_MFC);    /* Delete a multicast forwarding entry	*/
#endif
#ifdef  MRT_VERSION
    PyModule_AddIntMacro(m, MRT_VERSION);    /* Get the kernel multicast version	*/
#endif
#ifdef  MRT_ASSERT  /* Activate PIM assert mode		*/
    PyModule_AddIntMacro(m, MRT_ASSERT);
#endif
#ifdef  MRT_PIM     /* enable PIM code			*/
    PyModule_AddIntMacro(m, MRT_PIM);
#endif
#ifdef  MRT_TABLE   /* Specify mroute table ID		*/
    PyModule_AddIntMacro(m, MRT_TABLE);
#endif
#ifdef  MRT_ADD_MFC_PROXY   /* Add a (*,*|G) mfc entry	*/
    PyModule_AddIntMacro(m, MRT_ADD_MFC_PROXY);
#endif
#ifdef  MRT_DEL_MFC_PROXY   /* Del a (*,*|G) mfc entry	*/
    PyModule_AddIntMacro(m, MRT_DEL_MFC_PROXY);
#endif
#ifdef  MRT_FLUSH   /* Flush all mfc entries and/or vifs	*/
    PyModule_AddIntMacro(m, MRT_FLUSH);
#endif
#ifdef  MRT_MAX     /* max mrt opt code	*/
    PyModule_AddIntMacro(m, MRT_MAX);
#endif
#ifdef  MRT_FLUSH_MFC   /* Flush multicast entries */
    PyModule_AddIntMacro(m, MRT_FLUSH_MFC);
#endif
#ifdef  MRT_FLUSH_MFC_STATIC   /* Flush static multicast entries */
    PyModule_AddIntMacro(m, MRT_FLUSH_MFC_STATIC);
#endif
#ifdef  MRT_FLUSH_VIFS   /* Flush multicast vifs  */
    PyModule_AddIntMacro(m, MRT_FLUSH_VIFS);
#endif
#ifdef  MRT_FLUSH_VIFS_STATIC   /* Flush static multicast vifs */
    PyModule_AddIntMacro(m, MRT_FLUSH_VIFS_STATIC);
#endif
#ifdef  IGMPMSG_NOCACHE
    PyModule_AddIntMacro(m, IGMPMSG_NOCACHE);    /* Kern cache fill request to mrouted */
#endif
#ifdef  IGMPMSG_WHOLEPKT
    PyModule_AddIntMacro(m, IGMPMSG_WHOLEPKT);   /* For PIM Register processing */
#endif
#ifdef  IGMPMSG_WRVIFWHOLE
    PyModule_AddIntMacro(m, IGMPMSG_WRVIFWHOLE); /* For PIM Register and assert processing */
#endif
#ifdef  VIFF_TUNNEL
    PyModule_AddIntMacro(m, VIFF_TUNNEL); /* Flag if vifctl for IPIP tunnel.  Not supported by FreeBSD. */
#endif
#ifdef  VIFF_SRCRT
    PyModule_AddIntMacro(m, VIFF_SRCRT); /* Flag in vifctl for NI */
#endif
#ifdef  VIFF_REGISTER
    PyModule_AddIntMacro(m, VIFF_REGISTER); /* Flag in vifctl to register VIF */
#endif
#ifdef  VIFF_USE_IFINDEX
    PyModule_AddIntMacro(m, VIFF_USE_IFINDEX); /* Flag if vifctl to use vifc_lcl_ifindex instead of vifc_lcl_addr to find an interface  */
#endif
#ifdef  MAXVIFS
    PyModule_AddIntMacro(m, MAXVIFS); /* Max number of vifs supported by kernel */
#endif
#ifdef  SIOCGETVIFCNT
    PyModule_AddIntMacro(m, SIOCGETVIFCNT);
#endif
#ifdef  SIOCGETSGCNT
    PyModule_AddIntMacro(m, SIOCGETSGCNT);
#endif
#ifdef  SIOCGETRPF
    PyModule_AddIntMacro(m, SIOCGETVIFCNT);
#endif
    return m;
}

#undef CHECK_NULL_AND_RAISE_NOMEMORY
#undef ADD_ITEM_AND_CHECK