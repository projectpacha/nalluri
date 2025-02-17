from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QMessageBox, QHBoxLayout

class DuplicatesWindow(QDialog):
    def __init__(self, duplicates_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Duplicate Headwords")
        self.setMinimumSize(400, 300)
        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setText(duplicates_text)
        layout.addWidget(self.text_edit)

        # Create a horizontal layout for the action buttons.
        buttons_layout = QHBoxLayout()

        self.merge_button = QPushButton("Merge Duplicates", self)
        self.merge_button.clicked.connect(self.merge_duplicates)
        buttons_layout.addWidget(self.merge_button)

        self.delete_button = QPushButton("Delete Duplicates", self)
        self.delete_button.clicked.connect(self.delete_duplicates)
        buttons_layout.addWidget(self.delete_button)

        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)

        layout.addLayout(buttons_layout)

    def merge_duplicates(self):
        reply = QMessageBox.question(
            self,
            "Confirm Merge",
            "Are you sure you want to merge duplicate entries? This will combine senses and remove duplicate entries.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Assumes that the parent is the main window with a db_manager attribute.
            if hasattr(self.parent(), 'db_manager'):
                try:
                    self.parent().db_manager.merge_duplicates()
                    if hasattr(self.parent(), 'populate_headwords'):
                        self.parent().populate_headwords()
                    QMessageBox.information(self, "Merge Completed", "Duplicate entries have been merged successfully.")
                    self.close()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An error occurred while merging duplicates:\n{e}")
            else:
                QMessageBox.critical(self, "Error", "Database manager not available.")

    def delete_duplicates(self):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete duplicate entries? Only one instance of each duplicate headword will be kept.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if hasattr(self.parent(), 'db_manager'):
                try:
                    self.parent().db_manager.delete_duplicates()
                    if hasattr(self.parent(), 'populate_headwords'):
                        self.parent().populate_headwords()
                    QMessageBox.information(self, "Deletion Completed", "Duplicate entries have been deleted successfully.")
                    self.close()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"An error occurred while deleting duplicates:\n{e}")
            else:
                QMessageBox.critical(self, "Error", "Database manager not available.")
