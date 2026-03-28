import os

PATH = "lab_5/test_files"


def create_tests():
    os.makedirs(PATH, exist_ok=True)

    with open(f"{PATH}/short.txt", "w") as f:
        f.write("Hello from Host OS!")

    with open(f"{PATH}/binary.dat", "wb") as f:
        f.write(os.urandom(256))  # 256 random bytes

    with open(f"{PATH}/this_is_a_very_long_filename_to_test_truncation.txt", "w") as f:
        f.write("Name test")

    print(f"Test files generated in {PATH} folder.")
