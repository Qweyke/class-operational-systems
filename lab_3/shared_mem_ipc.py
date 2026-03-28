import multiprocessing
import math
import matplotlib.pyplot as plt
import numpy as np


def process_1(shared_x, ready_p1):
    """Generates X values and stores them in shared memory."""
    x_range = np.arange(-10, 10.1, 0.1)
    for i, val in enumerate(x_range):
        shared_x[i] = val
    ready_p1.set()  # Notify P2 that X values are ready


def process_2(shared_x, shared_y, ready_p1, ready_p2):
    """Calculates Y values once X is ready."""
    ready_p1.wait()
    for i in range(len(shared_x)):
        shared_y[i] = math.sin(shared_x[i])
    ready_p2.set()  # Notify P3 that Y values are ready


def process_3(shared_x, shared_y, ready_p2):
    """Plots the graph once data is fully processed."""
    ready_p2.wait()
    # Convert shared memory to list for plotting
    plt.plot(list(shared_x), list(shared_y), color="red", label="y = sin(x)")
    plt.title("IPC via Shared Memory (Assignment 2)")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    size = int((10 - (-10)) / 0.1) + 1

    # Shared arrays ('d' for double precision)
    shared_x = multiprocessing.Array("d", size)
    shared_y = multiprocessing.Array("d", size)

    # Synchronization events
    ready_p1 = multiprocessing.Event()
    ready_p2 = multiprocessing.Event()

    p1 = multiprocessing.Process(target=process_1, args=(shared_x, ready_p1))
    p2 = multiprocessing.Process(
        target=process_2, args=(shared_x, shared_y, ready_p1, ready_p2)
    )
    p3 = multiprocessing.Process(target=process_3, args=(shared_x, shared_y, ready_p2))

    processes = [p1, p2, p3]
    for p in processes:
        p.start()
    for p in processes:
        p.join()
