"""Which processors a process of ours may run on (2026-10-12).

Why: on the owner's PC (a Core Ultra 7 265K: eight performance cores, logical 0, 1, 6, 7, 8, 9, 18, 19, and twelve
efficiency cores) a thread pushed off an EFFICIENCY core in mid-work now and then came back a few instructions early
and the process died with no traceback (RESULTS 2026-10-12 13:00). A process on a performance core never died of it.
A process pinned alone to an efficiency core is safer than a free one but not safe: 0 dead in 120 one-minute jobs, 3
dead in 20 jobs of 17 minutes the same afternoon. So: the performance cores for everything that matters
(`pin_mask(0xC03C3)`), an efficiency core only for a job that is watched and started again when it dies.

    import pin
    pin.pin_mask(0xC03C3)      # this process (and the children it starts from now on) on a set of processors
    pin.pin_self(12)           # ... on one processor
    Pool(n, initializer=pin.pin_pool_worker)     # each worker of a pool on a processor of its own, from PIN_CORES

PIN_CORES in the environment: a list of processors ("2,3,4,5,10,11"); the pool's k-th worker takes the k-th, round and
round, so a pool must not have more workers than the list has processors. Unset: nothing is done.
PIN_OFF=1 switches all of it off. Windows only; elsewhere nothing is done. Never raises."""
import os


def _k32():
    import ctypes
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p             # (default types cut the handle on 64-bit Python and fail silently)
    k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    k.SetProcessAffinityMask.restype = ctypes.c_int
    return k


def pin_mask(mask):
    """this process may run on the processors of mask only; True if Windows took it"""
    if os.name != "nt" or os.environ.get("PIN_OFF") == "1":
        return False
    try:
        k = _k32()
        return bool(k.SetProcessAffinityMask(k.GetCurrentProcess(), int(mask)))
    except Exception:                                        # noqa: BLE001
        return False


def pin_self(i):
    """this process on processor i (modulo the count); returns the processor or -1"""
    c = int(i) % (os.cpu_count() or 1)
    return c if pin_mask(1 << c) else -1


def pin_pool_worker():
    """a pool's initializer: the k-th worker on the k-th processor of PIN_CORES; returns the processor or -1"""
    cores = [int(x) for x in (os.environ.get("PIN_CORES") or "").replace(" ", "").split(",") if x != ""]
    if not cores:
        return -1
    try:
        import multiprocessing
        k = (multiprocessing.current_process()._identity or (1,))[0] - 1
    except Exception:                                        # noqa: BLE001
        k = os.getpid() // 4
    return pin_self(cores[k % len(cores)])
