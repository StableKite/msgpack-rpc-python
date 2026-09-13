#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject* websocket_mask(PyObject* self, PyObject* args) {
    const char* mask;
    Py_ssize_t mask_len;
    const char* data;
    Py_ssize_t data_len;
    Py_ssize_t i;
    PyObject* result;
    char* buf;

    if (!PyArg_ParseTuple(args, "y#y#", &mask, &mask_len, &data, &data_len)) {
        return NULL;
    }

    if (mask_len != 4) {
        PyErr_SetString(PyExc_ValueError, "websocket mask must be exactly 4 bytes");
        return NULL;
    }

    result = PyBytes_FromStringAndSize(NULL, data_len);
    if (!result) {
        return NULL;
    }
    buf = PyBytes_AsString(result);
    for (i = 0; i < data_len; i++) {
        buf[i] = data[i] ^ mask[i % 4];
    }

    return result;
}

static PyMethodDef methods[] = {
    {"websocket_mask",  websocket_mask, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}
};

#if PY_MAJOR_VERSION >= 3
#if PY_VERSION_HEX >= 0x030D0000
static struct PyModuleDef_Slot speedups_slots[] = {
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
    {0, NULL}
};

static struct PyModuleDef speedupsmodule = {
   PyModuleDef_HEAD_INIT,
   "speedups",
   NULL,
   0,
   methods,
   speedups_slots,
   NULL,
   NULL,
   NULL
};

PyMODINIT_FUNC
PyInit_speedups(void) {
    return PyModuleDef_Init(&speedupsmodule);
}
#else
static struct PyModuleDef speedupsmodule = {
   PyModuleDef_HEAD_INIT,
   "speedups",
   NULL,
   -1,
   methods
};

PyMODINIT_FUNC
PyInit_speedups(void) {
    return PyModule_Create(&speedupsmodule);
}
#endif
#else  // Python 2.x
PyMODINIT_FUNC
initspeedups(void) {
    Py_InitModule("tornado.speedups", methods);
}
#endif
