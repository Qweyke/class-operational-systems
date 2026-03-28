import struct
import os

CLUSTER_SIZE = 1  # 1 cluster = 1 byte
MAX_FILES = 16  # Max 16 files per directory

# Размеры структур
NAME_SIZE = 16  # Длина имени
ENTRY_SIZE = 1 + 1 + NAME_SIZE + 4 + 4  # 26 байт (Status + Type + Name + Start + End)
BITS_IN_BYTE = 8


class CustomFS:
    def __init__(self, image_path):
        self.image_path = image_path

    def format(self, size_in_clusters):
        """Создает новый образ ФС"""
        bitmap_size = (size_in_clusters + (BITS_IN_BYTE - 1)) // BITS_IN_BYTE
        header = struct.pack("<II", size_in_clusters, bitmap_size)
        bitmap = b"\x00" * bitmap_size
        root_dir = b"\x00" * (ENTRY_SIZE * MAX_FILES)

        with open(self.image_path, "wb") as f:
            f.write(header)
            f.write(bitmap)
            f.write(root_dir)
            f.write(b"\x00" * size_in_clusters)

    def copy_in(self, host_file_path, target_offset=0):
        """Копирует файл из ОС в текущую папку (target_offset)"""
        filename = os.path.basename(host_file_path)[:16]
        with open(host_file_path, "rb") as hf:
            content = hf.read()
            file_size = len(content)

        with open(self.image_path, "r+b") as f:
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 1. Поиск места в битмапе
            f.seek(8)
            bitmap = bytearray(f.read(bitmap_size))
            bits = "".join(f"{byte:08b}"[::-1] for byte in bitmap)
            free_idx = bits.find("0" * file_size)

            if free_idx == -1:
                print("Error: No space in Data Area")
                return False

            # 2. Поиск пустого слота в ТЕКУЩЕЙ таблице
            f.seek(8 + bitmap_size + target_offset)
            entry_index = -1
            for i in range(MAX_FILES):
                pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)  # Читаем все 26 байт (ИСПРАВЛЕНО)
                if not entry_data:
                    break
                if struct.unpack("<B", entry_data[:1])[0] == 0:
                    entry_index = i
                    f.seek(pos)  # Возвращаемся в начало найденного слота
                    break

            if entry_index == -1:
                print("Error: Directory table full")
                return False

            # 3. Запись данных файла
            data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
            f.seek(data_area_start + free_idx)
            f.write(content)

            # 4. Обновление битмапа
            for i in range(free_idx, free_idx + file_size):
                bitmap[i // 8] |= 1 << (i % 8)
            f.seek(8)
            f.write(bitmap)

            # 5. Запись метаданных
            # Мы уже сделали seek(pos) в шаге 2
            new_entry = struct.pack(
                f"<BB{NAME_SIZE}sII",
                1,
                0,
                filename.encode("ascii").ljust(16, b"\x00"),
                free_idx,
                free_idx + file_size,
            )
            f.write(new_entry)
            return True

    def mkdir(self, dir_name, offset=0):
        """Создает подпапку в указанном offset"""
        with open(self.image_path, "r+b") as f:
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))
            table_size = MAX_FILES * ENTRY_SIZE

            # 1. Место под таблицу новой папки
            f.seek(8)
            bitmap = bytearray(f.read(bitmap_size))
            bits = "".join(f"{byte:08b}"[::-1] for byte in bitmap)
            free_idx = bits.find("0" * table_size)
            if free_idx == -1:
                return False

            for i in range(free_idx, free_idx + table_size):
                bitmap[i // 8] |= 1 << (i % 8)
            f.seek(8)
            f.write(bitmap)

            # 2. Очистка новой таблицы
            data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
            f.seek(data_area_start + free_idx)
            f.write(b"\x00" * table_size)

            # 3. Запись в текущую таблицу (ИСПРАВЛЕНО)
            f.seek(8 + bitmap_size + offset)
            for i in range(MAX_FILES):
                pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)  # Читаем 26 байт
                if not entry_data:
                    break
                if struct.unpack("<B", entry_data[:1])[0] == 0:
                    f.seek(pos)
                    entry = struct.pack(
                        f"<BB{NAME_SIZE}sII",
                        1,
                        1,
                        dir_name.encode("ascii")[:16].ljust(16, b"\x00"),
                        free_idx,
                        free_idx + table_size,
                    )
                    f.write(entry)
                    return True
        return False

    def rename(self, old_name, new_name, offset=0):
        """Переименовывает объект в текущем offset"""
        with open(self.image_path, "r+b") as f:
            _, bitmap_size = struct.unpack("<II", f.read(8))
            f.seek(8 + bitmap_size + offset)

            for _ in range(MAX_FILES):
                pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)  # Читаем 26 байт (ИСПРАВЛЕНО)
                if not entry_data:
                    break

                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )
                if is_used and name.decode("ascii").strip("\x00") == old_name:
                    f.seek(pos + 2)  # Пропускаем Status и Type
                    f.write(new_name.encode("ascii")[:16].ljust(16, b"\x00"))
                    return True
        return False

    def delete_file(self, filename, offset=0):
        """Удаляет файл в текущем offset"""
        with open(self.image_path, "r+b") as f:
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))
            f.seek(8 + bitmap_size + offset)

            for _ in range(MAX_FILES):
                pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)  # Читаем 26 байт (ИСПРАВЛЕНО)
                if not entry_data:
                    break

                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )
                if (
                    is_used
                    and f_type == 0
                    and name.decode("ascii").strip("\x00") == filename
                ):
                    # Чистим битмап
                    f.seek(8)
                    bitmap = bytearray(f.read(bitmap_size))
                    for bit_idx in range(start, end):
                        bitmap[bit_idx // 8] &= ~(1 << (bit_idx % 8))
                    f.seek(8)
                    f.write(bitmap)

                    # Удаляем запись
                    f.seek(pos)
                    f.write(b"\x00")
                    return True
        return False

    def delete_directory(self, dirname, offset=0):
        """Рекурсивно удаляет папку и её содержимое"""
        with open(self.image_path, "r+b") as f:
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))
            f.seek(8 + bitmap_size + offset)

            for _ in range(MAX_FILES):
                pos = f.tell()
                entry_data = f.read(ENTRY_SIZE)  # Читаем 26 байт (ИСПРАВЛЕНО)
                if not entry_data:
                    break

                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )
                if (
                    is_used
                    and f_type == 1
                    and name.decode("ascii").strip("\x00") == dirname
                ):
                    # 1. Читаем таблицу удаляемой папки
                    data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)
                    f.seek(data_area_start + start)
                    sub_table = f.read(MAX_FILES * ENTRY_SIZE)

                    # 2. Чистим битмап для всех файлов внутри папки
                    f.seek(8)
                    bitmap = bytearray(f.read(bitmap_size))

                    for i in range(0, len(sub_table), ENTRY_SIZE):
                        s_entry = sub_table[i : i + ENTRY_SIZE]
                        if len(s_entry) < ENTRY_SIZE:
                            break
                        s_used, _, _, s_start, s_end = struct.unpack(
                            f"<BB{NAME_SIZE}sII", s_entry
                        )
                        if s_used:
                            for bit in range(s_start, s_end):
                                bitmap[bit // 8] &= ~(1 << (bit % 8))

                    # 3. Чистим саму таблицу папки
                    for bit in range(start, end):
                        bitmap[bit // 8] &= ~(1 << (bit % 8))

                    f.seek(8)
                    f.write(bitmap)

                    # 4. Удаляем запись из родительской таблицы
                    f.seek(pos)
                    f.write(b"\x00")
                    return True
        return False

    def copy_out(self, filename, host_save_path, offset=0):
        """Copies file from FS image to host OS (Export)"""
        with open(self.image_path, "rb") as f:
            # 1. Читаем метаданные, чтобы найти начало Data Area
            f.seek(0)
            fs_size, bitmap_size = struct.unpack("<II", f.read(8))

            # 2. Ищем файл в ТЕКУЩЕЙ таблице (offset)
            f.seek(8 + bitmap_size + offset)

            file_data_info = None
            for _ in range(MAX_FILES):
                entry_data = f.read(ENTRY_SIZE)
                if not entry_data:
                    break

                is_used, f_type, name, start, end = struct.unpack(
                    f"<BB{NAME_SIZE}sII", entry_data
                )
                clean_name = name.decode("ascii").strip("\x00")

                # Проверяем, что это файл (type=0) и имя совпадает
                if is_used and f_type == 0 and clean_name == filename:
                    file_data_info = (start, end)
                    break

            if not file_data_info:
                print(f"Error: File '{filename}' not found at offset {offset}")
                return False

            # 3. Вычисляем физический адрес данных в образе
            start, end = file_data_info
            data_area_start = 8 + bitmap_size + (MAX_FILES * ENTRY_SIZE)

            f.seek(data_area_start + start)
            content = f.read(end - start)

            # 4. Сохраняем на реальный диск
            with open(host_save_path, "wb") as hf:
                hf.write(content)

            print(f"File '{filename}' exported successfully to {host_save_path}")
            return True
