import socket
import os
import math
import struct
import multiprocessing
import time
import matplotlib.pyplot as plt

SOCKET_P1_P2 = "/tmp/socket_p1_p2"
SOCKET_P2_P3 = "/tmp/socket_p2_p3"


def process_1(left_x=-10, right_x=10, step=0.1):
    """Generates X values and sends them to Process 2."""
    if os.path.exists(SOCKET_P1_P2):
        os.remove(SOCKET_P1_P2)

    # Setup server
    x_gen_server = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
    x_gen_server.bind(SOCKET_P1_P2)
    x_gen_server.listen(1)

    # Connection and sending
    conn, _ = x_gen_server.accept()
    x = left_x
    while x <= right_x:
        # Pack to 4-bytes struct of float-type
        conn.sendall(struct.pack("f", x))
        x += step
    conn.close()
    x_gen_server.close()


def process_2():
    """Reads X, calculates Y = sin(X), and sends (X, Y) to Process 3."""
    # Connect to P1
    x_receive_client = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
    while True:  # Wait for P1 to be ready
        try:
            x_receive_client.connect(SOCKET_P1_P2)
            break
        except (ConnectionRefusedError, FileNotFoundError):
            time.sleep(0.1)
            pass

    # Server for P3
    if os.path.exists(SOCKET_P2_P3):
        os.remove(SOCKET_P2_P3)
    xy_send_server = socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM)
    xy_send_server.bind(SOCKET_P2_P3)
    xy_send_server.listen(1)

    conn, _ = xy_send_server.accept()

    while True:
        data = x_receive_client.recv(4)
        if not data:
            break
        x = struct.unpack("f", data)[0]
        y = math.sin(x)
        conn.sendall(struct.pack("ff", x, y))

    conn.close()
    xy_send_server.close()
    x_receive_client.close()


def process_3():
    """Reads (X, Y) pairs and plots the graph."""
    xy_receive_client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    while True:
        try:
            xy_receive_client.connect(SOCKET_P2_P3)
            break
        except (ConnectionRefusedError, FileNotFoundError):
            time.sleep(0.1)
            pass

    x_values = []
    y_values = []

    while True:
        data = xy_receive_client.recv(8)
        if not data:
            break
        x, y = struct.unpack("ff", data)
        x_values.append(x)
        y_values.append(y)

    xy_receive_client.close()

    plt.plot(x_values, y_values, label="y = sin(x)")
    plt.title("IPC via Sockets (Assignment 1)")
    plt.grid(True)
    plt.legend()
    plt.show()


if __name__ == "__main__":
    p1 = multiprocessing.Process(target=process_1)
    p2 = multiprocessing.Process(target=process_2)
    p3 = multiprocessing.Process(target=process_3)

    p3.start()
    p2.start()
    p1.start()

    p1.join()
    p2.join()
    p3.join()
