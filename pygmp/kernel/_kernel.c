//
// Created by jack on 4/14/23.
//
// TODO - cleanup method signatures
// TODO - improve error handling.  I'm skipping over a lot of potential errors.
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

// TODO - whats the difference between mroute and this? #include <netinet/ip_mroute.h>



PyObject *kernel_add_mfc(PyObject *self, PyObject *args) {
    // TODO - add expire flag
    const char *src_str, *grp_str;
    unsigned int parent_vif;
    PyObject *sock_obj;
    PyObject *ttls_obj;
    struct in_addr src_addr, grp_addr;
    int sockfd;

    // Parse input arguments
    if (!PyArg_ParseTuple(args, "OssIO", &sock_obj, &src_str, &grp_str,
                          &parent_vif, &ttls_obj))
        return NULL;

    // Convert source and group addresses from string to binary format
    if (!inet_aton(src_str, &src_addr) || !inet_aton(grp_str, &grp_addr)) {
        PyErr_SetString(PyExc_ValueError, "Invalid address format");
        return NULL;
    }

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


PyObject *kernel_del_mfc(PyObject *self, PyObject *args) {
    const char *src_str, *grp_str;
    unsigned int parent_vif;
    PyObject *sock_obj;
    struct in_addr src_addr, grp_addr;
    int sockfd;

    // Parse input arguments
    if (!PyArg_ParseTuple(args, "OssI", &sock_obj, &src_str, &grp_str, &parent_vif))
        return NULL;

    // Convert source and group addresses from string to binary format
    if (!inet_aton(src_str, &src_addr) || !inet_aton(grp_str, &grp_addr)) {
        PyErr_SetString(PyExc_ValueError, "Invalid address format");
        return NULL;
    }

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    // pass to del_mfc
    return del_mfc(sockfd, src_addr, grp_addr, parent_vif);

}


PyObject *kernel_add_vif(PyObject* self, PyObject* args, PyObject* kwargs) {
    static char* keywords[] = {"sock", "vifi", "threshold", "rate_limit", "lcl_addr", "rmt_addr", NULL};

    int vifi, thresh, rate_limit, sockfd;
    char* lcl_addr_str = NULL;
    char* rmt_addr_str = NULL;
    PyObject *sock_obj;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Oiii|ss", keywords, &sock_obj, &vifi, &thresh, &rate_limit, &lcl_addr_str, &rmt_addr_str)) {
        return NULL;
    }

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    return add_vif(sockfd, vifi, thresh, rate_limit, lcl_addr_str, rmt_addr_str);
}


PyObject *kernel_del_vif(PyObject *self, PyObject *args) {
    int vifi, sockfd;
    PyObject *sock_obj;

    if (!PyArg_ParseTuple(args, "Oi", &sock_obj, &vifi)) {
        return NULL;
    }

    sockfd = PyObject_AsFileDescriptor(sock_obj);
    if (sockfd < 0) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    return del_vif(sockfd, vifi);
}



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

    // set rmt_addr
    inet_aton(rmt_addr_str, &rmt_addr);

    memset(&vif, 0, sizeof(vif));
    vif.vifc_vifi = vifi;
    vif.vifc_threshold = thresh;
    vif.vifc_rate_limit = rate_limit;
    vif.vifc_rmt_addr = rmt_addr;

    // check if lcl_addr_str is a valid IP address
    if (inet_pton(AF_INET, lcl_addr_str, &lcl_addr) > 0) {
        vif.vifc_lcl_addr.s_addr = lcl_addr.s_addr;
    } else {
        // assume lcl_addr_str is an interface index
        vif.vifc_lcl_ifindex = atoi(lcl_addr_str);
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

    // Fill in the multicast forwarding cache control structure
    memset(&mfc, 0, sizeof(mfc));
    mfc.mfcc_origin = src_addr;
    mfc.mfcc_mcastgrp = grp_addr;
    mfc.mfcc_parent = parent_vif;
    if (ttls_list != Py_None) {
        for (i = 0; i < PyList_Size(ttls_list) && i < MAXVIFS; i++) {
            mfc.mfcc_ttls[i] = PyLong_AsUnsignedLong(PyList_GetItem(ttls_list, i));
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
        {"add_mfc", kernel_add_mfc, METH_VARARGS, "Add a multicast forwarding cache entry."},
        {"del_mfc", kernel_del_mfc, METH_VARARGS, "Delete a multicast forwarding cache entry."},
        {"add_vif", (PyCFunction)kernel_add_vif, METH_VARARGS | METH_KEYWORDS, "Add a virtual interface to the multicast routing table."},
        {"del_vif", kernel_del_vif, METH_VARARGS, "Delete a virtual interface from the multicast routing table."},
        {"parse_igmp_control", kernel_parse_igmp_control, METH_VARARGS, "Parse an IGMP control message."},
        {"parse_ip_header", kernel_parse_ip_header, METH_VARARGS, "Parse an IP header."},
        {"parse_igmp", kernel_parse_igmp, METH_VARARGS, "Parse an IGMP message.  Only the payload of the IP packet."},
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