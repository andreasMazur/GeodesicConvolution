#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <math.h>
#include "numpy/arrayobject.h"
#include "cblas.h"


double compute_angle(double vector_1[], double vector_2[])
{
    double v1_norm = cblas_dnrm2(3, vector_1, 1);
    double v2_norm = cblas_dnrm2(3, vector_2, 1);
    double v1v2_dot = cblas_ddot(3, vector_1, 1, vector_2, 1);
    double x = v1v2_dot / (v1_norm * v2_norm);

    if (x > 1) x = 1;
    if (x < -1) x = -1;

    return acos(x);
}


void compute_dist_and_dir(double vertex_i[],
                          double vertex_j[],
                          double vertex_k[],
                          double u_j,
                          double u_k,
                          double theta_j,
                          double theta_k,
                          double *result)
{
    double e_j[3];
    cblas_dcopy(3, vertex_j, 1, e_j, 1);
    cblas_daxpy(3, -1.0, vertex_i, 1, e_j, 1);
    double e_j_norm = cblas_dnrm2(3, e_j, 1);

    double e_k[3];
    cblas_dcopy(3, vertex_k, 1, e_k, 1);
    cblas_daxpy(3, -1.0, vertex_i, 1, e_k, 1);
    double e_k_norm = cblas_dnrm2(3, e_k, 1);

    double e_kj[3];
    cblas_dcopy(3, vertex_k, 1, e_kj, 1);
    cblas_daxpy(3, -1.0, vertex_j, 1, e_kj, 1);
    double e_kj_sqnrm = cblas_ddot(3, e_kj, 1, e_kj, 1);

    double A = e_j_norm * e_k_norm * sin(compute_angle(e_j, e_k));
    double radicand = (e_kj_sqnrm - pow(u_j - u_k, 2)) * (pow(u_j + u_k, 2) - e_kj_sqnrm);

    double u_ijk;
    double theta_i;
    if(radicand <= 0)
    {
        double j = u_j + cblas_dnrm2(3, e_j, 1);
        double k = u_k + cblas_dnrm2(3, e_k, 1);
        if(j <= k)
        {
            u_ijk = j;
            theta_i = theta_j;
        } else {
            u_ijk = k;
            theta_i = theta_k;
        }
    } else {
        double H = sqrt(radicand);
        double u_j_sq = pow(u_j, 2);
        double u_k_sq = pow(u_k, 2);
        double x_j = A * (e_kj_sqnrm + u_k_sq - u_j_sq) + cblas_ddot(3, e_k, 1, e_kj, 1) * H;
        double x_k = A * (e_kj_sqnrm + u_j_sq - u_k_sq) - cblas_ddot(3, e_j, 1, e_kj, 1) * H;
        if (x_j < 0 || x_k < 0) {
            double j = u_j + cblas_dnrm2(3, e_j, 1);
            double k = u_k + cblas_dnrm2(3, e_k, 1);
            if(j <= k)
            {
                u_ijk = j;
                theta_i = theta_j;
            } else {
                u_ijk = k;
                theta_i = theta_k;
            }
        } else {
            // Compute distance
            double denominator = 2 * A * e_kj_sqnrm;
            x_j /= denominator;
            x_k /= denominator;
            cblas_dscal(3, x_j, e_j, 1);
            cblas_dscal(3, x_k, e_k, 1);

            double result_vector[3];
            cblas_dcopy(3, e_k, 1, result_vector, 1);
            cblas_daxpy(3, 1.0, e_j, 1, result_vector, 1);
            u_ijk = cblas_dnrm2(3, result_vector, 1);

            // Compute angle
            double s[3];
            cblas_dcopy(3, result_vector, 1, s, 1);
            cblas_daxpy(3, 1.0, vertex_i, 1, s, 1);

            cblas_daxpy(3, -1.0, s, 1, vertex_k, 1);
            cblas_daxpy(3, -1.0, s, 1, vertex_j, 1);
            cblas_daxpy(3, -1.0, s, 1, vertex_i, 1);
            double phi_kj = compute_angle(vertex_k, vertex_j);
            double phi_ij = compute_angle(vertex_i, vertex_j);
            if (!phi_kj) {
                double j = u_j + cblas_dnrm2(3, e_j, 1);
                double k = u_k + cblas_dnrm2(3, e_k, 1);
                if(j <= k)
                {
                    u_ijk = j;
                    theta_i = theta_j;
                } else {
                    u_ijk = k;
                    theta_i = theta_k;
                }
            } else {
                double alpha = phi_ij / phi_kj;
                theta_i = fmod((1 - alpha) * theta_j + alpha * theta_k, 2 * M_PI);
            }
        }
    }

    result[0] = u_ijk;
    result[1] = theta_i;
}

static PyObject *compute_dist_and_dir_wrapper(PyObject *self, PyObject *args) {

    // Parse numpy array
    PyArrayObject *result_values_numpy, *vertex_i_numpy, *vertex_j_numpy, *vertex_k_numpy;
    double u_j, u_k, theta_j, theta_k;
    double vertex_i[3], vertex_j[3], vertex_k[3], result_values[2];

    if(!PyArg_ParseTuple(args,
                         "O!O!O!O!dddd",
                         &PyArray_Type,
                         &result_values_numpy,
                         &PyArray_Type,
                         &vertex_i_numpy,
                         &PyArray_Type,
                         &vertex_j_numpy,
                         &PyArray_Type,
                         &vertex_k_numpy,
                         &u_j,
                         &u_k,
                         &theta_j,
                         &theta_k)) {
        return NULL;
    }

    PyArrayObject *vertices_numpy[] = {vertex_i_numpy, vertex_j_numpy, vertex_k_numpy, result_values_numpy};
    double *vertices[] = {vertex_i, vertex_j, vertex_k};
    for (int i = 0; i < 3; i++) {
        // Check for correct array types
        if (vertices_numpy[i]->nd != 1 || vertices_numpy[i]->descr->type_num != PyArray_DOUBLE) {
            PyErr_SetString(PyExc_ValueError, "Array must be one-dimensional and of type numpy.float64!");
            return NULL;
        }
        // Translate Numpy array to C array (except `result_values`)
        if (i < 3) {
            for (int j = 0; j < 3; j++) {
                vertices[i][j] = *(double *)(vertices_numpy[i]->data + j * vertices_numpy[i]->strides[0]);
            }
        }
    }

    // Compute geodesic distance and angle. Store result in `result`-array.
    compute_dist_and_dir(vertices[0], vertices[1], vertices[2], u_j, u_k, theta_j, theta_k, result_values);

    // Write the result into the numpy result array
    for (int i = 0; i < 2; i++) {
        *(double *)(result_values_numpy->data + i * result_values_numpy->strides[0]) = result_values[i];
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *compute_angle_wrapper(PyObject *self, PyObject *args) {
    PyArrayObject *vector_1_numpy, *vector_2_numpy;
    double vector_1[3], vector_2[3];

    if(!PyArg_ParseTuple(args,
                         "O!O!",
                         &PyArray_Type,
                         &vector_1_numpy,
                         &PyArray_Type,
                         &vector_2_numpy)) {
        return NULL;
    }

    PyArrayObject *vectors_numpy[] = {vector_1_numpy, vector_2_numpy};
    double *vectors[] = {vector_1, vector_2};
    for (int i = 0; i < 2; i++) {
        // Check for correct array types
        if (vectors_numpy[i]->nd != 1 || vectors_numpy[i]->descr->type_num != PyArray_DOUBLE) {
            PyErr_SetString(PyExc_ValueError, "Array must be one-dimensional and of type numpy.float64!");
            return NULL;
        }
        // Translate Numpy array to C array (except `result_values`)
        if (i < 3) {
            for (int j = 0; j < 3; j++) {
                vectors[i][j] = *(double *)(vectors_numpy[i]->data + j * vectors_numpy[i]->strides[0]);
            }
        }
    }

    double angle = compute_angle(vectors[0], vectors[1]);
    return PyFloat_FromDouble(angle);
}

static PyMethodDef C_Extension_Methods[] = {
    {"compute_dist_and_dir", compute_dist_and_dir_wrapper, METH_VARARGS, "Compute GPC in C."},
    {"compute_angle", compute_angle_wrapper, METH_VARARGS, "Compute the angle between two vectors."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef c_extension = {
    PyModuleDef_HEAD_INIT,
    "c_extension",
    NULL,
    -1,
    C_Extension_Methods
};

PyMODINIT_FUNC PyInit_c_extension(void) {
    PyObject *module;

    module = PyModule_Create(&c_extension);
    if(module == NULL) return NULL;

    import_array();  // This is mandatory: https://numpy.org/doc/1.17/reference/c-api.array.html#c.import_array
    if (PyErr_Occurred()) return NULL;

    return module;
}
