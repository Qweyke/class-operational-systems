import struct
import os

CLUSTER_SIZE = 1  # 1 cluster = 1 byte
MAX_FILES = 16  # Max 16 files per directory

# One dir-entry size
NAME_SIZE = 16  # Filename length
ENTRY_SIZE = 1 + 1 + NAME_SIZE + 4 + 4  # Directory entry size

BITS_IN_BYTE = 8


class CustomFS:
    def __init__(self, image_path):
        self.image_path = image_path

    def format(self, size_in_clusters):
        """Creates a new FS image"""

        # We need the byte-size to cover all bits, so add (BITS_IN_BYTE - 1) to keep this condition
        bitmap_size = (size_in_clusters + (BITS_IN_BYTE - 1)) // BITS_IN_BYTE
        # Pack header
        header = struct.pack("<II", size_in_clusters, bitmap_size)

        bitmap = b"\x00" * bitmap_size
        root_dir = b"\x00" * (ENTRY_SIZE * MAX_FILES)

        with open(self.image_path, "wb") as f:
            f.write(header)
            f.write(bitmap)
            f.write(root_dir)
            # Fill data area with zeros
            f.write(b"\x00" * size_in_clusters)

    def list_dir1(self):
        """View directory contents"""
        with open(self.image_path, "rb") as f:
            # Read header to find offset
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))
            print(f"\nCustom file system ({fs_size})")
            f.seek(8 + bitmap_size)

            splitter_str = f"{'Name':<16} | {'Type':<10} | {'Start':<6} | {'End':<6}"
            print(splitter_str)
            print("-" * (len(splitter_str) - 2))

            for _ in range(MAX_FILES):
                data = f.read(ENTRY_SIZE)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", data
                )

                if is_used:
                    name_str = name.decode("ascii").strip("\x00")
                    type_str = "DIR" if f_type == 1 else "FILE"
                    print(f"{name_str:<16} | {type_str:<10} | {start:<6} | {end:<6}")

    def copy_in(self, host_file_path):
        """Copy file from host OS to FS image"""
        # 1. Read the source file from your PC
        filename = os.path.basename(host_file_path)[:16]
        with open(host_file_path, "rb") as hf:
            content = hf.read()
            file_size = len(content)

        with open(
            self.image_path, "r+b"
        ) as f:  # Open for random access reading/writing
            # 2. Read FS metadata to know where everything is
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 3. Read the bitmap and find continuous free space
            f.seek(8)
            bitmap = bytearray(f.read(bitmap_size))

            # Convert bitmap to a string of bits for easier searching
            bits = "".join(f"{byte:08b}"[::-1] for byte in bitmap)
            free_space_idx = bits.find("0" * file_size)

            if free_space_idx == -1 or free_space_idx + file_size > fs_size:
                print("Error: Not enough continuous space")
                return

            # 4. Find an empty slot in the root directory (16 entries)
            f.seek(8 + bitmap_size)
            dir_offset = 8 + bitmap_size
            entry_index = -1

            for i in range(MAX_FILES):
                entry_data = f.read(ENTRY_SIZE)
                # Check status byte (first byte of entry)
                if struct.unpack("<B", entry_data[:1])[0] == 0:
                    entry_index = i
                    break

            if entry_index == -1:
                print("Error: Directory is full (max 16 files)")
                return

            # 5. Write the file data to the Data Area
            # Data Area starts after Header + Bitmap + Directory (416 bytes)
            data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
            f.seek(data_area_start + free_space_idx)
            f.write(content)

            # 6. Update the Bitmap
            for i in range(free_space_idx, free_space_idx + file_size):
                byte_idx = i // 8
                bit_idx = i % 8
                bitmap[byte_idx] |= 1 << bit_idx

            f.seek(8)
            f.write(bitmap)

            # 7. Write the directory entry
            f.seek(dir_offset + (entry_index * ENTRY_SIZE))
            # Format: Status(1), Type(0 for file), Name(16s), Start(I), End(I)
            new_entry = struct.pack(
                f"<BB{NAME_SIZE}sII",
                1,
                0,
                filename.encode("ascii"),
                free_space_idx,
                free_space_idx + file_size,
            )
            f.write(new_entry)
            print(f"File '{filename}' copied successfully!")

    def copy_out(self, filename_in_fs, host_dest_path):
        """Copy file from FS image to your computer"""
        with open(self.image_path, "rb") as f:
            # 1. Read metadata to calculate offsets
            _, bitmap_size = struct.unpack("<II", f.read(8))

            # 2. Search for the file in the Root Directory
            f.seek(8 + bitmap_size)
            file_found = False
            start_addr = 0
            end_addr = 0

            for i in range(MAX_FILES):
                entry_data = f.read(ENTRY_SIZE)
                # Unpack the entry: status, type, name, start, end
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )

                # Clean the name from null bytes and compare
                clean_name = name.decode("ascii").strip("\x00")
                if is_used and clean_name == filename_in_fs:
                    file_found = True
                    start_addr = start
                    end_addr = end
                    break

            if not file_found:
                print(f"Error: File '{filename_in_fs}' not found in FS")
                return

            # 3. Read the data from the Data Area
            # Data Area offset = Header + Bitmap + RootDir (416 bytes)
            data_area_offset = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
            f.seek(data_area_offset + start_addr)

            # The size is end_addr - start_addr
            file_content = f.read(end_addr - start_addr)

            # 4. Save to the host OS
            with open(host_dest_path, "wb") as host_file:
                host_file.write(file_content)

            print(
                f"File '{filename_in_fs}' exported to '{host_dest_path}' successfully!"
            )

    def list_dir(self):
        """View directory contents"""
        with open(self.image_path, "rb") as f:
            # 1. Read header to calculate the offset of the directory
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 2. Move to the start of the Root Directory
            # Header(8) + Bitmap(bitmap_size)
            f.seek(8 + bitmap_size)

            print(f"{'Name':<16} | {'Type':<6} | {'Size (B)':<8} | {'Range'}")
            print("-" * 50)

            files_found = 0
            for _ in range(MAX_FILES):
                entry_data = f.read(ENTRY_SIZE)
                # Unpack: Status(B), Type(B), Name(16s), Start(I), End(I)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )

                # If the status byte is 1, the slot is occupied
                if is_used:
                    files_found += 1
                    clean_name = name.decode("ascii").strip("\x00")
                    type_str = "DIR" if f_type == 1 else "FILE"
                    size = end - start
                    print(
                        f"{clean_name:<16} | {type_str:<6} | {size:<8} | {start}-{end}"
                    )

            if files_found == 0:
                print("Directory is empty.")

    def delete_file(self, filename):
        """Delete a file by marking its space and entry as free"""
        with open(self.image_path, "r+b") as f:
            # 1. Basic FS info
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 2. Find file in directory
            f.seek(8 + bitmap_size)
            dir_offset = 8 + bitmap_size
            found = False

            for i in range(MAX_FILES):
                current_entry_pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )

                clean_name = name.decode("ascii").strip("\x00")
                if is_used and clean_name == filename and f_type == 0:
                    # 3. Clear bitmap bits
                    f.seek(8)
                    bitmap = bytearray(f.read(bitmap_size))
                    for bit_idx in range(start, end):
                        byte_pos = bit_idx // 8
                        bit_pos = bit_idx % 8
                        bitmap[byte_pos] &= ~(1 << bit_pos)  # Set bit to 0

                    f.seek(8)
                    f.write(bitmap)

                    # 4. Mark directory entry as free (Status = 0)
                    f.seek(current_entry_pos)
                    f.write(b"\x00")

                    print(f"File '{filename}' deleted.")
                    found = True
                    break

            if not found:
                print(f"Error: File '{filename}' not found.")

    def delete_directory(self, dirname):
        """Delete a directory and all its contents"""
        with open(self.image_path, "r+b") as f:
            # 1. Read metadata
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 2. Find the directory entry in Root
            f.seek(8 + bitmap_size)
            dir_offset = 8 + bitmap_size
            found = False

            for i in range(MAX_FILES):
                current_entry_pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )

                clean_name = name.decode("ascii").strip("\x00")

                # Check if it's a used entry, matches name, and is a DIRECTORY (type 1)
                if is_used and clean_name == dirname and f_type == 1:
                    found = True

                    # 3. Read the content of the directory (its own table of files)
                    data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
                    f.seek(data_area_start + start)
                    sub_dir_data = f.read(end - start)

                    # 4. Load bitmap to modify it
                    f.seek(8)
                    bitmap = bytearray(f.read(bitmap_size))

                    # 5. Internal logic: Free all files inside this directory
                    # We treat the sub_dir_data as a sequence of ENTRY_SIZE blocks
                    for j in range(0, len(sub_dir_data), ENTRY_SIZE):
                        sub_entry = sub_dir_data[j : j + ENTRY_SIZE]
                        if len(sub_entry) < ENTRY_SIZE:
                            break

                        s_used, s_type, s_name, s_start, s_end = struct.unpack(
                            f"<BB{NAME_SIZE}sII", sub_entry
                        )

                        if s_used:
                            # Free space of the nested file in bitmap
                            for bit_idx in range(s_start, s_end):
                                bitmap[bit_idx // 8] &= ~(1 << (bit_idx % 8))

                    # 6. Free the directory's own space in bitmap
                    for bit_idx in range(start, end):
                        bitmap[bit_idx // 8] &= ~(1 << (bit_idx % 8))

                    # 7. Save updated bitmap
                    f.seek(8)
                    f.write(bitmap)

                    # 8. Mark the directory entry in the parent as free
                    f.seek(current_entry_pos)
                    f.write(b"\x00")

                    print(f"Directory '{dirname}' and all its contents deleted.")
                    break

            if not found:
                print(f"Error: Directory '{dirname}' not found.")

    def rename(self, old_name, new_name):
        """Rename a file or directory"""
        # Ensure new name fits in 16 bytes
        new_name_encoded = new_name.encode("ascii")[:16]

        with open(self.image_path, "r+b") as f:
            _, bitmap_size = struct.unpack("<II", f.read(8))
            f.seek(8 + bitmap_size)

            for _ in range(MAX_FILES):
                current_entry_pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )

                clean_name = name.decode("ascii").strip("\x00")
                if is_used and clean_name == old_name:
                    # Jump to the name field (+2 bytes from start of entry)
                    f.seek(current_entry_pos + 2)
                    # Write new name padded with null bytes to reach 16 bytes
                    f.write(new_name_encoded.ljust(16, b"\x00"))
                    print(f"Renamed '{old_name}' to '{new_name}'")
                    return

            print(f"Error: '{old_name}' not found.")

    def move(self, filename, target_dir_name):
        """Move a file from root to a subdirectory (simplified)"""
        with open(self.image_path, "r+b") as f:
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))
            dir_offset = 8 + bitmap_size

            # 1. Find the file to move and its data
            file_entry = None
            old_entry_pos = -1

            f.seek(dir_offset)
            for _ in range(MAX_FILES):
                pos = f.tell()
                data = f.read(ENTRY_SIZE)
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", data
                )
                if is_used and name.decode("ascii").strip("\x00") == filename:
                    file_entry = data
                    old_entry_pos = pos
                    break

            # 2. Find the target directory
            f.seek(dir_offset)
            target_dir_start = -1
            for i in range(MAX_FILES):
                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", f.read(ENTRY_SIZE)
                )
                if (
                    is_used
                    and f_type == 1
                    and name.decode("ascii").strip("\x00") == target_dir_name
                ):
                    target_dir_start = start
                    break

            if file_entry and target_dir_start != -1:
                # 3. Paste entry into target directory's data block
                data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
                f.seek(data_area_start + target_dir_start)

                # Look for empty slot inside target directory
                inserted = False
                for _ in range(MAX_FILES):
                    slot_pos = f.tell()
                    if struct.unpack("<B", f.read(1))[0] == 0:
                        f.seek(slot_pos)
                        f.write(file_entry)
                        inserted = True
                        break

                if inserted:
                    # 4. Clear the old entry in root
                    f.seek(old_entry_pos)
                    f.write(b"\x00")
                    print(f"Moved '{filename}' to '{target_dir_name}'")
                else:
                    print("Error: Target directory is full.")
            else:
                print("Error: File or Target Directory not found.")


# Example usage
fs = CustomFS("lab5_fs.img")
fs.format(1024)  # Create 1KB filesystem
fs.list_dir()
