import numpy as np
import numpy
import warnings
from six.moves import xrange

import theano
from theano.tensor import basic
from theano.tensor import nlinalg  # noqa
from theano import gof, scalar
from theano.gradient import DisconnectedType
tensor = basic


class CpuContiguous(theano.Op):
    """
    Check to see if the input is c-contiguous,
    if it is, do nothing, else return a contiguous array.
    """

    __props__ = ()
    view_map = {0: [0]}

    def make_node(self, x):
        x_ = theano.tensor.as_tensor_variable(x)
        return theano.Apply(self, [x_], [x_.type()])

    def perform(self, node, inputs, output_storage):
        x, = inputs
        y = output_storage[0]
        # if the ouput is contiguous do nothing, else copy
        # the input
        if not x.flags['C_CONTIGUOUS']:
            x = x.copy()
        assert x.flags['C_CONTIGUOUS']
        y[0] = x

    def c_code(self, node, name, inames, onames, sub):
        x, = inames
        y, = onames
        code = """
            if (!PyArray_CHKFLAGS(%(x)s, NPY_ARRAY_C_CONTIGUOUS)){
                // check to see if output is contiguous first
                if (%(y)s != NULL &&
                    PyArray_CompareLists(PyArray_DIMS(%(y)s), PyArray_DIMS(%(x)s), PyArray_NDIM(%(x)s)) &&
                    PyArray_CHKFLAGS(%(y)s, NPY_ARRAY_C_CONTIGUOUS)){
                    PyArray_CopyInto(%(y)s, %(x)s);
                }
                else{
                    Py_XDECREF(%(y)s);
                    %(y)s = PyArray_GETCONTIGUOUS(%(x)s);
                }
            }
            else{
                Py_XINCREF(%(x)s);
                Py_XDECREF(%(y)s);
                %(y)s = %(x)s;
            }
            """ % locals()
        return code

    def c_code_cache_version(self):
        return (1,)

cpu_contiguous = CpuContiguous()


class CumsumOp(theano.Op):
    # See function cumsum for docstring

    __props__ = ("axis",)

    def __init__(self, axis=None):
        self.axis = axis

    def make_node(self, x):
        x = basic.as_tensor_variable(x)
        out_type = x.type()

        if self.axis is None:
            out_type = theano.tensor.vector(dtype=x.dtype)  # Flatten
        elif self.axis >= x.ndim or self.axis < -x.ndim:
            raise ValueError('axis(={0}) out of bounds'.format(self.axis))

        return theano.Apply(self, [x], [out_type])

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        z = output_storage[0]
        z[0] = np.cumsum(x, axis=self.axis)

    def grad(self, inputs, output_gradients):
        [gi] = output_gradients

        if self.axis is None:
            return [cumsum(gi[::-1])[::-1].reshape(inputs[0].shape)]

        # We need to reverse the gradients along ``self.axis``,
        #  compute cumsum, then reverse again
        reverse_slicing = [slice(None, None, None)] * gi.ndim
        reverse_slicing[self.axis] = slice(None, None, -1)
        reverse_slicing = tuple(reverse_slicing)
        return [cumsum(gi[reverse_slicing], self.axis)[reverse_slicing]]

    def infer_shape(self, node, shapes):
        if self.axis is None:
            return [(tensor.prod(shapes[0]),)]  # Flatten

        return shapes

    def c_code(self, node, name, inames, onames, sub):
        x, = inames
        z, = onames
        axis = self.axis
        fail = sub['fail']

        if self.axis is None or (self.axis == 0 and node.inputs[0].ndim == 1):
            code = """
                npy_intp shape[1] = { PyArray_SIZE(%(x)s) };
                if(!(%(z)s && PyArray_DIMS(%(z)s)[0] == shape[0]))
                {
                    Py_XDECREF(%(z)s);
                    %(z)s = (PyArrayObject*) PyArray_SimpleNew(1, shape, PyArray_TYPE((PyArrayObject*) py_%(x)s));
                }

                if (!%(z)s)
                    %(fail)s;
                {
                    PyObject * t = PyArray_CumSum(
                        %(x)s, NPY_MAXDIMS,
                        PyArray_TYPE((PyArrayObject*) py_%(x)s), %(z)s);
                    if (!t){
                       %(fail)s;
                    }
                    // Because PyArray_CumSum returns a newly created reference on t.
                    Py_XDECREF(t);
                }
            """ % locals()
        else:
            code = """
                if(!(%(z)s && PyArray_CompareLists(PyArray_DIMS(%(z)s), PyArray_DIMS(%(x)s), PyArray_NDIM(%(x)s))))
                {
                    Py_XDECREF(%(z)s);
                    %(z)s = (PyArrayObject*) PyArray_SimpleNew(PyArray_NDIM(%(x)s), PyArray_DIMS(%(x)s), PyArray_TYPE((PyArrayObject*) py_%(x)s));
                }

                if (!%(z)s)
                    %(fail)s;
                {

                    PyObject * t = PyArray_CumSum(
                        %(x)s, %(axis)s,
                        PyArray_TYPE((PyArrayObject*) py_%(x)s), %(z)s);
                    if (!t){
                       %(fail)s;
                    }
                    // Because PyArray_CumSum returns a newly created reference on t.
                    Py_XDECREF(t);
                }
            """ % locals()

        return code

    def c_code_cache_version(self):
        return (6,)

    def __str__(self):
        return "%s{%s}" % (self.__class__.__name__, self.axis)


def cumsum(x, axis=None):
    """Return the cumulative sum of the elements along a given axis.

    Wraping of numpy.cumsum.

    Parameters
    ----------
    x
        Input tensor variable.
    axis
        The axis along which the cumulative sum is computed.
        The default (None) is to compute the cumsum over the flattened array.


    .. versionadded:: 0.7

    """
    return CumsumOp(axis=axis)(x)


class CumprodOp(theano.Op):
    # See function cumprod for docstring

    __props__ = ("axis",)

    def __init__(self, axis=None):
        self.axis = axis

    def make_node(self, x):
        x = basic.as_tensor_variable(x)
        out_type = x.type()

        if self.axis is None:
            out_type = theano.tensor.vector(dtype=x.dtype)  # Flatten
        elif self.axis >= x.ndim or self.axis < -x.ndim:
            raise ValueError('axis(={0}) out of bounds'.format(self.axis))

        return theano.Apply(self, [x], [out_type])

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        z = output_storage[0]
        z[0] = np.cumprod(x, axis=self.axis)

    def grad(self, inputs, output_gradients):
        x, = inputs
        gi, = output_gradients
        fx = cumprod(x, axis=self.axis)

        if self.axis is None:
            return [cumsum((fx * gi)[::-1])[::-1].reshape(inputs[0].shape) / x]

        # We need to reverse the gradients along ``self.axis``,
        #  compute cumsum, then reverse again
        reverse_slicing = [slice(None, None, None)] * gi.ndim
        reverse_slicing[self.axis] = slice(None, None, -1)
        reverse_slicing = tuple(reverse_slicing)
        return [cumsum((fx * gi)[reverse_slicing],
                       self.axis)[reverse_slicing] / x]

    def infer_shape(self, node, shapes):
        if self.axis is None:
            return [(tensor.prod(shapes[0]),)]  # Flatten

        return shapes

    def c_code(self, node, name, inames, onames, sub):
        x, = inames
        z, = onames
        axis = self.axis
        fail = sub['fail']

        if self.axis is None or (self.axis == 0 and node.inputs[0].ndim == 1):
            code = """
                npy_intp shape[1] = { PyArray_SIZE(%(x)s) };
                if(!(%(z)s && PyArray_DIMS(%(z)s)[0] == shape[0]))
                {
                    Py_XDECREF(%(z)s);
                    %(z)s = (PyArrayObject*) PyArray_SimpleNew(1, shape, PyArray_TYPE((PyArrayObject*) py_%(x)s));
                }

                if (!%(z)s)
                    %(fail)s;
                {
                    PyObject * t = PyArray_CumProd(
                        %(x)s, NPY_MAXDIMS,
                        PyArray_TYPE((PyArrayObject*) py_%(x)s), %(z)s);
                    if (!t){
                       %(fail)s;
                    }
                    // Because PyArray_CumSum returns a newly created reference on t.
                    Py_XDECREF(t);
                }
            """ % locals()
        else:
            code = """
                if(!(%(z)s && PyArray_CompareLists(PyArray_DIMS(%(z)s), PyArray_DIMS(%(x)s), PyArray_NDIM(%(x)s)) ))
                {
                    Py_XDECREF(%(z)s);
                    %(z)s = (PyArrayObject*) PyArray_SimpleNew(PyArray_NDIM(%(x)s), PyArray_DIMS(%(x)s), PyArray_TYPE((PyArrayObject*) py_%(x)s));
                }

                if (!%(z)s)
                    %(fail)s;
                {
                    PyObject * t = PyArray_CumProd(
                        %(x)s, %(axis)s,
                        PyArray_TYPE((PyArrayObject*) py_%(x)s), %(z)s);
                    if (!t){
                       %(fail)s;
                    }
                    // Because PyArray_CumSum returns a newly created reference on t.
                    Py_XDECREF(t);
                }
            """ % locals()

        return code

    def c_code_cache_version(self):
        return (4,)

    def __str__(self):
        return "%s{%s}" % (self.__class__.__name__, self.axis)


def cumprod(x, axis=None):
    """Return the cumulative product of the elements along a given axis.

    Wraping of numpy.cumprod.

    Parameters
    ----------
    x
        Input tensor variable.

    axis
        The axis along which the cumulative product is computed.
        The default (None) is to compute the cumprod over the flattened array.


    .. versionadded:: 0.7

    """
    return CumprodOp(axis=axis)(x)


class DiffOp(theano.Op):
    # See function diff for docstring

    __props__ = ("n", "axis")

    def __init__(self, n=1, axis=-1):
        self.n = n
        self.axis = axis
        # numpy return a view in that case.
        # TODO, make an optimization that remove this op in this case.
        if n == 0:
            self.view_map = {0: [0]}

    def make_node(self, x):
        x = basic.as_tensor_variable(x)
        return theano.Apply(self, [x], [x.type()])

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        z = output_storage[0]
        z[0] = np.diff(x, n=self.n, axis=self.axis)

    def grad(self, inputs, outputs_gradients):
        inputs = inputs[0]

        if inputs.ndim != 1:
            raise NotImplementedError("Grad is not implemented for inputs with"
                                      "number of dimension other than 1.")

        z = outputs_gradients[0]

        def _grad_helper(z):
            pre = basic.concatenate([[0.], z])
            app = basic.concatenate([z, [0.]])
            return pre - app

        for k in range(self.n):
            z = _grad_helper(z)
        return [z]

    def infer_shape(self, node, ins_shapes):
        i0_shapes = ins_shapes[0]
        out_shape = list(i0_shapes)
        out_shape[self.axis] = out_shape[self.axis] - self.n
        return [out_shape]


def diff(x, n=1, axis=-1):
    """Calculate the n-th order discrete difference along given axis.

    The first order difference is given by out[i] = a[i + 1] - a[i]
    along the given axis, higher order differences are calculated by
    using diff recursively. Wraping of numpy.diff.

    Parameters
    ----------
    x
        Input tensor variable.

    n
        The number of times values are differenced, default is 1.

    axis
        The axis along which the difference is taken, default is the last axis.


    .. versionadded:: 0.6

    """
    return DiffOp(n=n, axis=axis)(x)


class BinCountOp(theano.Op):
    """
    .. note:: Deprecated
              Use bincount() instead.
              See function bincount for docstring.

    """
    compatible_type = ('int8', 'int16', 'int32', 'int64',
                       'uint8', 'uint16', 'uint32', 'uint64')
    """Tuple of all compatible dtype for the parameter of this op."""
    __props__ = ("minlength",)

    def __init__(self, minlength=None):
        self.minlength = minlength
        if minlength is not None:
            numpy_ver = [int(n) for n in numpy.__version__.split('.')[:2]]
            if not bool(numpy_ver >= [1, 6]):
                raise NotImplementedError(
                    "BinCountOp with minlength attribute"
                    " requires NumPy 1.6 or higher.")

    def make_node(self, x, weights):
        warnings.warn((
            "Tile op is deprecated, use tile function instead."),
            stacklevel=3)

        x = basic.as_tensor_variable(x)

        if x.dtype not in BinCountOp.compatible_type:
            raise TypeError("Inputs dtype must be an integer.")

        # Some dtypes are not supported by numpy's implementation of bincount.
        # Until another one is available, we should fail at graph construction
        # time, not wait for execution.
        int_bitwidth = theano.configdefaults.python_int_bitwidth()
        if int_bitwidth == 64:
            numpy_unsupported_dtypes = ('uint64',)
        if int_bitwidth == 32:
            numpy_unsupported_dtypes = ('uint32', 'int64', 'uint64')
        intp_bitwidth = theano.configdefaults.local_bitwidth()
        if intp_bitwidth == 32:
            out_type = basic.ivector()
        elif intp_bitwidth == 64:
            out_type = basic.lvector()

        if x.dtype in numpy_unsupported_dtypes:
            raise TypeError(
                ("Input dtypes %s are not supported by numpy.bincount, "
                 % numpy_unsupported_dtypes), x.dtype)

        if x.ndim != 1:
            raise TypeError("Inputs must be of dimension 1.")

        if weights is None:
            weights = theano.gof.Constant(theano.gof.Generic(), None)
        else:
            weights = basic.as_tensor_variable(weights)
            out_type = basic.dvector()
            if weights.ndim != 1:
                raise TypeError("Weights cannot have a number of"
                                "dimension different of 1.")

        return theano.Apply(self, [x, weights], [out_type])

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        weights = inputs[1]
        z = output_storage[0]

        if weights is not None and weights.shape != x.shape:
            raise TypeError("All inputs must have the same shape.")

        # Needed for numpy 1.4.1 compatibility
        if self.minlength:
            out = np.bincount(x, weights=weights, minlength=self.minlength)
        else:
            out = np.bincount(x, weights=weights)

        z[0] = theano._asarray(out, dtype=node.outputs[0].dtype)

    def grad(self, inputs, outputs_gradients):
        output = self(*inputs)

        if output.dtype.find('int') != -1:
            return [inp.zeros_like().astype(theano.config.floatX)
                    for inp in inputs]

        raise NotImplementedError()

    def infer_shape(self, node, ins_shapes):
        x = node.inputs[0]
        m = basic.max(x) + 1
        if self.minlength is not None:
            m = basic.maximum(m, self.minlength)
        return [[m]]


def bincount(x, weights=None, minlength=None, assert_nonneg=False):
    """Count number of occurrences of each value in array of ints.

    The number of bins (of size 1) is one larger than the largest
    value in x. If minlength is specified, there will be at least
    this number of bins in the output array (though it will be longer
    if necessary, depending on the contents of x). Each bin gives the
    number of occurrences of its index value in x. If weights is
    specified the input array is weighted by it, i.e. if a value n
    is found at position i, out[n] += weight[i] instead of out[n] += 1.

    Parameters
    ----------
    x : 1 dimension, nonnegative ints
    weights : array of the same shape as x with corresponding weights.
        Optional.
    minlength : A minimum number of bins for the output array.
        Optional.
    assert_nonneg : A flag that inserts an assert_op to check if
        every input x is nonnegative.
        Optional.


    .. versionadded:: 0.6

    """
    if x.ndim != 1:
        raise TypeError("Inputs must be of dimension 1.")

    if assert_nonneg:
        from theano.tensor.opt import Assert
        assert_op = Assert('Input to bincount has negative values!')
        x = assert_op(x, theano.tensor.all(x >= 0))

    max_value = theano.tensor.cast(x.max() + 1, 'int64')

    if minlength is not None:
        max_value = theano.tensor.maximum(max_value, minlength)

    if weights is None:
        out = theano.tensor.zeros([max_value], dtype=x.dtype)
        out = theano.tensor.inc_subtensor(out[x], 1)
    else:
        out = theano.tensor.zeros([max_value], dtype=weights.dtype)
        out = theano.tensor.inc_subtensor(out[x], weights)
    return out


def squeeze(x):
    """
    Remove broadcastable dimensions from the shape of an array.

    It returns the input array, but with the
    broadcastable dimensions removed. This is
    always `x` itself or a view into `x`.

    .. versionadded:: 0.6

    Parameters
    ----------
    x
        Input data, tensor variable.

    Returns
    -------
    object
        `x` without its broadcastable dimensions.

    """
    view = x.dimshuffle([i for i in range(x.ndim)
                         if not x.broadcastable[i]])
    return view


def compress(condition, x, axis=None):
    """
    Return selected slices of an array along given axis.

    It returns the input tensor, but with selected slices along a given axis
    retained. If no axis is provided, the tensor is flattened.
    Corresponds to numpy.compress

    .. versionadded:: 0.7

    Parameters
    ----------
    x
        Input data, tensor variable.
    condition
         1 dimensional array of non-zero and zero values
         corresponding to indices of slices along a selected axis.

    Returns
    -------
    object
        `x` with selected slices.

    """
    indices = theano.tensor.basic.flatnonzero(condition)
    return x.take(indices, axis=axis)


class RepeatOp(theano.Op):
    # See the repeat function for docstring

    __props__ = ("axis",)

    def __init__(self, axis=None):
        self.axis = axis

    def make_node(self, x, repeats):
        x = basic.as_tensor_variable(x)
        repeats = basic.as_tensor_variable(repeats)

        if repeats.dtype not in tensor.discrete_dtypes:
            raise TypeError("repeats.dtype must be an integer.")

        # Some dtypes are not supported by numpy's implementation of repeat.
        # Until another one is available, we should fail at graph construction
        # time, not wait for execution.
        ptr_bitwidth = theano.configdefaults.local_bitwidth()
        if ptr_bitwidth == 64:
            numpy_unsupported_dtypes = ('uint64',)
        if ptr_bitwidth == 32:
            numpy_unsupported_dtypes = ('uint32', 'int64', 'uint64')

        if repeats.dtype in numpy_unsupported_dtypes:
            raise TypeError(
                ("dtypes %s are not supported by numpy.repeat "
                 "for the 'repeats' parameter, "
                 % str(numpy_unsupported_dtypes)), repeats.dtype)

        if self.axis is None:
            broadcastable = [False]
        else:
            try:
                const_reps = basic.get_scalar_constant_value(repeats)
            except basic.NotScalarConstantError:
                const_reps = None
            if const_reps == 1:
                broadcastable = x.broadcastable
            else:
                broadcastable = list(x.broadcastable)
                broadcastable[self.axis] = False

        out_type = theano.tensor.TensorType(x.dtype, broadcastable)

        return theano.Apply(self, [x, repeats], [out_type()])

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        repeats = inputs[1]
        z = output_storage[0]
        z[0] = np.repeat(x, repeats=repeats, axis=self.axis)

    def connection_pattern(self, node):

        return [[True], [False]]

    def grad(self, inputs, gout):
        (x, repeats) = inputs
        (gz,) = gout
        if repeats.ndim == 0:
            if self.axis is None:
                axis = x.ndim
            else:
                if self.axis >= 0:
                    axis = self.axis + 1
                else:
                    axis = self.axis + x.ndim + 1

            shape = [x.shape[k] for k in range(x.ndim)]
            shape.insert(axis, repeats)

            return [gz.reshape(shape, x.ndim + 1).sum(axis=axis),
                    DisconnectedType()()]
        elif repeats.ndim == 1:
            # For this implementation, we would need to specify the length
            # of repeats in order to split gz in the right way to sum
            # the good part.
            raise NotImplementedError()
        else:
            raise ValueError()

    def infer_shape(self, node, ins_shapes):
        i0_shapes = ins_shapes[0]
        repeats = node.inputs[1]
        out_shape = list(i0_shapes)

        # uint64 shape are not supported.
        dtype = None
        if repeats.dtype in ['uint8', 'uint16', 'uint32']:
            dtype = 'int64'
        if self.axis is None:
            if repeats.ndim == 0:
                if len(i0_shapes) == 0:
                    out_shape = [repeats]
                else:
                    res = 1
                    for d in i0_shapes:
                        res = res * d
                    out_shape = (res * repeats, )
            else:
                out_shape = [theano.tensor.sum(repeats, dtype=dtype)]
        else:
            if repeats.ndim == 0:
                out_shape[self.axis] = out_shape[self.axis] * repeats
            else:
                out_shape[self.axis] = theano.tensor.sum(repeats, dtype=dtype)
        return [out_shape]


def repeat(x, repeats, axis=None):
    """Repeat elements of an array.

    It returns an array which has the same shape as `x`, except
    along the given axis. The axis is used to speficy along which
    axis to repeat values. By default, use the flattened input
    array, and return a flat output array.

    The number of repetitions for each element is `repeat`.
    `repeats` is broadcasted to fit the length of the given `axis`.

    Parameters
    ----------
    x
        Input data, tensor variable.
    repeats
        int, scalar or tensor variable
    axis : int, optional

    See Also
    --------
    tensor.tile

    .. versionadded:: 0.6

    """
    repeats = tensor.as_tensor_variable(repeats)

    if repeats.ndim > 1:
        raise ValueError('The dimension of repeats should not exceed 1.')

    if repeats.ndim == 1 and not repeats.broadcastable[0]:
            return RepeatOp(axis=axis)(x, repeats)
    else:
        if repeats.ndim == 1:
            repeats = repeats[0]

        if x.dtype == 'uint64':
            raise TypeError("theano.tensor.repeat don't support dtype uint64")

        if axis is None:
            axis = 0
            x = x.flatten()
        else:
            if axis >= x.ndim:
                raise ValueError('Axis should not exceed x.ndim-1.')
            if axis < 0:
                axis = x.ndim + axis

        shape = [x.shape[i] for i in xrange(x.ndim)]

        # shape_ is the shape of the intermediate tensor which has
        # an additional dimension comparing to x. We use alloc to
        # allocate space for this intermediate tensor to replicate x
        # along that additional dimension.
        shape_ = shape[:]
        shape_.insert(axis + 1, repeats)

        # shape is now the shape of output, where shape[axis] becomes
        # shape[axis]*repeats.
        shape[axis] = shape[axis] * repeats

        # dims_ is the dimension of that intermediate tensor.
        dims_ = list(numpy.arange(x.ndim))
        dims_.insert(axis + 1, 'x')

        # After the original tensor is duplicated along the additional
        # dimension, we reshape it to the expected output shape, and
        # return the output z.
        z = tensor.alloc(x.dimshuffle(*dims_), *shape_).reshape(shape)
        return z


class Bartlett(gof.Op):
    # See function bartlett for docstring
    __props__ = ()

    def make_node(self, M):
        M = tensor.as_tensor_variable(M)
        if M.ndim != 0:
            raise TypeError('%s only works on scalar input'
                            % self.__class__.__name__)
        elif (not M.dtype.startswith('int') and
              not M.dtype.startswith('uint')):
            # dtype is a theano attribute here
            raise TypeError('%s only works on integer input'
                            % self.__class__.__name__)
        return gof.Apply(self, [M], [tensor.dvector()])

    def perform(self, node, inputs, out_):
        M = inputs[0]
        out, = out_
        out[0] = numpy.bartlett(M)

    def infer_shape(self, node, in_shapes):
        temp = node.inputs[0]
        M = tensor.switch(tensor.lt(temp, 0),
                          tensor.cast(0, temp.dtype),
                          temp)
        return [[M]]

    def grad(self, inputs, output_grads):
        return [None for i in inputs]
bartlett_ = Bartlett()


# I create a function only to have the doc show well.
def bartlett(M):
    """
    An instance of this class returns the Bartlett spectral window in the
    time-domain. The Bartlett window is very similar to a triangular window,
    except that the end points are at zero. It is often used in signal
    processing for tapering a signal, without generating too much ripple in
    the frequency domain.

    .. versionadded:: 0.6

    Parameters
    ----------
    M : integer scalar
        Number of points in the output window. If zero or less,
        an empty vector is returned.

    Returns
    -------
    vector of doubles
        The triangular window, with the maximum value normalized to one
        (the value one appears only if the number of samples is odd), with
        the first and last samples equal to zero.

    """
    return bartlett_(M)


class FillDiagonal(gof.Op):
    # See function fill_diagonal for docstring
    __props__ = ()

    def infer_shape(self, node, in_shapes):
        return [in_shapes[0]]

    def make_node(self, a, val):
        a = tensor.as_tensor_variable(a)
        val = tensor.as_tensor_variable(val)
        if a.ndim < 2:
            raise TypeError('%s: first parameter must have at least'
                            ' two dimensions' % self.__class__.__name__)
        elif val.ndim != 0:
            raise TypeError('%s: second parameter must be a scalar'
                            % self.__class__.__name__)
        val = tensor.cast(val, dtype=scalar.upcast(a.dtype, val.dtype))
        if val.dtype != a.dtype:
            raise TypeError('%s: type of second parameter must be the same as'
                            ' the first\'s' % self.__class__.__name__)
        return gof.Apply(self, [a, val], [a.type()])

    def perform(self, node, inputs, output_storage):
        a = inputs[0].copy()
        val = inputs[1]
        if a.ndim == 2:
            # numpy.fill_diagonal up to date(including 1.6.2) have a
            # bug for tall matrix.
            # For 2-d arrays, we accept rectangular ones.
            step = a.shape[1] + 1
            end = a.shape[1] * a.shape[1]
            # Write the value out into the diagonal.
            a.flat[:end:step] = val
        else:
            numpy.fill_diagonal(a, val)

        output_storage[0][0] = a

    def grad(self, inp, cost_grad):
        """
        Notes
        -----
        The gradient is currently implemented for matrices only.

        """
        a, val = inp
        grad = cost_grad[0]
        if (a.dtype.startswith('complex')):
            return [None, None]
        elif a.ndim > 2:
            raise NotImplementedError('%s: gradient is currently implemented'
                                      ' for matrices only' %
                                      self.__class__.__name__)
        wr_a = fill_diagonal(grad, 0)  # valid for any number of dimensions
        # diag is only valid for matrices
        wr_val = theano.tensor.nlinalg.diag(grad).sum()
        return [wr_a, wr_val]
fill_diagonal_ = FillDiagonal()


# I create a function only to have the doc show well.
def fill_diagonal(a, val):
    """
    Returns a copy of an array with all
    elements of the main diagonal set to a specified scalar value.

    .. versionadded:: 0.6

    Parameters
    ----------
    a
        Rectangular array of at least two dimensions.
    val
        Scalar value to fill the diagonal whose type must be
        compatible with that of array 'a' (i.e. 'val' cannot be viewed
        as an upcast of 'a').

    Returns
    -------
    array
        An array identical to 'a' except that its main diagonal
        is filled with scalar 'val'. (For an array 'a' with a.ndim >=
        2, the main diagonal is the list of locations a[i, i, ..., i]
        (i.e. with indices all identical).)

    Support rectangular matrix and tensor with more than 2 dimensions
    if the later have all dimensions are equals.



    """
    return fill_diagonal_(a, val)


class FillDiagonalOffset(gof.Op):
    # See function fill_diagonal_offset for docstring
    __props__ = ()

    def infer_shape(self, node, in_shapes):
        return [in_shapes[0]]

    def make_node(self, a, val, offset):
        a = tensor.as_tensor_variable(a)
        val = tensor.as_tensor_variable(val)
        offset = tensor.as_tensor_variable(offset)
        if a.ndim != 2:
            raise TypeError('%s: first parameter must have exactly'
                            ' two dimensions' % self.__class__.__name__)
        elif val.ndim != 0:
            raise TypeError('%s: second parameter must be a scalar'
                            % self.__class__.__name__)
        elif offset.ndim != 0:
            raise TypeError('%s: third parameter must be a scalar'
                            % self.__class__.__name__)
        val = tensor.cast(val, dtype=scalar.upcast(a.dtype, val.dtype))
        if val.dtype != a.dtype:
            raise TypeError('%s: type of second parameter must be the same'
                            ' as the first\'s' % self.__class__.__name__)
        elif offset.dtype[:3] != 'int':
            raise TypeError('%s: type of third parameter must be as integer'
                            ' use theano.tensor.cast( input, \'int32/int64\')'
                            % self.__class__.__name__)

        return gof.Apply(self, [a, val, offset], [a.type()])

    def perform(self, node, inputs, output_storage):
        a = inputs[0].copy()
        val = inputs[1]
        offset = inputs[2]
        height, width = a.shape

        """
        Notes
        -----
        The fill_diagonal only support rectangular matrix. The output
        of tall matrix is "wrapped", which is an option in numpy 1.9.0
        but was regarded as a bug in numpy 1.6.2. Here I implement the
        fill_diagonal_offset with unwrapped output, so fill_diagonal_offset
        supports tall matrix.(This make a little difference between the output
        of fill_diagonal and fill_diagonal_offset only in the case of tall
        matrix)

        """
        if offset >= 0:
            start = offset
            num_of_step = min(min(width, height), width - offset)
        else:
            start = - offset * a.shape[1]
            num_of_step = min(min(width, height), height + offset)
        step = a.shape[1] + 1
        end = start + step * num_of_step
        # Write the value out into the diagonal.
        a.flat[start:end:step] = val

        output_storage[0][0] = a

    def grad(self, inp, cost_grad):
        """
        Notes
        -----
        The gradient is currently implemented for matrices only.
        """
        a, val, offset = inp
        grad = cost_grad[0]
        height, width = grad.shape

        if (a.dtype.startswith('complex')):
            return [None, None]

        # only valid for matrices
        wr_a = fill_diagonal_offset(grad, 0, offset)

        offset_abs = basic.abs_(offset)
        pos_offset_flag = basic.ge(offset, 0)
        neg_offset_flag = basic.lt(offset, 0)
        min_wh = basic.minimum(width, height)

        start = offset * pos_offset_flag + offset_abs * width * neg_offset_flag
        num_of_step = basic.minimum(min_wh, width * pos_offset_flag +
                                    height * neg_offset_flag - offset_abs)

        step = a.shape[1] + 1
        end = start + step * num_of_step

        # input of slice should be integer
        start = basic.cast(start, 'int32')
        step = basic.cast(step, 'int32')
        end = basic.cast(end, 'int32')

        wr_val = grad.flatten()[start:end:step].sum()

        wr_offset = theano.gradient.grad_undefined(
            self, 2, offset,
            "offset is not defined for non-integer offset so"
            " fill_diagonal_offset(a,val,offset+eps) is undefined")

        return [wr_a, wr_val, wr_offset]

fill_diagonal_offset_ = FillDiagonalOffset()


def fill_diagonal_offset(a, val, offset):
    """
    Returns a copy of an array with all
    elements of the main diagonal set to a specified scalar value.

    Parameters
    ----------
    a
        Rectangular array of two dimensions.
    val
        Scalar value to fill the diagonal whose type must be
        compatible with that of array 'a' (i.e. 'val' cannot be viewed
        as an upcast of 'a').
    offset
        Scalar value Offset of the diagonal from the main
        diagonal. Can be positive or negative integer.

    Returns
    -------
    array
        An array identical to 'a' except that its offset diagonal
        is filled with scalar 'val'. The output is unwrapped.

    """
    return fill_diagonal_offset_(a, val, offset)


def to_one_hot(y, nb_class, dtype=None):
    """
    Return a matrix where each row correspond to the one hot
    encoding of each element in y.

    Parameters
    ----------
    y
        A vector of integer value between 0 and nb_class - 1.
    nb_class : int
        The number of class in y.
    dtype : data-type
        The dtype of the returned matrix. Default floatX.

    Returns
    -------
    object
        A matrix of shape (y.shape[0], nb_class), where each row ``i`` is
        the one hot encoding of the corresponding ``y[i]`` value.

    """
    ret = theano.tensor.zeros((y.shape[0], nb_class),
                              dtype=dtype)
    ret = theano.tensor.set_subtensor(ret[theano.tensor.arange(y.shape[0]), y],
                                      1)
    return ret


class Unique(theano.Op):
    """
    Wraps numpy.unique. This op is not implemented on the GPU.

    Examples
    --------
    >>> import numpy as np
    >>> import theano

    >>> x = theano.tensor.vector()
    >>> f = theano.function([x], Unique(True, True, False)(x))
    >>> f([1, 2., 3, 4, 3, 2, 1.])
    [array([ 1.,  2.,  3.,  4.]), array([0, 1, 2, 3]), array([0, 1, 2, 3, 2, 1, 0])]

    >>> y = theano.tensor.matrix()
    >>> g = theano.function([y], Unique(True, True, False)(y))
    >>> g([[1, 1, 1.0], (2, 3, 3.0)])
    [array([ 1.,  2.,  3.]), array([0, 3, 4]), array([0, 0, 0, 1, 2, 2])]

    """

    __props__ = ("return_index", "return_inverse", "return_counts")

    def __init__(self, return_index=False, return_inverse=False,
                 return_counts=False):
        self.return_index = return_index
        self.return_inverse = return_inverse
        self.return_counts = return_counts
        numpy_ver = [int(n) for n in numpy.__version__.split('.')[:2]]
        if self.return_counts and bool(numpy_ver < [1, 9]):
            raise RuntimeError(
                "Numpy version = " + np.__version__ +
                ". Option 'return_counts=True' works starting"
                " from version 1.9.0.")

    def make_node(self, x):
        x = basic.as_tensor_variable(x)
        outputs = [basic.TensorType(broadcastable=[False], dtype=x.dtype)()]
        typ = basic.TensorType(broadcastable=[False], dtype='int64')
        if self.return_index:
            outputs.append(typ())
        if self.return_inverse:
            outputs.append(typ())
        if self.return_counts:
            outputs.append(typ())
        return theano.Apply(self, [x], outputs)

    def perform(self, node, inputs, output_storage):
        x = inputs[0]
        z = output_storage
        param = {}
        if self.return_index:
            param['return_index'] = True
        if self.return_inverse:
            param['return_inverse'] = True
        if self.return_counts:
            param['return_counts'] = True
        outs = np.unique(x, **param)
        if ((not self.return_inverse) and
                (not self.return_index) and
                (not self.return_counts)):
            z[0][0] = outs
        else:
            for i in range(len(outs)):
                z[i][0] = outs[i]

    def infer_shape(self, node, i0_shapes):
        ret = node.fgraph.shape_feature.default_infer_shape(node, i0_shapes)
        if self.return_inverse:
            shape = (basic.prod(i0_shapes[0]), )
            if self.return_index:
                ret[2] = shape
                return ret
            ret[1] = shape
            return ret
        return ret
