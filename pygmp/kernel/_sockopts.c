#define PY_SSIZE_T_CLEAN

#include <Python.h>

#include <Python.h>
#include <sys/ioctl.h>
#include <linux/igmp.h>
#include <linux/ip.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <linux/mroute.h>
#include <ifaddrs.h>
#include <net/if.h>
// TODO - whats the difference between mroute and this? #include <netinet/ip_mroute.h>

# include "_sockopts.h"


#define ADDR_BUF_LEN 128  // TODO - is this adequate?


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
