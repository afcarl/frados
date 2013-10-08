/*
  wavcorr.c
*/

#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

inline int min(int x, int y) { return (x < y)? x : y; }
inline int max(int x, int y) { return (x < y)? y : x; }
inline double hann(int i, int n) { return (1.0-cos(2.0*M_PI*i/n))/2.0; }


/* calcsims16: compute the similarity between two vectors. */
double calcsims16(int n, const short* seq1, const short* seq2)
{
    int i;
    double s1 = 0, s2 = 0;
    double t1 = 0, t2 = 0;
    double dot = 0;
    for (i = 0; i < n; i++) {
	double x1 = seq1[i]/32768.0;
	double x2 = seq2[i]/32768.0;
	s1 += x1;
	s2 += x2;
	t1 += x1*x1;
	t2 += x2*x2;
	dot += x1*x2;
    }
    // sum((x1-s1/n)*(x2-s2/n))
    //  = sum(x1*x2 - (s1*x2+s2*x1)/n + s1*s2/n/n)
    //  = sum(x1*x2) - (s1*sum(x2) + s2*sum(x1))/n + s1*s2/n/n*sum(1)
    //  = dot - 2*s1*s2/n + s1*s2/n = dot - s1*s2/n
    double v = (n*t1-s1*s1) * (n*t2-s2*s2);
    return (v == 0)? 0 : ((n*dot-s1*s2) / sqrt(v));
}

/* calcisf16: compute the intensity of samples. */
double calcisf16(int length, const short* seq)
{
    int i;
    double f = 0;
    for (i = 0; i < length; i++) {
	double x = seq[i]/32768.0;
	f += x*x;
    }
    return (length == 0)? 0 : sqrt(f)/length;
}

/* autocorrs16: find the window that has the maximum similarity. */
int autocorrs16(double* sim, int window0, int window1, int length, const short* seq)
{
    /* assert(window0 <= window1); */

    int w;
    for (w = window0; w <= window1; w++) {
	sim[w-window0] = 0;
    }
  
    /* Enhanced Auto Correlation:
       The idea is taken from Tolonen and Karjalainen, 2000,
       "A Computationally Efficient Multipitch Analysis Model"
       IEEE Transactions on Speech and Audio Processing, 
       Vol. 8, No. 6, Nov. 2000
    */
    for (w = window0; w <= window1; w++) {
	int w1 = window1 - (window1%w);
	if (w1+w <= length) {
	    double s = calcsims16(w1, seq, seq+w);
	    s += sim[w-window0];
	    s = (0 < s)? s : 0;
	    sim[w-window0] = s;
	    /* remove overlapping freq. */
	    int i2 = w*2-window0;
	    if (i2+1 <= window1-window0) {
		sim[i2] -= s;
		sim[i2+1] -= s;
	    }
	}
    }

    /* find the maximum similarity. */
    int wmax = -1;
    double smax = -1;
    for (w = window0; w <= window1; w++) {
	double s = sim[w-window0];
	if (smax < s) {
	    smax = s;
	    wmax = w;
	}
    }
  
    return wmax;
}

/* autosplices16: find the window that has the maximum similarity. */
int autosplices16(double* psim, int window0, int window1, 
		  int length1, const short* seq1, 
		  int length2, const short* seq2)
{
    if (window1 < window0) {
	int x = window1;
	window1 = window0;
	window0 = x;
    }
    /* assert(window0 <= window1); */
  
    int wmax = 0;
    double smax = -1;
    int w;
    for (w = window0; w <= window1; w++) {
	if (w <= length1 && w <= length2) {
	    double s = calcsims16(w, seq1+length1-w, seq2);
	    if (smax < s) {
		wmax = w;
		smax = s;
	    }
	}
    }
  
    *psim = smax;
    return wmax;
}

/* psolas16: overlap-add two vectors. */
void psolas16(int outlen, short* out, 
	      int length1, const short* seq1, 
	      int length2, const short* seq2)
{
    int i;

    for (i = 0; i < outlen; i++) {
	/* i < outlen ==> i*length/outlen < length */
	double v = 0;
	if (0 < length1) {
	    /* first half (decreasing) */
	    v += seq1[i*length1/outlen] * hann(i+outlen, outlen*2);
	}
	if (0 < length2) {
	    /* second half (increasing) */
	    v += seq2[i*length2/outlen] * hann(i, outlen*2);
	}
	out[i] = (short)v;
    }
}


/*  Python functions
 */

/* pycalcsims16(window, data1, offset1, data2, offset2); */
static PyObject* pycalcsims16(PyObject* self, PyObject* args)
{
    int window;
    PyObject* data1;
    PyObject* data2;
    int offset1;
    int offset2;

    if (!PyArg_ParseTuple(args, "iOiOi", &window, 
			  &data1, &offset1, &data2, &offset2)) {
	return NULL;
    }

    if (!PyString_CheckExact(data1) ||
	!PyString_CheckExact(data2)) {
	PyErr_SetString(PyExc_TypeError, "Must be string");
	return NULL;
    }

    int length1 = PyString_Size(data1) / sizeof(short);
    int length2 = PyString_Size(data2) / sizeof(short);
    if (window < 0 ||
	offset1 < 0 || length1 < offset1+window ||
	offset2 < 0 || length2 < offset2+window) {
	PyErr_SetString(PyExc_ValueError, "Invalid offset/window");
	return NULL;
    }

    short* seq1 = (short*)PyString_AsString(data1);
    short* seq2 = (short*)PyString_AsString(data2);
    double sim = calcsims16(window, &seq1[offset1], &seq2[offset2]);

    return PyFloat_FromDouble(sim);
}


/* pycalcisf16(data, offset, window); */
static PyObject* pycalcisf16(PyObject* self, PyObject* args)
{
    PyObject* data;
    int offset;
    int window;

    if (!PyArg_ParseTuple(args, "Oii", &data, &offset, &window)) {
	return NULL;
    }

    if (!PyString_CheckExact(data)) {
	PyErr_SetString(PyExc_TypeError, "Must be string");
	return NULL;
    }

    int length = PyString_Size(data) / sizeof(short);
    if (window < 0 ||
	offset < 0 || length < offset+window) {
	PyErr_SetString(PyExc_ValueError, "Invalid offset/window");
	return NULL;
    }

    short* seq = (short*)PyString_AsString(data);
    double isf = calcisf16(window, &seq[offset]);

    return PyFloat_FromDouble(isf);
}


/* pyautocorrs16(window0, window1, data, offset); */
static PyObject* pyautocorrs16(PyObject* self, PyObject* args)
{
    int window0, window1;
    PyObject* data;
    int offset;

    if (!PyArg_ParseTuple(args, "iiOi", &window0, &window1, &data, &offset)) {
	return NULL;
    }

    if (!PyString_CheckExact(data)) {
	PyErr_SetString(PyExc_TypeError, "Must be string");
	return NULL;
    }

    int length = PyString_Size(data) / sizeof(short);
    if (window0 < 0 || window1 < 0 || 
	offset < 0 || length < offset+window0 || length < offset+window1) {
	PyErr_SetString(PyExc_ValueError, "Invalid offset/window");
	return NULL;
    }

    if (window1 < window0) {
	int x = window1;
	window1 = window0;
	window0 = x;
    }
    double* sim = (double*) PyMem_Malloc(sizeof(double)*(window1-window0+1));
    if (sim == NULL) return PyErr_NoMemory();
    short* seq = (short*)PyString_AsString(data);
    int wmax = autocorrs16(sim, window0, window1, length-offset, &seq[offset]);
    double smax = sim[wmax-window0];
    PyMem_Free(sim);
  
    PyObject* tuple;
    {
	PyObject* v1 = PyInt_FromLong(wmax);
	PyObject* v2 = PyFloat_FromDouble(smax);
	tuple = PyTuple_Pack(2, v1, v2);
	Py_DECREF(v1);
	Py_DECREF(v2);
    }

    return tuple;
}


/* pyautosplices16(window0, window1, data1, data2); */
static PyObject* pyautosplices16(PyObject* self, PyObject* args)
{
    int window0, window1;
    PyObject* data1;
    PyObject* data2;

    if (!PyArg_ParseTuple(args, "iiOO", &window0, &window1, &data1, &data2)) {
	return NULL;
    }

    if (!PyString_CheckExact(data1) ||
	!PyString_CheckExact(data2)) {
	PyErr_SetString(PyExc_TypeError, "Must be string");
	return NULL;
    }

    int length1 = PyString_Size(data1) / sizeof(short);
    int length2 = PyString_Size(data2) / sizeof(short);
    if (window0 < 0 || window1 < 0 ||
	length1 < window0 || length1 < window1 ||
	length2 < window0 || length2 < window1) {
	PyErr_SetString(PyExc_ValueError, "Invalid offset/window");
	return NULL;
    }

    short* seq1 = (short*)PyString_AsString(data1);
    short* seq2 = (short*)PyString_AsString(data2);  
    double smax = 0;
    int wmax = autosplices16(&smax, window0, window1, length1, seq1, length2, seq2);
  
    PyObject* tuple;
    {
	PyObject* v1 = PyInt_FromLong(wmax);
	PyObject* v2 = PyFloat_FromDouble(smax);
	tuple = PyTuple_Pack(2, v1, v2);
	Py_DECREF(v1);
	Py_DECREF(v2);
    }
    return tuple;
}


/* pypsolas16(outlen, 
   offset1, window1, data1,
   offset2, window2, data2); */
static PyObject* pypsolas16(PyObject* self, PyObject* args)
{
    int outlen;
    int offset1, offset2;
    int window1, window2;
    PyObject* data1;
    PyObject* data2;

    if (!PyArg_ParseTuple(args, "iiiOiiO", &outlen,
			  &offset1, &window1, &data1,
			  &offset2, &window2, &data2)) {
	return NULL;
    }
  
    if (!PyString_CheckExact(data1) ||
	!PyString_CheckExact(data2)) {
	PyErr_SetString(PyExc_TypeError, "Must be string");
	return NULL;
    }

    int length1 = PyString_Size(data1) / sizeof(short);
    int length2 = PyString_Size(data2) / sizeof(short);
    if (window1 < 0 || window2 < 0 || 
	offset1 < 0 || length1 < offset1+window1 ||
	offset2 < 0 || length2 < offset2+window2) {
	PyErr_SetString(PyExc_ValueError, "Invalid offset/window");
	return NULL;
    }

    if (outlen <= 0) {
	PyErr_SetString(PyExc_ValueError, "Invalid outlen");
	return NULL;
    }

    short* out = (short*) PyMem_Malloc(sizeof(short)*outlen);
    if (out == NULL) return PyErr_NoMemory();

    short* seq1 = (short*)PyString_AsString(data1);
    short* seq2 = (short*)PyString_AsString(data2);
    psolas16(outlen, out, window1, &seq1[offset1], window2, &seq2[offset2]);
    PyObject* obj = PyString_FromStringAndSize((char*)out, sizeof(short)*outlen);
    PyMem_Free(out);
  
    return obj;
}


/* Module initialization */
PyMODINIT_FUNC
initwavcorr(void)
{
    static PyMethodDef functions[] = {
	{ "calcsims16", (PyCFunction)pycalcsims16, METH_VARARGS,
	  "calcsims16"
	},
	{ "calcisf16", (PyCFunction)pycalcisf16, METH_VARARGS,
	  "calcisf16"
	},
	{ "autocorrs16", (PyCFunction)pyautocorrs16, METH_VARARGS,
	  "autocorrs16"
	},
	{ "autosplices16", (PyCFunction)pyautosplices16, METH_VARARGS,
	  "autosplices16"
	},
	{ "psolas16", (PyCFunction)pypsolas16, METH_VARARGS,
	  "psolas16"
	},
	{NULL, NULL},
    };

    Py_InitModule3("wavcorr", functions, "wavcorr"); 
}
