import anndata as ad
import h5py
import numpy as np
import pytest
import zarr
from anndata.tests.helpers import assert_equal, subset_func, slice_subset, array_int_subset, array_bool_subset
from scipy import sparse

from cirrocumulus.sparse_dataset import SparseDataset

subset_func2 = subset_func


@pytest.fixture(scope="function")
def ondisk_equivalent_adata(tmp_path):
    csr_path = tmp_path / "csr.h5ad"
    csc_path = tmp_path / "csc.h5ad"
    dense_path = tmp_path / "dense.h5ad"

    csr_mem = ad.AnnData(X=sparse.random(50, 50, format="csr", density=0.1))
    csc_mem = ad.AnnData(X=csr_mem.X.tocsc())

    csr_mem.write_h5ad(csr_path)
    csc_mem.write_h5ad(csc_path)
    csr_mem.write_h5ad(dense_path, as_dense="X")

    csr_disk = ad.read_h5ad(csr_path, backed="r")
    csc_disk = ad.read_h5ad(csc_path, backed="r")
    dense_disk = ad.read_h5ad(dense_path, backed="r")

    return csr_mem, csr_disk, csc_disk, dense_disk


@pytest.fixture(scope="function")
def ondisk_equivalent_adata_zarr(tmp_path):
    csr_path = tmp_path / "csr.zarr"
    csc_path = tmp_path / "csc.zarr"

    csr_mem = ad.AnnData(X=sparse.random(50, 50, format="csr", density=0.1))
    csc_mem = ad.AnnData(X=csr_mem.X.tocsc())

    csr_mem.write_zarr(csr_path)
    csc_mem.write_zarr(csc_path)

    csr_disk = SparseDataset(zarr.open(csr_path / "X"))
    csc_disk = SparseDataset(zarr.open(csc_path / "X"))

    return csr_mem, csr_disk, csc_disk


@pytest.fixture(params=[slice_subset, array_int_subset, array_bool_subset])
def subset_func_zarr(request):
    return request.param


# not supported:
# array_subset,
# single_subset
# matrix_bool_subset
# spmatrix_bool_subset
# spmatrix_bool_subset


def test_backed_indexing_zarr_obs(ondisk_equivalent_adata_zarr, subset_func_zarr):
    csr_mem, csr_disk, csc_disk = ondisk_equivalent_adata_zarr
    X = csr_mem.X
    idx = subset_func_zarr(csr_mem.obs_names)
    assert_equal(X[idx], csr_disk[idx])
    assert_equal(X[idx], csc_disk[idx])


def test_backed_indexing_zarr_var(ondisk_equivalent_adata_zarr, subset_func_zarr):
    csr_mem, csr_disk, csc_disk = ondisk_equivalent_adata_zarr
    X = csr_mem.X
    idx = subset_func_zarr(csr_mem.var_names)
    assert_equal(X[:, idx], csr_disk[:, idx])
    assert_equal(X[:, idx], csc_disk[:, idx])


# subset_func_zarr2 = subset_func_zarr
#
#
# def test_backed_indexing_zarr(ondisk_equivalent_adata_zarr, subset_func_zarr, subset_func_zarr2):
#     csr_mem, csr_disk, csc_disk = ondisk_equivalent_adata_zarr
#     obs_idx = subset_func_zarr(csr_mem.obs_names)
#     var_idx = subset_func_zarr2(csr_mem.var_names)
#     X = csr_mem.X
#     assert_equal(X[obs_idx:, var_idx], csr_disk[obs_idx][:, var_idx])
#     assert_equal(X[obs_idx:, var_idx], csc_disk[obs_idx][:, var_idx])


def test_backed_indexing(ondisk_equivalent_adata, subset_func, subset_func2):
    csr_mem, csr_disk, csc_disk, dense_disk = ondisk_equivalent_adata

    obs_idx = subset_func(csr_mem.obs_names)
    var_idx = subset_func2(csr_mem.var_names)

    assert_equal(csr_mem[obs_idx, var_idx].X, csr_disk[obs_idx, var_idx].X)
    assert_equal(csr_mem[obs_idx, var_idx].X, csc_disk[obs_idx, var_idx].X)
    assert_equal(csr_mem[obs_idx, :].X, dense_disk[obs_idx, :].X)
    assert_equal(csr_mem[:, var_idx].X, dense_disk[:, var_idx].X)


@pytest.mark.parametrize(
    ["sparse_format", "append_method"],
    [
        pytest.param(sparse.csr_matrix, sparse.vstack),
        pytest.param(sparse.csc_matrix, sparse.hstack),
    ],
)
def test_dataset_append_memory(tmp_path, sparse_format, append_method):
    h5_path = tmp_path / "test.h5"
    a = sparse_format(sparse.random(100, 100))
    b = sparse_format(sparse.random(100, 100))

    with h5py.File(h5_path, "a") as f:
        ad._io.specs.write_elem(f, "mtx", a)
        diskmtx = SparseDataset(f["mtx"])

        diskmtx.append(b)
        fromdisk = diskmtx.to_memory()

    frommem = append_method([a, b])

    assert_equal(fromdisk, frommem)


@pytest.mark.parametrize(
    ["sparse_format", "append_method"],
    [
        pytest.param(sparse.csr_matrix, sparse.vstack),
        pytest.param(sparse.csc_matrix, sparse.hstack),
    ],
)
def test_dataset_append_disk(tmp_path, sparse_format, append_method):
    h5_path = tmp_path / "test.h5"
    a = sparse_format(sparse.random(10, 10))
    b = sparse_format(sparse.random(10, 10))

    with h5py.File(h5_path, "a") as f:
        ad._io.specs.write_elem(f, "a", a)
        ad._io.specs.write_elem(f, "b", b)
        a_disk = SparseDataset(f["a"])
        b_disk = SparseDataset(f["b"])

        a_disk.append(b_disk)
        fromdisk = a_disk.to_memory()

    frommem = append_method([a, b])

    assert_equal(fromdisk, frommem)


@pytest.mark.parametrize(
    ["sparse_format", "a_shape", "b_shape"],
    [
        pytest.param("csr", (100, 100), (100, 200)),
        pytest.param("csc", (100, 100), (200, 100)),
    ],
)
def test_wrong_shape(tmp_path, sparse_format, a_shape, b_shape):
    h5_path = tmp_path / "base.h5"
    a_mem = sparse.random(*a_shape, format=sparse_format)
    b_mem = sparse.random(*b_shape, format=sparse_format)

    with h5py.File(h5_path, "a") as f:
        ad._io.specs.write_elem(f, "a", a_mem)
        ad._io.specs.write_elem(f, "b", b_mem)
        a_disk = SparseDataset(f["a"])
        b_disk = SparseDataset(f["b"])

        with pytest.raises(AssertionError):
            a_disk.append(b_disk)


def test_wrong_formats(tmp_path):
    h5_path = tmp_path / "base.h5"
    base = sparse.random(100, 100, format="csr")

    with h5py.File(h5_path, "a") as f:
        ad._io.specs.write_elem(f, "base", base)
        disk_mtx = SparseDataset(f["base"])
        pre_checks = disk_mtx.to_memory()

        with pytest.raises(ValueError):
            disk_mtx.append(sparse.random(100, 100, format="csc"))
        with pytest.raises(ValueError):
            disk_mtx.append(sparse.random(100, 100, format="coo"))
        with pytest.raises(NotImplementedError):
            disk_mtx.append(np.random.random((100, 100)))
        disk_dense = f.create_dataset("dense", data=np.random.random((100, 100)))
        with pytest.raises(NotImplementedError):
            disk_mtx.append(disk_dense)

        post_checks = disk_mtx.to_memory()

    # Check nothing changed
    assert not np.any((pre_checks != post_checks).toarray())
