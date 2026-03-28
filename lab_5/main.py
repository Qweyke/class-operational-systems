import os
from test_case import create_tests

from file_sys import CustomFS
from gui import start_gui

PATH = "lab_5/lab5_fs.img"

if __name__ == "__main__":
    fs = CustomFS(PATH)

    create_tests()
    # if not os.path.exists("lab5_fs.img"):
    fs.format(2048)

    start_gui(fs)
