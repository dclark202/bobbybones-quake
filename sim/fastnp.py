"""The server's frame budget (2026-10-30): numpy's np.linalg.norm and np.stack without their Python layers, for the small
arrays of one frame. Each gives the same numbers (the same sums in the same order), dtype and C layout as numpy's own:
the server's inputs and network are checked bit for bit against the code before it (docs/guides/FRAME_BUDGET.md)."""
import numpy as np

_SQRT, _ADD_REDUCE, _ARRAY, _CONTIG = np.sqrt, np.add.reduce, np.array, np.ascontiguousarray
_NDARRAY = np.ndarray


def norm(x, axis=None):
    """np.linalg.norm(x) or np.linalg.norm(x, axis=k) (ord None, no keepdims): numpy's own fast cases for a real float
    array (sqrt(x.dot(x)) of the flattened array; sqrt(add.reduce(x * x, axis))), anything else to numpy"""
    if type(x) is not _NDARRAY:
        x = np.asarray(x)
    if x.dtype.kind != "f" or (type(axis) is tuple and len(axis) != 1):
        return np.linalg.norm(x, axis=axis)
    if axis is None:
        x = x.ravel(order="K")
        return _SQRT(x.dot(x))
    return _SQRT(_ADD_REDUCE(x * x, axis=axis))


def stack(arrays, axis=0):
    """np.stack(arrays, axis) for arrays of one shape: np.array of the list (the same values and dtype), the new axis
    moved into place and the result made C-contiguous as np.stack's is"""
    a = _ARRAY(arrays if type(arrays) is list or type(arrays) is tuple else list(arrays))
    if axis == 0:
        return a
    if a.ndim == 2 and axis in (1, -1):
        return _CONTIG(a.T)
    return _CONTIG(np.moveaxis(a, 0, axis))
