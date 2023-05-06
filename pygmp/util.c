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

#include <Python.h>
#include <arpa/inet.h>
#include <ifaddrs.h>

#include "util.h"


/*
 * Function:  inet_ntop_with_exception
 * -----------------------------------
 *
 * Wrapper for inet_ntop that raises a Python exception if the address is invalid.
 *
 * inet_ntop() converts a network format address (usually a struct in_addr or some other internal binary representation,
 * in network byte order) into a presentation format string suitable for printing.
 *
 */
PyObject *inet_ntop_with_exception(int af, const void *src) {
    PyObject *result;

    if (af == AF_INET) {
        char mca_str[INET_ADDRSTRLEN];
        if (inet_ntop(af, src, mca_str, INET_ADDRSTRLEN) == NULL) {
            PyErr_SetFromErrno(PyExc_OSError);
            return NULL;
        }
        result = PyUnicode_FromString(mca_str);
        CHECK_NULL_AND_RAISE_NOMEMORY(result);
        return result;
    }

    char mca_str[INET6_ADDRSTRLEN];
    if (inet_ntop(af, src, mca_str, INET6_ADDRSTRLEN) == NULL) {
        PyErr_SetFromErrno(PyExc_OSError);
        return NULL;
    }

    result = PyUnicode_FromString(mca_str);
    CHECK_NULL_AND_RAISE_NOMEMORY(result);
    return result;
}


/*
 * Function:  sin_addr_with_exception
 * ----------------------------------
 *
 * Extracts readable IP address from ifaddrs struct returneed by getifaddrs.
 * Sets Python exception on failure.
 *
 */
PyObject *sin_addr_with_exception(const struct ifaddrs *ifa) {
    int family = ifa->ifa_addr->sa_family;
    if (family == AF_INET)
        return inet_ntop_with_exception(family, &(((struct sockaddr_in *) ifa->ifa_addr)->sin_addr));
    if (family == AF_INET6)
        return inet_ntop_with_exception(family, &(((struct sockaddr_in6 *) ifa->ifa_addr)->sin6_addr));

    PyErr_SetString(PyExc_ValueError, "Invalid address format");
    return NULL;
}


/*
 * Function:  inet_pton_with_exception
 * -----------------------------------
 *
 * Wrapper for inet_pton that raises a Python exception if the address is invalid.
 *
 * inet_pton() converts a presentation format address (that is, printable form as held in a character string)
 * into network format (usually a struct in_addr or some other internal binary representation, in network byte order).
 *
 */
int inet_pton_with_exception(int af, const char *src_str, void *dst) {
    int result = inet_pton(af, src_str, dst);
    if (result <= 0) {
        if (result == 0) {
            PyErr_SetString(PyExc_ValueError, "Invalid address format");
        } else {
            PyErr_SetFromErrno(PyExc_OSError);
        }
        return 0;
    }
    return 1;
}