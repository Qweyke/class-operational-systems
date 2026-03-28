import sys
import os
import struct
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QLabel,
)
from PySide6.QtCore import Qt

from file_sys import MAX_FILES, ENTRY_SIZE, NAME_SIZE


class FSGui(QMainWindow):
    def __init__(self, fs_core):
        super().__init__()
        self.fs = fs_core  # CustomFS object
        self.current_dir_offset = 0
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Custom File System Manager - Advanced")
        self.setMinimumSize(800, 500)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Image Info
        self.path_label = QLabel(f"FS Image: {self.fs.image_path}")
        self.main_layout.addWidget(self.path_label)

        # File List
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("font-family: 'Courier New';")
        self.main_layout.addWidget(self.file_list)

        # Button Rows
        self.row1 = QHBoxLayout()
        self.row2 = QHBoxLayout()

        # Row 1: Basic File Ops
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_import = QPushButton("Import File")
        self.btn_export = QPushButton("Export File")
        self.btn_move = QPushButton("Move to Dir")

        # Row 2: Directory & Meta Ops
        self.btn_mkdir = QPushButton("Create Directory")
        self.btn_rename = QPushButton("Rename Item")
        self.btn_delete_file = QPushButton("Delete File")
        self.btn_delete_dir = QPushButton("Delete Dir (Recursive)")
        self.btn_back = QPushButton("Back to Root")
        self.row2.addWidget(self.btn_back)

        # Adding to layouts
        for btn in [self.btn_refresh, self.btn_import, self.btn_export, self.btn_move]:
            self.row1.addWidget(btn)
        for btn in [
            self.btn_mkdir,
            self.btn_rename,
            self.btn_delete_file,
            self.btn_delete_dir,
        ]:
            self.row2.addWidget(btn)

        self.main_layout.addLayout(self.row1)
        self.main_layout.addLayout(self.row2)

        # Connections
        self.btn_refresh.clicked.connect(self.update_list)
        self.btn_import.clicked.connect(self.handle_import)
        self.btn_export.clicked.connect(self.handle_export)
        self.btn_move.clicked.connect(self.handle_move)
        self.btn_mkdir.clicked.connect(self.handle_mkdir)
        self.btn_rename.clicked.connect(self.handle_rename)
        self.btn_delete_file.clicked.connect(self.handle_delete_file)
        self.btn_delete_dir.clicked.connect(self.handle_delete_dir)
        self.btn_back.clicked.connect(self.go_to_root)
        self.file_list.itemDoubleClicked.connect(self.handle_double_click)

        self.update_list()

    def handle_double_click(self, item):
        raw_text = item.text()
        if "|" not in raw_text or "---" in raw_text:
            return

        # Важно: в update_list ты выводишь "DIR", а не "[DIR]"
        name = raw_text.split("|")[0].strip()
        is_dir = "DIR" in raw_text.split("|")[1]

        if not is_dir:
            return

        try:
            with open(self.fs.image_path, "rb") as f:
                header = f.read(8)
                _, bitmap_size = struct.unpack("<II", header)

                # Ищем папку в текущей таблице
                f.seek(8 + bitmap_size + self.current_dir_offset)
                for _ in range(MAX_FILES):
                    data = f.read(ENTRY_SIZE)
                    is_used, f_type, e_name, start, end = struct.unpack(
                        f"<BB{NAME_SIZE}sII", data
                    )
                    if is_used and e_name.decode("ascii").strip("\x00") == name:
                        # Смещение = Таблица Root (416 байт) + Начало в Data Area
                        self.current_dir_offset = (MAX_FILES * ENTRY_SIZE) + start
                        self.update_list()
                        return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Navigation error: {e}")

    def go_to_root(self):
        """Exit sub-directory and return to Root"""
        self.current_dir_offset = 0
        self.update_list()

    def show_directory_contents(self, dir_name):
        """Helper to list files inside a specific directory's block"""
        # 1. Find dir start address in FS
        # 2. Read ENTRY_SIZE * MAX_FILES from that address
        # 3. Display in a new QMessageBox or update the main list
        QMessageBox.information(self, "Folder Content", f"Opening {dir_name}...")

    def handle_import(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import File")
        if file_path:
            # ПЕРЕДАЕМ self.current_dir_offset
            if self.fs.copy_in(file_path, target_offset=self.current_dir_offset):
                self.update_list()
            else:
                QMessageBox.critical(
                    self, "Error", "Could not import file (no space or table full)."
                )

    def handle_export(self):
        filename, is_dir = self.get_selection()
        if filename and not is_dir:
            save_path, _ = QFileDialog.getSaveFileName(self, "Export File", filename)
            if save_path:
                # ПЕРЕДАЕМ ОФФСЕТ ТУТ:
                if self.fs.copy_out(
                    filename, save_path, offset=self.current_dir_offset
                ):
                    QMessageBox.information(self, "Success", f"Exported to {save_path}")
                else:
                    QMessageBox.critical(self, "Error", "Export failed.")
        elif is_dir:
            QMessageBox.warning(
                self, "Export", "Directories cannot be exported directly."
            )

    def get_selection(self):
        item = self.file_list.currentItem()
        if not item or "|" not in item.text() or "---" in item.text():
            return None, None
        parts = item.text().split("|")
        name = parts[0].strip()
        # Исправлено: ищем "DIR", так как скобок [] в списке нет
        is_dir = "DIR" in parts[1]
        return name, is_dir

    def update_list(self):
        self.file_list.clear()

        # Consistent header formatting
        loc = "Root" if self.current_dir_offset == 0 else "Sub"
        header = f"[{loc:^4}] {'Name':<16} | {'Type':<6} | {'Size':<6} | {'Range'}"
        self.file_list.addItem(header)
        # Increased dashes to match the longer header
        self.file_list.addItem("-" * 70)

        try:
            with open(self.fs.image_path, "rb") as f:

                fs_size, bitmap_size = struct.unpack("<II", f.read(8))

                f.seek(8 + bitmap_size + self.current_dir_offset)

                for _ in range(MAX_FILES):
                    data = f.read(ENTRY_SIZE)
                    if not data:
                        break
                    is_used, f_type, name, start, end = struct.unpack(
                        f"<BB{NAME_SIZE}sII", data
                    )

                    if is_used:
                        clean_name = name.decode("ascii").strip("\x00")
                        type_str = "DIR" if f_type == 1 else "FILE"
                        size = end - start
                        # Use fixed widths for all columns to keep pipes aligned
                        self.file_list.addItem(
                            f"       {clean_name:<16} | {type_str:<6} | {size:<6} | {start}-{end}"
                        )
        except Exception as e:
            print(f"UI Update Error: {e}")

    def handle_mkdir(self):
        dir_name, ok = QInputDialog.getText(self, "New Directory", "Enter name:")
        if ok and dir_name:
            if self.fs.mkdir(dir_name, offset=self.current_dir_offset):
                self.update_list()
            else:
                QMessageBox.critical(self, "Error", "Directory table full or no space.")

    def handle_move(self):
        """Move selected file to a target directory"""
        filename, is_dir = self.get_selection()
        if filename and not is_dir:
            target_dir, ok = QInputDialog.getText(
                self, "Move File", "Enter target directory name:"
            )
            if ok and target_dir:
                self.fs.move(filename, target_dir)
                self.update_list()
        elif is_dir:
            QMessageBox.warning(self, "Move", "Select a FILE to move, not a directory.")

    def handle_rename(self):
        old_name, _ = self.get_selection()
        if old_name:
            new_name, ok = QInputDialog.getText(self, "Rename", f"New name:")
            if ok and new_name:
                self.fs.rename(old_name, new_name, offset=self.current_dir_offset)
                self.update_list()

    def handle_delete_file(self):
        name, is_dir = self.get_selection()
        if name and not is_dir:
            if QMessageBox.question(self, "Delete", "Sure?") == QMessageBox.Yes:
                self.fs.delete_file(name, offset=self.current_dir_offset)
                self.update_list()

    def handle_delete_dir(self):
        name, is_dir = self.get_selection()
        if name and is_dir:
            msg = f"Delete directory {name} AND ALL ITS CONTENTS?"
            if QMessageBox.question(self, "Recursive Delete", msg) == QMessageBox.Yes:
                # Передаем текущее смещение, чтобы поиск шел в нужной таблице
                self.fs.delete_directory(name, offset=self.current_dir_offset)
                self.update_list()
        else:
            QMessageBox.warning(self, "Delete", "Please select a DIRECTORY.")


def start_gui(fs_object):
    app = QApplication(sys.argv)
    gui = FSGui(fs_object)
    gui.show()
    sys.exit(app.exec())
