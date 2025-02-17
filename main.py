import sys, os, logging, difflib, json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QListWidget,
    QPushButton, QMessageBox, QFileDialog, QInputDialog, QMenuBar, QMenu, QStatusBar, QFrame, QShortcut, QSplitter, QComboBox, QCheckBox
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QEvent
from settings import load_settings, save_settings
from database import DatabaseManager
from import_export import ImportExportManager
from duplicates import DuplicatesWindow

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DictionaryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/app_icon.png")))
        self.translations = {}
        self.current_language = "en"
        self.current_theme = "themes/default_style.qss"
        self.current_entry_id = None

        # Create manager instances (pass a status callback and the translations dictionary)
        self.db_manager = DatabaseManager(self.translations, self.update_status)
        self.import_export_manager = ImportExportManager(self.db_manager, self.translations, self.update_status)
        self.duplicates_window = None

        self.initUI()
        settings = load_settings()
        self.change_theme(settings.get("theme", "themes/default_style.qss"))
        self.change_language(settings.get("language", "en"))

    def initUI(self):
        self.setWindowTitle("Nalluri DictMaker")
        self.setGeometry(100, 100, 1280, 800)

        # Menu system
        menubar = self.menuBar()
        self.file_menu = menubar.addMenu("File")
        self.new_db_action = self.file_menu.addAction("New Database", self.create_database)
        self.open_db_action = self.file_menu.addAction("Open Database", self.load_database)
        self.file_menu.addSeparator()
        self.import_csv_action = self.file_menu.addAction("Import CSV", self.import_csv)
        self.export_csv_action = self.file_menu.addAction("Export CSV", self.export_csv)
        self.import_json_action = self.file_menu.addAction("Import JSON", self.import_json)
        self.export_json_action = self.file_menu.addAction("Export JSON", self.export_json)
        self.file_menu.addSeparator()
        self.show_duplicates_action = self.file_menu.addAction("Show Duplicates", self.show_duplicates)
        self.file_menu.addSeparator()
        self.exit_action = self.file_menu.addAction("Exit", self.close)

        self.preferences_menu = menubar.addMenu("Preferences")
        self.theme_menu = self.preferences_menu.addMenu("Theme")
        self.light_theme_action = self.theme_menu.addAction("Light", lambda: self.change_theme("themes/style_light.qss"))
        self.dark_theme_action = self.theme_menu.addAction("Dark", lambda: self.change_theme("themes/style_dark.qss"))
        self.greenlit_theme_action = self.theme_menu.addAction("Greenlit", lambda: self.change_theme("themes/greenlit_style.qss"))
        self.material_theme_action = self.theme_menu.addAction("Material", lambda: self.change_theme("themes/material_style.qss"))
        self.default_theme_action = self.theme_menu.addAction("Default", lambda: self.change_theme("themes/default_style.qss"))

        self.language_menu = self.preferences_menu.addMenu("Language")
        self.english_action = self.language_menu.addAction("English", lambda: self.change_language("en"))
        self.german_action = self.language_menu.addAction("German", lambda: self.change_language("de"))
        self.malayalam_action = self.language_menu.addAction("Malayalam", lambda: self.change_language("ml"))
        self.chinese_action = self.language_menu.addAction("Chinese", lambda: self.change_language("zh"))
        self.arabic_action = self.language_menu.addAction("Arabic", lambda: self.change_language("ar"))
        self.russian_action = self.language_menu.addAction("Russian", lambda: self.change_language("ru"))
        self.japanese_action = self.language_menu.addAction("Japanese", lambda: self.change_language("jp"))
        self.indonesian_action = self.language_menu.addAction("Indonesian", lambda: self.change_language("id"))

        self.help_menu = menubar.addMenu("Help")
        self.keyboard_shortcuts_action = self.help_menu.addAction("Keyboard Shortcuts", self.show_help)
        self.about_action = self.help_menu.addAction("About", self.show_about)

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Search bar
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        self.search_label = QLabel("Search:")
        search_layout.addWidget(self.search_label)
        self.entry_search = QLineEdit()
        self.entry_search.setToolTip(self.translations.get("enter_search", "Enter search term"))
        search_layout.addWidget(self.entry_search)
        self.search_criteria_combo = QComboBox()
        self.search_criteria_combo.addItems([
            self.translations.get("search_all", "All"),
            self.translations.get("headword_label", "Headword"),
            self.translations.get("pos_label", "Part of Speech"),
            self.translations.get("variation_label", "Variation"),
            self.translations.get("meaning_label", "Meaning"),
        ])
        self.search_criteria_combo.setToolTip("Select search criteria")
        search_layout.addWidget(self.search_criteria_combo)
        self.fuzzy_search_checkbox = QCheckBox(self.translations.get("fuzzy_search", "Fuzzy Search"))
        self.fuzzy_search_checkbox.setToolTip(self.translations.get("fuzzy_search_tooltip", "Check for approximate matches"))
        search_layout.addWidget(self.fuzzy_search_checkbox)
        self.search_button = QPushButton("")
        self.search_button.setIcon(QIcon(resource_path("icons/search_icon.png")))
        self.search_button.clicked.connect(self.search_filter)
        search_layout.addWidget(self.search_button)
        main_layout.addWidget(search_frame)

        # Content area
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        splitter = QSplitter(Qt.Horizontal)

        # Left: Headword list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        self.entries_label = QLabel("Entries")
        list_layout.addWidget(self.entries_label)
        self.listbox_headwords = QListWidget()
        self.listbox_headwords.itemClicked.connect(self.display_entry)
        list_layout.addWidget(self.listbox_headwords)
        splitter.addWidget(list_frame)

        # Right: Entry form
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        self.headword_label = QLabel("Headword")
        form_layout.addWidget(self.headword_label)
        self.entry_headword = QLineEdit()
        form_layout.addWidget(self.entry_headword)
        self.variation_label = QLabel("Variation")
        form_layout.addWidget(self.variation_label)
        self.entry_variation = QLineEdit()
        form_layout.addWidget(self.entry_variation)
        self.pos_label = QLabel("Part of Speech")
        form_layout.addWidget(self.pos_label)
        self.entry_pos = QLineEdit()
        form_layout.addWidget(self.entry_pos)
        self.notes_label = QLabel("Notes")
        form_layout.addWidget(self.notes_label)
        self.entry_notes = QLineEdit()
        form_layout.addWidget(self.entry_notes)
        self.meaning_label = QLabel("Meaning")
        form_layout.addWidget(self.meaning_label)
        self.entry_meaning = QTextEdit()
        form_layout.addWidget(self.entry_meaning)

        # Action buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        self.save_button = QPushButton("")
        self.save_button.setIcon(QIcon(resource_path("icons/save_icon.png")))
        self.save_button.setToolTip("Save entry, Ctrl+S")
        self.save_button.clicked.connect(self.save_entry)
        button_layout.addWidget(self.save_button)
        self.new_button = QPushButton("")
        self.new_button.setIcon(QIcon(resource_path("icons/new_icon.png")))
        self.new_button.setToolTip("New entry, Ctrl+N")
        self.new_button.clicked.connect(self.clear_fields)
        button_layout.addWidget(self.new_button)
        self.delete_button = QPushButton("")
        self.delete_button.setIcon(QIcon(resource_path("icons/delete_icon.png")))
        self.delete_button.setToolTip("Delete entry, Ctrl+D")
        self.delete_button.clicked.connect(self.delete_entry)
        button_layout.addWidget(self.delete_button)
        self.duplicates_button = QPushButton("")
        self.duplicates_button.setIcon(QIcon(resource_path("icons/duplicates_icon.png")))
        self.duplicates_button.setToolTip("Check for duplicate entries")
        self.duplicates_button.clicked.connect(self.show_duplicates)
        button_layout.addWidget(self.duplicates_button)
        form_layout.addWidget(button_frame)
        splitter.addWidget(form_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Total Headwords: 0")
        self.status_bar.addPermanentWidget(self.status_label)

        # Initialize last database if available
        self.initialize_last_db()

        # Keyboard shortcuts
        self.add_shortcut(Qt.CTRL + Qt.Key_S, self.save_entry)
        self.add_shortcut(Qt.CTRL + Qt.Key_D, self.delete_entry)
        self.add_shortcut(Qt.CTRL + Qt.Key_F, self.search_filter)
        self.add_shortcut(Qt.CTRL + Qt.Key_N, self.clear_fields)
        self.add_shortcut(Qt.CTRL + Qt.Key_A, self.create_database)
        self.add_shortcut(Qt.CTRL + Qt.Key_O, self.load_database)
        self.add_shortcut(Qt.CTRL + Qt.Key_Q, self.close)

    def add_shortcut(self, key, function):
        shortcut = QShortcut(key, self)
        shortcut.activated.connect(function)

    def initialize_last_db(self):
        last_db = self.db_manager.load_last_db()
        if last_db and os.path.exists(last_db):
            self.db_manager.load_database(self, last_db)
            self.populate_headwords()

    def populate_headwords(self):
        self.listbox_headwords.clear()
        if self.db_manager.conn:
            self.db_manager.cursor.execute("SELECT headword FROM Entry ORDER BY headword")
            for row in self.db_manager.cursor.fetchall():
                self.listbox_headwords.addItem(row[0])
            self.update_headword_count()

    def display_entry(self, item):
        headword = item.text()
        self.db_manager.cursor.execute('''
            SELECT Entry.*, Senses.meaning 
            FROM Entry LEFT JOIN Senses 
            ON Entry.id = Senses.entry_id 
            WHERE headword=?''', (headword,))
        result = self.db_manager.cursor.fetchone()
        if result:
            self.current_entry_id = result[0]
            self.entry_headword.setText(result[1])
            self.entry_variation.setText(result[2])
            self.entry_pos.setText(result[3])
            self.entry_notes.setText(result[4])
            self.entry_meaning.clear()
            self.db_manager.cursor.execute("SELECT meaning FROM Senses WHERE entry_id=?", (self.current_entry_id,))
            for row in self.db_manager.cursor.fetchall():
                self.entry_meaning.append(row[0])

    def search_filter(self):
        search_term = self.entry_search.text().lower().strip()
        criteria = self.search_criteria_combo.currentText()
        fuzzy = self.fuzzy_search_checkbox.isChecked()
        self.listbox_headwords.clear()
        if not search_term:
            self.populate_headwords()
            return

        try:
            if fuzzy:
                self.db_manager.cursor.execute("SELECT headword, part_of_speech, variation FROM Entry")
                rows = self.db_manager.cursor.fetchall()
                matched = []
                for row in rows:
                    if criteria == "Headword":
                        field = (row[0] or "").lower()
                        if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                            matched.append(row[0])
                    elif criteria == "Part of Speech":
                        field = (row[1] or "").lower()
                        if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                            matched.append(row[0])
                    elif criteria == "Variation":
                        field = (row[2] or "").lower()
                        if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                            matched.append(row[0])
                    else:
                        fields = [(row[0] or "").lower(), (row[1] or "").lower(), (row[2] or "").lower()]
                        if any(difflib.get_close_matches(search_term, [f], cutoff=0.6) for f in fields):
                            matched.append(row[0])
                for head in sorted(set(matched)):
                    self.listbox_headwords.addItem(head)
            else:
                if criteria == "Headword":
                    query = "SELECT headword FROM Entry WHERE LOWER(headword) LIKE ?"
                    param = ('%' + search_term + '%',)
                elif criteria == "Part of Speech":
                    query = "SELECT headword FROM Entry WHERE LOWER(part_of_speech) LIKE ?"
                    param = ('%' + search_term + '%',)
                elif criteria == "Variation":
                    query = "SELECT headword FROM Entry WHERE LOWER(variation) LIKE ?"
                    param = ('%' + search_term + '%',)
                elif criteria == "Meaning":
                    query = '''SELECT headword FROM Entry 
                               WHERE id IN (
                                   SELECT entry_id FROM Senses WHERE LOWER(meaning) LIKE ?
                               )'''
                    param = ('%' + search_term + '%',)
                else:
                    query = '''SELECT headword FROM Entry
                               WHERE LOWER(headword) LIKE ? OR LOWER(part_of_speech) LIKE ? OR LOWER(variation) LIKE ?
                               OR id IN (SELECT entry_id FROM Senses WHERE LOWER(meaning) LIKE ?)'''
                    param = ('%' + search_term + '%', '%' + search_term + '%', '%' + search_term + '%', '%' + search_term + '%')
                self.db_manager.cursor.execute(query, param)
                rows = self.db_manager.cursor.fetchall()
                for row in rows:
                    self.listbox_headwords.addItem(row[0])
        except Exception as e:
            logging.exception("Error in search_filter")

    def save_entry(self):
        if not self.db_manager.conn:
            QMessageBox.warning(self, self.translations.get("db_error", "Database Error"),
                                self.translations.get("db_error_message", "Please create or load a database first."))
            return

        fields = {
            'headword': self.entry_headword.text(),
            'variation': self.entry_variation.text(),
            'pos': self.entry_pos.text(),
            'notes': self.entry_notes.text(),
            'meanings': self.entry_meaning.toPlainText().strip().splitlines()
        }

        if not fields['headword'] or not fields['meanings']:
            QMessageBox.warning(self, self.translations.get("missing", "Missing"),
                                self.translations.get("missing_text", "Headword and Meaning(s) are required!"))
            return

        try:
            if self.current_entry_id:  # Update
                self.db_manager.cursor.execute('''UPDATE Entry SET
                    headword=?, variation=?, part_of_speech=?, notes=?
                    WHERE id=?''',
                    (fields['headword'], fields['variation'], fields['pos'], fields['notes'], self.current_entry_id))
                self.db_manager.cursor.execute("DELETE FROM Senses WHERE entry_id=?", (self.current_entry_id,))
                for meaning in fields['meanings']:
                    self.db_manager.cursor.execute("INSERT INTO Senses (entry_id, meaning) VALUES (?, ?)",
                                              (self.current_entry_id, meaning.strip()))
            else:  # Insert new
                self.db_manager.cursor.execute("INSERT INTO Entry (headword, variation, part_of_speech, notes) VALUES (?, ?, ?, ?)",
                                          (fields['headword'], fields['variation'], fields['pos'], fields['notes']))
                entry_id = self.db_manager.cursor.lastrowid
                for meaning in fields['meanings']:
                    self.db_manager.cursor.execute("INSERT INTO Senses (entry_id, meaning) VALUES (?, ?)",
                                              (entry_id, meaning.strip()))
            self.db_manager.conn.commit()
            self.update_status(self.translations.get("status_entry_saved", "Entry saved successfully"))
            self.clear_fields()
            self.populate_headwords()
        except Exception as e:
            logging.exception("Error saving entry")
            self.update_status(f"Error: {e}")

    def delete_entry(self):
        if not self.current_entry_id:
            return
        if QMessageBox.question(
            self, 
            self.translations.get("confirm_delete", "Confirm"),
            self.translations.get("delete_confirmation", "Delete this entry permanently?")
        ) == QMessageBox.Yes:
            try:
                self.db_manager.cursor.execute("DELETE FROM Senses WHERE entry_id=?", (self.current_entry_id,))
                self.db_manager.cursor.execute("DELETE FROM Entry WHERE id=?", (self.current_entry_id,))
                self.db_manager.conn.commit()
                self.update_status(self.translations.get("delete_entry", "Entry deleted"))
                self.clear_fields()
                self.populate_headwords()
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    self.translations.get("error", "Error"), 
                    self.translations.get("delete_failed", "Delete failed: {error_message}").format(error_message=e)
                )

    def clear_fields(self):
        self.current_entry_id = None
        self.entry_headword.clear()
        self.entry_variation.clear()
        self.entry_pos.clear()
        self.entry_notes.clear()
        self.entry_meaning.clear()

    def update_headword_count(self):
        if self.db_manager.conn:
            self.db_manager.cursor.execute("SELECT COUNT(*) FROM Entry")
            total_count = self.db_manager.cursor.fetchone()[0]
            self.status_label.setText(self.translations.get("total_headwords", "Total Headwords: {count}").format(count=total_count))

    def update_status(self, message):
        self.status_bar.showMessage(message)

    def show_duplicates(self):
        if not self.db_manager.conn or not self.db_manager.cursor:
            QMessageBox.warning(
                self,
                self.translations.get("db_error", "Database Error"),
                self.translations.get("db_error_message", "Please create or load a database first.")
            )
            return

        self.db_manager.cursor.execute("SELECT headword, COUNT(*) FROM Entry GROUP BY headword HAVING COUNT(*) > 1")
        rows = self.db_manager.cursor.fetchall()
        if rows:
            duplicates_text = ""
            for row in rows:
                duplicates_text += self.translations.get("duplicate_headword", "Duplicate Headword: {headword} (Appears {count} times)\n\n").format(headword=row[0], count=row[1])
            self.duplicates_window = DuplicatesWindow(duplicates_text, self)
            self.duplicates_window.show()
            self.duplicates_window.raise_()
            self.duplicates_window.activateWindow()
        else:
            QMessageBox.information(
                self,
                self.translations.get("no_duplicates_title", "No Duplicates"),
                self.translations.get("no_duplicates_message", "No duplicate headwords found.")
            )

    def create_database(self):
        db_name = self.db_manager.create_database(self)
        if db_name:
            self.populate_headwords()

    def load_database(self):
        db_name = self.db_manager.load_database(self)
        if db_name:
            self.populate_headwords()

    def export_csv(self):
        self.import_export_manager.export_csv(self)

    def export_json(self):
        self.import_export_manager.export_json(self)

    def import_csv(self):
        self.import_export_manager.import_csv(self)
        self.populate_headwords()

    def import_json(self):
        self.import_export_manager.import_json(self)
        self.populate_headwords()

    def show_about(self):
        QMessageBox.information(
            self,
            self.translations.get("about_title", "About Nalluri Dictmaker"),
            self.translations.get("about_text", "DictMaker\nVersion 1.0.0\n\nA professional dictionary creation tool...")
        )

    def show_help(self):
        help_text = self.translations.get("help_text", "Keyboard Shortcuts:\nCtrl+S - Save Entry\nCtrl+D - Delete Entry\nCtrl+F - Search/Filter Entries\nCtrl+N - New Entry\nCtrl+A - New Database\nCtrl+O - Open/Load Database\nCtrl+Q - Quit")
        QMessageBox.information(self, self.translations.get("help_title", "Help"), help_text)

    def load_stylesheet(self, filename):
        style_path = resource_path(filename)
        if os.path.exists(style_path):
            with open(style_path, "r") as file:
                self.setStyleSheet(file.read())
        else:
            logging.error(f"Stylesheet not found: {style_path}")

    def change_theme(self, theme_filename):
        self.load_stylesheet(theme_filename)
        self.current_theme = theme_filename
        settings = load_settings()
        settings["theme"] = theme_filename
        save_settings(settings)
        self.update_status(self.translations.get("theme_changed", "Theme changed to {theme}").format(theme=theme_filename))

    def load_translations(self, lang_code):
        trans_path = resource_path(f"translations/{lang_code}.json")
        if os.path.exists(trans_path):
            try:
                with open(trans_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load translations: {e}")
                self.translations = {}
        else:
            logging.error(f"Translation file not found: {trans_path}")
            self.translations = {}

    def change_language(self, lang_code):
        self.current_language = lang_code
        self.load_translations(lang_code)
        self.apply_translations()
        settings = load_settings()
        settings["language"] = lang_code
        save_settings(settings)
        self.update_status(self.translations.get("status_language_changed", "Language changed."))

    def apply_translations(self):
        self.setWindowTitle(self.translations.get("window_title", "Nalluri Dictmaker"))
        self.file_menu.setTitle(self.translations.get("menu_file", "File"))
        self.new_db_action.setText(self.translations.get("menu_new_database", "New Database"))
        self.open_db_action.setText(self.translations.get("menu_open_database", "Open Database"))
        self.import_csv_action.setText(self.translations.get("menu_import_csv", "Import CSV"))
        self.export_csv_action.setText(self.translations.get("menu_export_csv", "Export CSV"))
        self.import_json_action.setText(self.translations.get("menu_import_json", "Import JSON"))
        self.export_json_action.setText(self.translations.get("menu_export_json", "Export JSON"))
        self.show_duplicates_action.setText(self.translations.get("menu_show_duplicates", "Show Duplicates"))
        self.exit_action.setText(self.translations.get("menu_exit", "Exit"))
        self.preferences_menu.setTitle(self.translations.get("menu_preferences", "Preferences"))
        self.theme_menu.setTitle(self.translations.get("menu_theme", "Theme"))
        self.light_theme_action.setText(self.translations.get("menu_light", "Light"))
        self.dark_theme_action.setText(self.translations.get("menu_dark", "Dark"))
        self.default_theme_action.setText(self.translations.get("menu_default", "Default"))
        self.greenlit_theme_action.setText(self.translations.get("menu_greenlit", "Greenlit"))
        self.material_theme_action.setText(self.translations.get("menu_material", "Material"))
        self.language_menu.setTitle(self.translations.get("menu_language", "Language"))
        self.english_action.setText(self.translations.get("menu_english", "English"))
        self.german_action.setText(self.translations.get("menu_german", "German"))
        self.malayalam_action.setText(self.translations.get("menu_malayalam", "Malayalam"))
        self.chinese_action.setText(self.translations.get("menu_chinese", "Chinese"))
        self.arabic_action.setText(self.translations.get("menu_arabic", "Arabic"))
        self.russian_action.setText(self.translations.get("menu_russian", "Russian"))
        self.japanese_action.setText(self.translations.get("menu_japanese", "Japanese"))
        self.indonesian_action.setText(self.translations.get("menu_indonesian", "Indonesian"))
        self.help_menu.setTitle(self.translations.get("menu_help", "Help"))
        self.keyboard_shortcuts_action.setText(self.translations.get("menu_keyboard_shortcuts", "Keyboard Shortcuts"))
        self.about_action.setText(self.translations.get("about", "About"))
        self.fuzzy_search_checkbox.setText(self.translations.get("fuzzy_search", "Fuzzy Search"))
        self.fuzzy_search_checkbox.setToolTip(self.translations.get("fuzzy_search_tooltip", "Check for approximate matches"))
        self.entry_search.setToolTip(self.translations.get("enter_search", "Enter search term"))
        self.search_label.setText(self.translations.get("search_label", "Search:"))
        self.entries_label.setText(self.translations.get("entries_label", "Entries"))
        self.headword_label.setText(self.translations.get("headword_label", "Headword"))
        self.variation_label.setText(self.translations.get("variation_label", "Variation"))
        self.pos_label.setText(self.translations.get("pos_label", "Part of Speech"))
        self.notes_label.setText(self.translations.get("notes_label", "Notes"))
        self.meaning_label.setText(self.translations.get("meaning_label", "Meaning"))
        self.save_button.setToolTip(self.translations.get("save_button_tooltip", "Save entry, Ctrl+S"))
        self.new_button.setToolTip(self.translations.get("new_button_tooltip", "New entry, Ctrl+N"))
        self.delete_button.setToolTip(self.translations.get("delete_button_tooltip", "Delete entry, Ctrl+D"))
        self.duplicates_button.setToolTip(self.translations.get("duplicates_button_tooltip", "Check for duplicate entries"))
        self.search_criteria_combo.setToolTip(self.translations.get("select_search_criteria", "Select search criteria"))
        self.search_criteria_combo.clear()
        self.search_criteria_combo.addItems([
            self.translations.get("search_all", "All"),
            self.translations.get("headword_label", "Headword"),
            self.translations.get("pos_label", "Part of Speech"),
            self.translations.get("variation_label", "Variation"),
            self.translations.get("meaning_label", "Meaning"),
        ])

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and obj.__class__.__name__ == "QLineEdit":
            if event.key() == Qt.Key_Up:
                obj.focusPreviousChild()
                return True
            elif event.key() == Qt.Key_Down:
                obj.focusNextChild()
                return True
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DictionaryApp()
    window.show()
    sys.exit(app.exec_())
