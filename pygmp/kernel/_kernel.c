//
// Created by jack on 4/14/23.
//
// TODO - cleanup method signatures
// TODO - improve error handling.  I'm skipping over a lot of potential errors.
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <linux/mroute.h>

#include "_sockopts.h"
#include "_net.h"


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