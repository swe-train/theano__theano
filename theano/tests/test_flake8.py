"""
Test flake8 errors.
"""

from nose.plugins.skip import SkipTest
import os
from fnmatch import fnmatch
import theano
try:
    import flake8.engine
    import flake8.main
    flake8_available = True
except ImportError:
    flake8_available = False

__authors__ = ("Saizheng Zhang")
__copyright__ = "(c) 2016, Universite de Montreal"
__contact__ = "Saizheng Zhang <saizhenglisa..at..gmail.com>"

# We ignore:
# - "line too long"
#    too complex to do with the C code
# - "closing bracket does not match indentation of opening bracket's line"
#    ignored by default by pep8
# - All errors from flake8-future-import
ignore = ('E501', 'E123', 'E133',
          'FI10', 'FI11', 'FI12', 'FI13', 'FI14', 'FI15', 'FI16', 'FI17',
          'FI50', 'FI51', 'FI53')

whitelist_flake8 = [
    "compat/six.py",  # This is bundled code that will be deleted, don't fix it
    "__init__.py",
    "tests/__init__.py",
    "compile/__init__.py",
    "compile/profiling.py",
    "typed_list/__init__.py",
    "tensor/__init__.py",
    "tensor/tests/test_subtensor.py",
    "tensor/tests/test_utils.py",
    "tensor/tests/test_nlinalg.py",
    "tensor/tests/test_shared_randomstreams.py",
    "tensor/tests/test_misc.py",
    "tensor/tests/mlp_test.py",
    "tensor/tests/test_opt_uncanonicalize.py",
    "tensor/tests/test_opt.py",
    "tensor/tests/test_basic.py",
    "tensor/tests/test_blas.py",
    "tensor/tests/test_elemwise.py",
    "tensor/tests/test_merge.py",
    "tensor/tests/test_gc.py",
    "tensor/tests/test_complex.py",
    "tensor/tests/test_io.py",
    "tensor/tests/test_sharedvar.py",
    "tensor/tests/test_fourier.py",
    "tensor/tests/test_casting.py",
    "tensor/tests/test_sort.py",
    "tensor/tests/test_raw_random.py",
    "tensor/tests/test_xlogx.py",
    "tensor/tests/test_extra_ops.py",
    "tensor/tests/test_slinalg.py",
    "tensor/tests/test_blas_c.py",
    "tensor/tests/test_blas_scipy.py",
    "tensor/tests/test_mpi.py",
    "tensor/signal/conv.py",
    "tensor/signal/tests/test_conv.py",
    "tensor/signal/tests/test_downsample.py",
    "tensor/nnet/__init__.py",
    "tensor/nnet/tests/test_conv.py",
    "tensor/nnet/tests/test_neighbours.py",
    "tensor/nnet/tests/test_nnet.py",
    "tensor/nnet/tests/test_conv3d2d.py",
    "tensor/nnet/tests/test_conv3d.py",
    "tensor/nnet/tests/speed_test_conv.py",
    "tensor/nnet/tests/test_sigm.py",
    "scalar/__init__.py",
    "scalar/tests/test_basic.py",
    "sandbox/tests/test_theano_object.py",
    "sandbox/tests/test_scan.py",
    "sandbox/tests/test_neighbourhoods.py",
    "sandbox/tests/__init__.py",
    "sandbox/cuda/var.py",
    "sandbox/cuda/GpuConvGrad3D.py",
    "sandbox/cuda/basic_ops.py",
    "sandbox/cuda/nnet.py",
    "sandbox/cuda/elemwise.py",
    "sandbox/cuda/type.py",
    "sandbox/cuda/__init__.py",
    "sandbox/cuda/opt.py",
    "sandbox/cuda/blas.py",
    "sandbox/cuda/blocksparse.py",
    "sandbox/cuda/rng_curand.py",
    "sandbox/cuda/fftconv.py",
    "sandbox/cuda/kernel_codegen.py",
    "sandbox/cuda/GpuConvTransp3D.py",
    "sandbox/cuda/nvcc_compiler.py",
    "sandbox/cuda/neighbours.py",
    "sandbox/cuda/tests/walltime.py",
    "sandbox/cuda/tests/test_gradient.py",
    "sandbox/cuda/tests/test_neighbours.py",
    "sandbox/cuda/tests/test_conv_cuda_ndarray.py",
    "sandbox/cuda/tests/test_var.py",
    "sandbox/cuda/tests/test_opt.py",
    "sandbox/cuda/tests/test_blas.py",
    "sandbox/cuda/tests/test_driver.py",
    "sandbox/cuda/tests/test_rng_curand.py",
    "sandbox/cuda/tests/test_basic_ops.py",
    "sandbox/cuda/tests/test_memory.py",
    "sandbox/cuda/tests/test_mlp.py",
    "sandbox/cuda/tests/test_bench_loopfusion.py",
    "sandbox/cuda/tests/test_blocksparse.py",
    "sandbox/cuda/tests/test_cuda_ndarray.py",
    "sandbox/cuda/tests/test_tensor_op.py",
    "sandbox/cuda/tests/test_extra_ops.py",
    "sandbox/cuda/tests/test_gemmcorr3d.py",
    "sandbox/cuda/tests/test_viewop.py",
    "sandbox/scan_module/scan_utils.py",
    "sandbox/scan_module/scan.py",
    "sandbox/scan_module/scan_op.py",
    "sandbox/scan_module/__init__.py",
    "sandbox/scan_module/tests/test_utils.py",
    "sandbox/scan_module/tests/test_scan.py",
    "sandbox/linalg/ops.py",
    "sandbox/linalg/__init__.py",
    "sandbox/linalg/tests/test_linalg.py",
    "sandbox/gpuarray/__init__.py",
    "scan_module/scan_utils.py",
    "scan_module/scan_views.py",
    "scan_module/scan.py",
    "scan_module/scan_op.py",
    "scan_module/scan_perform_ext.py",
    "scan_module/__init__.py",
    "scan_module/tests/test_scan.py",
    "scan_module/tests/test_scan_opt.py",
    "misc/hooks/reindent.py",
    "misc/hooks/check_whitespace.py",
    "sparse/__init__.py",
    "sparse/tests/test_utils.py",
    "sparse/tests/test_opt.py",
    "sparse/tests/test_basic.py",
    "sparse/tests/test_sp2.py",
    "sparse/sandbox/test_sp.py",
    "sparse/sandbox/sp2.py",
    "sparse/sandbox/truedot.py",
    "sparse/sandbox/sp.py",
    "gof/unify.py",
    "gof/__init__.py",
    "gof/sandbox/equilibrium.py",
    "d3viz/__init__.py"
]


def list_files(dir_path=theano.__path__[0], pattern='*.py', no_match=".#"):
    """
    List all files under theano's path.
    """
    files_list = []
    for (dir, _, files) in os.walk(dir_path):
        for f in files:
            if fnmatch(f, pattern):
                path = os.path.join(dir, f)
                if not f.startswith(no_match):
                    files_list.append(path)
    return files_list


def test_format_flake8():
    """
    Test if flake8 is respected.
    """
    if not flake8_available:
        raise SkipTest("flake8 is not installed")
    total_errors = 0
    for path in list_files():
        rel_path = os.path.relpath(path, theano.__path__[0])
        if rel_path in whitelist_flake8:
            continue
        else:
            error_num = flake8.main.check_file(path, ignore=ignore)
            total_errors += error_num
    if total_errors > 0:
        raise AssertionError("FLAKE8 Format not respected")


def print_files_information_flake8():
    """
    Print the list of files which can be removed from the whitelist and the
    list of files which do not respect FLAKE8 formatting that aren't in the
    whitelist.
    """
    infracting_files = []
    non_infracting_files = []
    for path in list_files():
        rel_path = os.path.relpath(path, theano.__path__[0])
        number_of_infractions = flake8.main.check_file(path,
                                                       ignore=ignore)
        if number_of_infractions > 0:
            if rel_path not in whitelist_flake8:
                infracting_files.append(rel_path)
        else:
            if rel_path in whitelist_flake8:
                non_infracting_files.append(rel_path)
    print("Files that must be corrected or added to whitelist:")
    for file in infracting_files:
        print(file)
    print("Files that can be removed from whitelist:")
    for file in non_infracting_files:
        print(file)


def check_all_files(dir_path=theano.__path__[0], pattern='*.py'):
    """
    List all .py files under dir_path (theano path), check if they follow
    flake8 format, save all the error-formatted files into
    theano_filelist.txt. This function is used for generating
    the "whitelist_flake8" in this file.
    """

    with open('theano_filelist.txt', 'a') as f_txt:
        for (dir, _, files) in os.walk(dir_path):
            for f in files:
                if fnmatch(f, pattern):
                    error_num = flake8.main.check_file(os.path.join(dir, f),
                                                       ignore=ignore)
                    if error_num > 0:
                        path = os.path.relpath(os.path.join(dir, f),
                                               theano.__path__[0])
                        f_txt.write('"' + path + '",\n')


if __name__ == "__main__":
    print_files_information_flake8()
