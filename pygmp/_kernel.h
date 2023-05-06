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

#ifndef PYGMP__KERNEL_H
#define PYGMP__KERNEL_H


PyObject *kernel_parse_igmp_control(PyObject *self, PyObject *args, PyObject* kwargs);
PyObject *kernel_parse_ip_header(PyObject *self, PyObject *args, PyObject* kwargs);
PyObject *kernel_parse_igmp(PyObject *self, PyObject *args, PyObject* kwargs);
PyObject *kernel_network_interfaces(PyObject *self, PyObject *args);
PyObject *kernel_add_mfc(PyObject *self, PyObject *args, PyObject* kwargs);
PyObject *kernel_del_mfc(PyObject *self, PyObject *args, PyObject* kwargs);
PyObject *kernel_add_vif(PyObject* self, PyObject* args, PyObject* kwargs);
PyObject *kernel_del_vif(PyObject *self, PyObject *args, PyObject* kwargs);


#endif //PYGMP__KERNEL_H

