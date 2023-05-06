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

#ifndef PYGMP_UTIL_H

int inet_pton_with_exception(int af, const char *src_str, void *dst);
PyObject *sin_addr_with_exception(const struct ifaddrs *ifa);
PyObject *inet_ntop_with_exception(int af, const void *src);


/*
 *  SAFE_DECREF
 *
 *  Given a PyObject pointer, checks that it is not Py_None.
 *  If it is not Py_None, calls Py_DECREF() on it.
 *
 */
#define SAFE_DECREF(obj) do { if ((obj) != Py_None) { Py_DECREF(obj); } } while(0)


/*
 *  ADD_ITEM_AND_CHECK
 *
 *  Given a Python dict object, a key, and a value:
 *   - Checks that the value is not NULL.
 *   - Adds the key and value to the dict.
 *
 *   If either of these operations fail, the dict is decref'd, PyNoMemory is called, and NULL is returned.
 *   If a python error was set before calling this macro, it is not overwritten.
 *
 */
#define ADD_ITEM_AND_CHECK(dict, key, value) do { \
    PyObject *_tmp_value = (value); \
    if (!_tmp_value) { \
        if (!PyErr_Occurred()) { \
            PyErr_NoMemory(); \
        }  \
        SAFE_DECREF(dict); \
        return NULL; \
    } \
    if (PyDict_SetItemString(dict, (key), _tmp_value) < 0) { \
        if (!PyErr_Occurred()) { \
            PyErr_NoMemory(); \
        }  \
        SAFE_DECREF(dict); \
        SAFE_DECREF(_tmp_value); \
        return NULL; \
    } \
    SAFE_DECREF(_tmp_value); \
} while (0)



/*
 *  CHECK_NULL_AND_RAISE_NOMEMORY
 *
 *  Given a PyObject pointer, checks that it is not NULL.
 *  If it is NULL, calls PyErr_NoMemory() and returns NULL.
 *
 *  This macro WILL overwrite any existing Python exception.
 *
 */
#define CHECK_NULL_AND_RAISE_NOMEMORY(value) do { \
    if ((value) == NULL) { \
        PyErr_NoMemory(); \
        return NULL; \
    } \
} while (0)


#define PYGMP_UTIL_H

#endif //PYGMP_UTIL_H
