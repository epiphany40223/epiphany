//
// To compile:
//
// 1. Compile and install git/pxlib-and-pxview into $bogus
//    MAKE SURE TO USE THE "run" SCRIPT
//    It is important to -I and -L to /opt/local (MacPorts dirs) so
//    that it uses the same base / standard libraries that Python3
//    uses.  Otherwise, you'll get weird Symbol not found errors when
//    trying to "import pds".
//
// 2. ./compile-pdsmodule.py build
//
// 3. sudo ./compile-pdsmodule.pt install
//

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdbool.h>

#include "paradox.h"

static PyObject *PDSError = NULL;
static bool px_booted = false;
static pxdoc_t *pxdoc = NULL;


static PyObject *
pds_open(PyObject *self, PyObject *args)
{
    const char *c_file;

    printf("In PDS open!\n");

    if (!PyArg_ParseTuple(args, "s", &c_file)) {
        return NULL;
    }

    if (!px_booted) {
        PX_boot();
        px_booted = true;
    }

    printf("PDX PX lib: opening %s\n", c_file);
    pxdoc = PX_new();
    PX_open_file(pxdoc, c_file);

    return self;
}

static PyObject *
pds_close(PyObject *self, PyObject *args)
{
    printf("In PDS close!\n");

    if (pxdoc) {
        PX_delete(pxdoc);
        PX_close(pxdoc);
        pxdoc = NULL;
    }

    if (px_booted) {
        PX_shutdown();
        px_booted = false;
    }

    Py_RETURN_NONE;
}

static PyObject *
pds_add_member_email(PyObject *self, PyObject *args)
{
    if (!px_booted) {
        PyErr_SetString(PDSError, "PDS PX lib: not initialized");
        return NULL;
    }
    if (NULL == pxdoc) {
        PyErr_SetString(PDSError, "PDS PX lib: file not opened");
        return NULL;
    }

    int mem_rec_num;
    const char *email_address;
    int preferred;
    if (!PyArg_ParseTuple(args, "isp", &mem_rec_num,
                          &email_address, &preferred)) {
        return NULL;
    }
    printf("Got mem rec num %d, address \"%s\", preferred=%d\n",
           mem_rec_num, email_address, preferred);

    Py_RETURN_NONE;
}


static PyMethodDef PDSMethods[] = {
    {"open", pds_open, METH_VARARGS, "Open a PDS DB file."},
    {"close", pds_close, METH_VARARGS, "Close a PDS DB file."},

    {"add_member_email", pds_add_member_email, METH_VARARGS,
     "Add email address for a member."},

    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef pdsmodule = {
    PyModuleDef_HEAD_INIT,
    "pds",    // name of module
    NULL,     // documentation
    -1,       /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    PDSMethods
};

PyMODINIT_FUNC
PyInit_pds(void)
{
    PyObject *m;

    printf("In the PDS __init__ function\n");

    m = PyModule_Create(&pdsmodule);
    if (m == NULL) {
        return NULL;
    }

    PDSError = PyErr_NewException("pds.error", NULL, NULL);
    Py_INCREF(PDSError);
    PyModule_AddObject(m, "error", PDSError);

    return m;
}
