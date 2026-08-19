# Python Performance

Python 3.12 improved the bytecode interpreter with specialized instructions, giving 10-25%
speedups. The GIL (Global Interpreter Lock) prevents true multi-threaded CPU parallelism;
use multiprocessing or async I/O instead. NumPy vectorizes operations by delegating to compiled
C routines. `__slots__` reduce memory for classes with many instances. f-strings are faster
than %-formatting and .format(). Profiling with cProfile shows per-function call counts and
cumulative time. Cython and Numba can JIT-compile hot loops.
