import sys
import sqlite3
import os
import json
import csv
import difflib
import datetime
import logging
from shutil import copyfile
from PyQt5.QtGui import QIcon, QTextCursor, QTextCharFormat, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QListWidget,
    QPushButton, QMessageBox, QFileDialog, QInputDialog, QMenuBar, QMenu, QStatusBar, QFrame, QShortcut, QSplitter,
    QDialog, QComboBox, QCheckBox
)
from PyQt5.QtCore import Qt, QEvent

SETTINGS_FILE = "settings.json"

def save_settings(settings):
    """Save the settings dictionary to a JSON file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        logging.error("Failed to save settings: %s", e)

def load_settings():
    """Load the settings from a JSON file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error("Failed to load settings: %s", e)
    return {}

# Initialize global variables
conn = None
cursor = None
last_loaded_db = "last_loaded_db.json"
current_entry_id = None

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


# Database structure check
def check_db_structure():
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Entry'")
        entry_table = cursor.fetchone()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Senses'")
        senses_table = cursor.fetchone()
        return entry_table and senses_table
    except sqlite3.Error as e:
        QMessageBox.critical(
            None, 
            window.translations.get("db_error", "Database Error"), 
            window.translations.get("error_structure", "Structure check failed: {error_message}").format(error_message=e)
        )
        return False

# Persistent database tracking
def save_last_db(db_name):
    with open(last_loaded_db, "w") as f:
        json.dump({"db_name": db_name}, f)

def load_last_db():
    if os.path.exists(last_loaded_db):
        with open(last_loaded_db) as f:
            return json.load(f).get("db_name")
    return None

def initialize_last_db():
    if db_name := load_last_db():
        if os.path.exists(db_name):
            load_database(db_name)

# Database operations
def create_database():
    db_name, ok = QInputDialog.getText(None, window.translations.get("new_db","New Database"),window.translations.get("enter_db_name","Enter database name:"))
    if not ok or not db_name:
        return
        
    if not db_name.endswith(".db"):
        db_name += ".db"
    
    if os.path.exists(db_name):
        QMessageBox.warning(None, window.translations.get("exists","Exists"),window.translations.get("db_exists","Database already exists!"))
        return
    
    try:
        global conn, cursor
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE Entry (
            id INTEGER PRIMARY KEY,
            headword TEXT,
            variation TEXT,
            part_of_speech TEXT,
            notes TEXT)''')
            
        cursor.execute('''CREATE TABLE Senses (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER,
            meaning TEXT,
            FOREIGN KEY(entry_id) REFERENCES Entry(id))''')
            
        conn.commit()
        save_last_db(db_name)
        status_bar.showMessage(window.translations.get("created_new_db", "Created new database: {database}").format(database=db_name))
        populate_headwords()
        update_headword_count()
        
    except Exception as e:
        QMessageBox.critical(
            None,
            window.translations.get("error","Error"),
            window.translations.get("failed_to_create_db",f"Failed to create database: {error_message}").format(error_message=e)
        )
        if conn:
            conn.close()

def load_database(db_name=None):
    if not db_name:
        db_name, _ = QFileDialog.getOpenFileName(None, 
                                                window.translations.get("select_db", "Select Database"), 
                                                "", 
                                                window.translations.get("db_file_filter", "Database files (*.db);;All files (*.*)"))

    if db_name and os.path.exists(db_name):
        try:
            global conn, cursor
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            
            if not check_db_structure():
                QMessageBox.critical(
                    None,
                    window.translations.get("invalid","Invalid"),
                    window.translations.get("not_valid","Not a valid dictionary database!")      
                    )
                conn.close()
                return
                
            save_last_db(db_name)
            status_bar.showMessage(
                window.translations.get("status_loaded", "Loaded: {database}").format(database=os.path.basename(db_name))
            )
            populate_headwords()
            update_headword_count()
            
        except Exception as e:
            QMessageBox.critical(
                None, 
                window.translations.get("error","Error"),
                window.translations.get("load_failed",f"Load failed: {error_message}").format(error_message=e)
                )
            if conn:
                conn.close()

# Data population
def populate_headwords():
    listbox_headwords.clear()
    if conn:
        cursor.execute("SELECT headword FROM Entry ORDER BY headword")
        for row in cursor.fetchall():
            listbox_headwords.addItem(row[0])



def display_entry():
    selection = listbox_headwords.currentRow()
    if selection == -1:
        return
    
    headword = listbox_headwords.item(selection).text()
    cursor.execute('''SELECT Entry.*, Senses.meaning 
                   FROM Entry LEFT JOIN Senses 
                   ON Entry.id = Senses.entry_id 
                   WHERE headword=?''', (headword,))
    
    if result := cursor.fetchone():
        global current_entry_id
        current_entry_id = result[0]
        
        entry_headword.setText(result[1])
        entry_variation.setText(result[2])
        entry_pos.setText(result[3])
        entry_notes.setText(result[4])
        
        entry_meaning.clear()
        cursor.execute("SELECT meaning FROM Senses WHERE entry_id=?", (current_entry_id,))
        for row in cursor.fetchall():
            entry_meaning.append(row[0])

def search_filter():
    search_term = entry_search.text().lower().strip()
    criteria = search_criteria_combo.currentText()
    fuzzy = fuzzy_search_checkbox.isChecked()
    listbox_headwords.clear()
    if not search_term:
        populate_headwords()
        return

    try:
        if fuzzy:
            cursor.execute("SELECT headword, part_of_speech, variation FROM Entry")
            rows = cursor.fetchall()
            matched = []
            for row in rows:
                # Depending on criteria, select the appropriate field(s)
                if criteria == "Headword":
                    field = row[0].lower() if row[0] else ""
                    if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                        matched.append(row[0])
                elif criteria == "Part of Speech":
                    field = row[1].lower() if row[1] else ""
                    if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                        matched.append(row[0])
                elif criteria == "Variation":
                    field = row[2].lower() if row[2] else ""
                    if difflib.get_close_matches(search_term, [field], cutoff=0.6):
                        matched.append(row[0])
                else:
                    # For "All", check all three fields
                    fields = [(row[0] or "").lower(), (row[1] or "").lower(), (row[2] or "").lower()]
                    if any(difflib.get_close_matches(search_term, [f], cutoff=0.6) for f in fields):
                        matched.append(row[0])
            # Remove duplicates and populate
            for head in sorted(set(matched)):
                listbox_headwords.addItem(head)
        else:
            # Use SQL search with wildcards
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
            else:  # "All"
                query = '''SELECT headword FROM Entry
                           WHERE LOWER(headword) LIKE ? OR LOWER(part_of_speech) LIKE ? OR LOWER(variation) LIKE ?
                           OR id IN (SELECT entry_id FROM Senses WHERE LOWER(meaning) LIKE ?)'''
                param = ('%' + search_term + '%', '%' + search_term + '%', '%' + search_term + '%', '%' + search_term + '%')
            cursor.execute(query, param)
            rows = cursor.fetchall()
            for row in rows:
                listbox_headwords.addItem(row[0])
    except Exception as e:
        logging.exception("Error in search_filter")

#data import export
def export_csv():
    path, _ = QFileDialog.getSaveFileName(None, 
                                            window.translations.get("export_csv","Export CSV"),
                                            window.translations.get("csv_file_filter", "CSV files (*.db);;All files (*.*)"))
    if not path:
        return
    try:
        # Join Entry with Senses and aggregate meanings
        cursor.execute('''
            SELECT Entry.*, GROUP_CONCAT(Senses.meaning, ';;') AS meanings 
            FROM Entry 
            LEFT JOIN Senses ON Entry.id = Senses.entry_id 
            GROUP BY Entry.id
        ''')
        entries = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        
        with open(path, "w", newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for row in entries:
                writer.writerow(row)
        status_bar.showMessage(window.translations.get("csv_exported","CSV exported successfully"))
    except Exception as e:
        QMessageBox.critical(
            None,
            window.translations.get("error","Error"),
            window.translations.get("csv_failed",f"CSV export failed: {error_message}").format(error_message=e)
        )

def export_json():
    path, _ = QFileDialog.getSaveFileName(None, window.translations.get("export_json","Export JSON"),window.translations.get("json_file_filter", "JSON files (*.db);;All files (*.*)"))
    if not path:
        return
    try:
        cursor.execute('''
            SELECT Entry.*, GROUP_CONCAT(Senses.meaning, ';;') AS meanings 
            FROM Entry 
            LEFT JOIN Senses ON Entry.id = Senses.entry_id 
            GROUP BY Entry.id
        ''')
        entries = cursor.fetchall()
        headers = [description[0] for description in cursor.description]
        
        data = []
        for row in entries:
            entry_dict = dict(zip(headers, row))
            # Split meanings into a list
            entry_dict['meanings'] = entry_dict['meanings'].split(';;') if entry_dict['meanings'] else []
            data.append(entry_dict)
        
        with open(path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        status_bar.showMessage(window.translations.get("json_exported","CSV exported successfully"))
    except Exception as e:
        QMessageBox.critical(
            None,
            window.translations.get("error","Error"),
            window.translations.get("json_failed",f"JSON export failed: {error_message}").format(error_message=e)
        )

def import_csv():
    path, _ = QFileDialog.getSaveFileName(None, window.translations.get("import_csv","Import CSV"),window.translations.get("csv_file_filter", "JSON files (*.db);;All files (*.*)"))
    if not path:
        return
    try:
        with open(path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Insert into Entry
                cursor.execute('''
                    INSERT INTO Entry (headword, variation, part_of_speech, notes)
                    VALUES (?, ?, ?, ?)
                ''', (
                    row.get('headword', ''),
                    row.get('variation', ''),
                    row.get('part_of_speech', ''),
                    row.get('notes', '')
                ))
                entry_id = cursor.lastrowid
                
                # Insert meanings into Senses
                meanings = row.get('meanings', '')
                if meanings:
                    for meaning in meanings.split(';;'):
                        cursor.execute('''
                            INSERT INTO Senses (entry_id, meaning)
                            VALUES (?, ?)
                        ''', (entry_id, meaning.strip()))
            conn.commit()
        populate_headwords()
        update_headword_count()
        status_bar.showMessage(window.translations.get("csv_imported","CSV imported successfully"))
    except Exception as e:
        QMessageBox.critical(
            None,
            window.translations.get("error","Error"),
            window.translations.get("csv_import_failed",f"CSV import failed: {error_message}").format(error_message=e)
        )

def import_json():
    path, _ = QFileDialog.getSaveFileName(None, window.translations.get("import_json","Import JSON"),window.translations.get("json_file_filter", "JSON files (*.db);;All files (*.*)"))
    if not path:
        return
    try:
        with open(path, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            # Insert into Entry
            cursor.execute('''
                INSERT INTO Entry (headword, variation, part_of_speech, notes)
                VALUES (?, ?, ?, ?)
            ''', (
                item.get('headword', ''),
                item.get('variation', ''),
                item.get('part_of_speech', ''),
                item.get('notes', '')
            ))
            entry_id = cursor.lastrowid
            
            # Insert meanings into Senses
            meanings = item.get('meanings', [])
            for meaning in meanings:
                cursor.execute('''
                    INSERT INTO Senses (entry_id, meaning)
                    VALUES (?, ?)
                ''', (entry_id, meaning.strip()))
        conn.commit()
        populate_headwords()
        update_headword_count()
        status_bar.showMessage(window.translations.get("json_imported","JSON imported successfully"))
    except Exception as e:
        QMessageBox.critical(
            None,
            window.translations.get("error","Error"),
            window.translations.get("json_import_failed",f"JSON import failed: {error_message}").format(error_message=e)
        )

# -----------------------

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

        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

def show_duplicates():
    if conn is None or cursor is None:
        QMessageBox.warning(
                            None,
                            window.translations.get("db_error", "Database Error"),
                            window.translations.get("db_error_message","Please create or load a database first.")
        )
        return

    cursor.execute('''
    SELECT headword, COUNT(*) FROM Entry GROUP BY headword HAVING COUNT(*) > 1
    ''')
    rows = cursor.fetchall()
    if rows:
        duplicates_text = ""
        for row in rows:
            duplicates_text += window.translations.get(
                "duplicate_headword", 
                "Duplicate Headword: {headword} (Appears {count} times)\n\n"
            ).format(headword=row[0], count=row[1])
        window.duplicates_window = DuplicatesWindow(duplicates_text, parent=window)
        window.duplicates_window.show()
        window.duplicates_window.raise_()
        window.duplicates_window.activateWindow()
    else:
        QMessageBox.information(
            None, 
            window.translations.get("no_duplicates_title", "No Duplicates"), 
            window.translations.get("no_duplicates_message", "No duplicate headwords found.")
        )

def save_entry():
    if not conn:
        QMessageBox.warning(None, window.translations.get("db_error", "Database Error"),window.translations.get("db_error_message","Please create or load a database first."))
        return

    fields = {
        'headword': entry_headword.text(),
        'variation': entry_variation.text(),
        'pos': entry_pos.text(),
        'notes': entry_notes.text(),
        'meanings': entry_meaning.toPlainText().strip().splitlines()
    }

    if not fields['headword'] or not fields['meanings']:
        QMessageBox.warning(None,
                            window.translations.get("missing","Missing"),
                            window.translations.get("missing_text","Headword and Meaning(s) are required!"))
        return

    try:
        if current_entry_id:  # Update existing entry
            cursor.execute('''UPDATE Entry SET
                headword=?, variation=?, part_of_speech=?, notes=?
                WHERE id=?''',
                (fields['headword'], fields['variation'], 
                 fields['pos'], fields['notes'], current_entry_id))
            
            cursor.execute('''DELETE FROM Senses WHERE entry_id=?''', (current_entry_id,))

            for meaning in fields['meanings']:
                cursor.execute('''INSERT INTO Senses (entry_id, meaning)
                    VALUES (?, ?)''', (current_entry_id, meaning.strip()))
        else:  # Insert new entry
            cursor.execute('''INSERT INTO Entry 
                (headword, variation, part_of_speech, notes)
                VALUES (?, ?, ?, ?)''',
                (fields['headword'], fields['variation'],
                 fields['pos'], fields['notes']))
            
            entry_id = cursor.lastrowid
            for meaning in fields['meanings']:
                cursor.execute('''INSERT INTO Senses (entry_id, meaning)
                    VALUES (?, ?)''', (entry_id, meaning.strip()))

        conn.commit()
        status_bar.showMessage(window.translations.get("status_entry_saved", "Entry saved successfully"))
        clear_fields()
        populate_headwords()
        update_headword_count()

    except sqlite3.Error as e:
        status_bar.showMessage(f"SQLite Error: {e}")
        print(f"SQLite Error: {e}")

    except Exception as e:
        status_bar.showMessage(f"Unexpected Error: {e}")
        print(f"Unexpected Error: {e}")

def delete_entry():
    if not current_entry_id:
        return
    
    if QMessageBox.question(None, window.translations.get("confirm_delete","Confirm"),window.translations.get("delete_confirmation","Delete this entry permanently?")) == QMessageBox.Yes:
        try:
            cursor.execute("DELETE FROM Senses WHERE entry_id=?", (current_entry_id,))
            cursor.execute("DELETE FROM Entry WHERE id=?", (current_entry_id,))
            conn.commit()
            status_bar.showMessage(window.translations.get("delete_entry", "Entry deleted"))
            clear_fields()
            populate_headwords()
            update_headword_count()
        except Exception as e:
            QMessageBox.critical(None, window.translations.get("error","Error"),"delete_failed",f"Delete failed: {error_message}").format(error_message=e)

def clear_fields():
    global current_entry_id
    current_entry_id = None
    entry_headword.clear()
    entry_variation.clear()
    entry_pos.clear()
    entry_notes.clear()
    entry_meaning.clear()

def update_headword_count():
    if conn:
        cursor.execute("SELECT COUNT(*) FROM Entry")
        total_count = cursor.fetchone()[0]
        window.status_label.setText(
            window.translations.get("total_headwords", "Total Headwords: {count}").format(count=total_count)
        )

def backup_database():
    if conn is None:
        return
    db_name = load_last_db()
    if not db_name or not os.path.exists(db_name):
        return
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{os.path.basename(db_name)}_{timestamp}.bak")
    try:
        copyfile(db_name, backup_path)
        logging.info(f"Database backed up to {backup_path}")
    except Exception as e:
        logging.exception("Database backup failed")

class DictionaryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("icons/app_icon.png")))
        global window  
        window = self
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)  # Ensure maximize button is present
        self.translations = {}  # will hold current language strings
        self.current_language = "en"
        self.initUI()
        settings = load_settings()
        theme = settings.get("theme", "themes/default_style.qss")
        self.load_stylesheet(theme)
        lang = settings.get("language", "en")
        self.change_language(lang)
        self.duplicates_window = None

    def initUI(self):
        self.setWindowTitle("Nalluri DictMaker")
        self.setGeometry(100, 100, 1280, 800)

        # Menu System
        menubar = self.menuBar()
        self.file_menu = menubar.addMenu("File")
        self.new_db_action = self.file_menu.addAction("New Database", create_database)
        self.open_db_action = self.file_menu.addAction("Open Database", load_database)
        self.file_menu.addSeparator()
        self.import_csv_action = self.file_menu.addAction("Import CSV", import_csv)
        self.export_csv_action = self.file_menu.addAction("Export CSV", export_csv)
        self.import_json_action = self.file_menu.addAction("Import JSON", import_json)
        self.export_json_action = self.file_menu.addAction("Export JSON", export_json)
        self.file_menu.addSeparator()
        self.show_duplicates_action = self.file_menu.addAction("Show Duplicates", show_duplicates)
        self.file_menu.addSeparator()
        self.exit_action = self.file_menu.addAction("Exit", self.close)

        self.preferences_menu = menubar.addMenu("Preferences")
        self.theme_menu = self.preferences_menu.addMenu("Theme")
        self.light_theme_action = self.theme_menu.addAction("Light", lambda: self.change_theme("themes/style_light.qss"))
        self.dark_theme_action = self.theme_menu.addAction("Dark", lambda: self.change_theme("themes/style_dark.qss"))
        self.greenlit_theme_action = self.theme_menu.addAction("Greenlit", lambda: self.change_theme("themes/greenlit_style.qss"))
        self.material_theme_action = self.theme_menu.addAction("Material", lambda: self.change_theme("themes/material_style.qss"))
        self.default_theme_action = self.theme_menu.addAction("Default", lambda: self.change_theme("themes/default_style.qss"))

        # New Language submenu
        self.language_menu = self.preferences_menu.addMenu("Language")
        self.english_action = self.language_menu.addAction("English", lambda: self.change_language("en"))
        self.german_action = self.language_menu.addAction("German", lambda: self.change_language("de"))
        self.malayalam_action = self.language_menu.addAction("Malayalam", lambda: self.change_language("ml"))
        self.chinese_action = self.language_menu.addAction("Chinese", lambda: self.change_language("zh"))
        self.arabic_action = self.language_menu.addAction("Arabic", lambda: self.change_language("ar"))
        self.russian_action = self.language_menu.addAction("russian", lambda: self.change_language("ru"))
        self.japanese_action = self.language_menu.addAction("Japanese", lambda: self.change_language("jp"))
        self.indonesian_action = self.language_menu.addAction("Indonesian", lambda: self.change_language("id"))

        
        self.help_menu = menubar.addMenu("Help")
        self.keyboard_shortcuts_action = self.help_menu.addAction("Keyboard Shortcuts", self.show_help)
        self.about_action = self.help_menu.addAction("About", self.show_about)

        # Main Layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Search Bar
        search_frame = QFrame()
        search_layout = QHBoxLayout(search_frame)
        self.search_label = QLabel("Search:")
        search_layout.addWidget(self.search_label)
        global entry_search
        entry_search = QLineEdit()
        entry_search.setToolTip(window.translations.get("enter_search", "Enter search term"))
        search_layout.addWidget(entry_search)
        global search_criteria_combo
        search_criteria_combo = QComboBox()
        search_criteria_combo.addItems([
                                window.translations.get("search_all", "All"),
                                window.translations.get("headword_label", "Headword"),
                                window.translations.get("pos_label", "Part of Speech"),
                                window.translations.get("variation_label", "Variation"),
                                window.translations.get("meaning_label", "Meaning"),
                                ])
        search_criteria_combo.setToolTip("Select search criteria")
        search_layout.addWidget(search_criteria_combo)
        global fuzzy_search_checkbox
        fuzzy_search_checkbox = QCheckBox(window.translations.get("fuzzy_search", "Fuzzy Search"))
        fuzzy_search_checkbox.setToolTip(window.translations.get("fuzzy_search_tooltip", "Check for approximate matches"))
        search_layout.addWidget(fuzzy_search_checkbox)
        search_button = QPushButton("")
        search_button.setIcon(QIcon(resource_path("icons/search_icon.png")))
        search_button.clicked.connect(search_filter)
        search_layout.addWidget(search_button)
        main_layout.addWidget(search_frame)

        # Main Content Area
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)

        splitter = QSplitter(Qt.Horizontal)
        # Left: Headword List
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        self.entries_label = QLabel("Entries")
        list_layout.addWidget(self.entries_label)
        global listbox_headwords
        listbox_headwords = QListWidget()
        listbox_headwords.itemClicked.connect(display_entry)
        list_layout.addWidget(listbox_headwords)
        splitter.addWidget(list_frame)

        # Right: Entry Form
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        global entry_headword, entry_variation, entry_pos, entry_notes, entry_meaning
        self.headword_label = QLabel("Headword")
        form_layout.addWidget(self.headword_label)
        entry_headword = QLineEdit()
        form_layout.addWidget(entry_headword)
        self.variation_label = QLabel("Variation")
        form_layout.addWidget(self.variation_label)
        entry_variation = QLineEdit()
        form_layout.addWidget(entry_variation)
        self.pos_label = QLabel("Part of Speech")
        form_layout.addWidget(self.pos_label)
        entry_pos = QLineEdit()
        form_layout.addWidget(entry_pos)
        self.notes_label = QLabel("Notes")
        form_layout.addWidget(self.notes_label)
        entry_notes = QLineEdit()
        form_layout.addWidget(entry_notes)
        self.meaning_label = QLabel("Meaning")
        form_layout.addWidget(self.meaning_label)
        entry_meaning = QTextEdit()
        form_layout.addWidget(entry_meaning)

        # Action Buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        self.save_button = QPushButton("")
        self.save_button.setIcon(QIcon(resource_path("icons/save_icon.png")))
        self.save_button.setToolTip("Save entry, Ctrl+S")
        self.save_button.clicked.connect(save_entry)
        button_layout.addWidget(self.save_button)
        self.new_button = QPushButton("")
        self.new_button.setIcon(QIcon(resource_path("icons/new_icon.png")))
        self.new_button.setToolTip("Create new entry, Ctrl+N")
        self.new_button.clicked.connect(clear_fields)
        button_layout.addWidget(self.new_button)
        self.delete_button = QPushButton("")
        self.delete_button.setIcon(QIcon(resource_path("icons/delete_icon.png")))
        self.delete_button.setToolTip("Delete entry, Ctrl+D")
        self.delete_button.clicked.connect(delete_entry)
        button_layout.addWidget(self.delete_button)
        self.duplicates_button = QPushButton("")
        self.duplicates_button.setIcon(QIcon(resource_path("icons/duplicates_icon.png")))
        self.duplicates_button.setToolTip("Check for duplicate entries")
        self.duplicates_button.clicked.connect(show_duplicates)
        button_layout.addWidget(self.duplicates_button)
        form_layout.addWidget(button_frame)
        
        splitter.addWidget(form_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)

        # Status Bar
        global status_bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_label = QLabel("Total Headwords: 0")
        status_bar.addPermanentWidget(self.status_label)

        # Initialization
        initialize_last_db()

        # Keyboard Shortcuts
        self.add_shortcut(Qt.CTRL + Qt.Key_S, save_entry)
        self.add_shortcut(Qt.CTRL + Qt.Key_D, delete_entry)
        self.add_shortcut(Qt.CTRL + Qt.Key_F, search_filter)
        self.add_shortcut(Qt.CTRL + Qt.Key_N, clear_fields)
        self.add_shortcut(Qt.CTRL + Qt.Key_A, create_database)
        self.add_shortcut(Qt.CTRL + Qt.Key_O, load_database)
        self.add_shortcut(Qt.CTRL + Qt.Key_Q, self.close)

    def add_shortcut(self, key, function):
        shortcut = QShortcut(key, self)
        shortcut.activated.connect(function)

    def show_about(self):
        QMessageBox.information(
            self,
            self.translations.get("about_title", "About Nalluri Dictmaker"),
            self.translations.get("about_text", "DictMaker\nVersion 1.0.0\n\nNalluri Dictmaker is a professional dictionary creation and management tool designed primarily for bilingual projects. It enables users to efficiently build, manage and edit dictionaries with structured entries, supporting headwords, parts of speech, and custom notes. Whether you're a linguist, researcher, translator, or language enthusiast, Nalluri DictMaker provides a user-friendly interface and powerful features to streamline dictionary development. With built-in search, filtering, duplicate detection, and export options, it ensures a seamless workflow for managing lexical data.\n\nThis Version is not meant to support multilingual dictionaries. However, you can use the meanings column to add meanings in multiple target languages at once.\n\nDeveloped by Arish Vijayakumar pachamalayalamproject@gmail.com")
        )

    def show_help(self):
        shortcuts = (
            "Keyboard Shortcuts:\n"
            "------------------------\n"
            "Ctrl+S - Save Entry\n"
            "Ctrl+D - Delete Entry\n"
            "Ctrl+F - Search/Filter Entries\n"
            "Ctrl+N - New Entry\n"
            "Ctrl+A - New Database\n"
            "Ctrl+O - Open/Load Database\n"
            "Ctrl+Q - Quit\n"
            "Up Arrow - Move focus to the previous field\n"
            "Down Arrow - Move focus to the next field\n"
        )
        QMessageBox.information(
            self, 
            self.translations.get("help_title", "Help - Keyboard Shortcuts"), 
            self.translations.get("help_text", "Keyboard Shortcuts:\n------------------------\nCtrl+S - Save Entry\nCtrl+D - Delete Entry\nCtrl+F - Search/Filter Entries\nCtrl+N - New Entry\nCtrl+A - New Database\nCtrl+O - Open/Load Database\nCtrl+Q - Quit\nUp Arrow - Move focus to the previous field\nDown Arrow - Move focus to the next field")
        )

    def load_stylesheet(self, filename):
        style_path = resource_path(filename)
        if os.path.exists(style_path):
            with open(style_path, "r") as file:
                self.setStyleSheet(file.read())
        else:
            logging.error(f"Stylesheet not found: {style_path}")

    def change_theme(self, theme_filename):
        """Load the chosen theme and save the preference for next start."""
        self.load_stylesheet(theme_filename)
        self.current_theme = theme_filename
        settings = load_settings()
        settings["theme"] = theme_filename
        save_settings(settings)
        status_bar.showMessage(
            self.translations.get("theme_changed", "Theme changed to {theme}").format(theme=theme_filename))



    def load_translations(self, lang_code):
        trans_path = resource_path(os.path.join("translations", f"{lang_code}.json"))
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
        status_bar.showMessage(self.translations.get("status_language_changed", "Language changed."))

    def apply_translations(self):
        # Update window title
        self.setWindowTitle(self.translations.get("window_title", "Nalluri Dictmaker"))
        # Update menu texts
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
        fuzzy_search_checkbox.setText(window.translations.get("fuzzy_search", "Fuzzy Search"))
        fuzzy_search_checkbox.setToolTip(window.translations.get("fuzzy_search_tooltip", "Check for approximate matches"))
        entry_search.setToolTip(window.translations.get("enter_search", "Enter search term"))

        
        # Update labels in main window
        self.search_label.setText(self.translations.get("search_label", "Search:"))
        self.entries_label.setText(self.translations.get("entries_label", "Entries"))
        self.headword_label.setText(self.translations.get("headword_label", "Headword"))
        self.variation_label.setText(self.translations.get("variation_label", "Variation"))
        self.pos_label.setText(self.translations.get("pos_label", "Part of Speech"))
        self.notes_label.setText(self.translations.get("notes_label", "Notes"))
        self.meaning_label.setText(self.translations.get("meaning_label", "Meaning"))
        
        # Update tooltips for buttons
        self.save_button.setToolTip(self.translations.get("save_button_tooltip", "Save entry, Ctrl+S"))
        self.new_button.setToolTip(self.translations.get("new_button_tooltip", "New entry, Ctrl+N"))
        self.delete_button.setToolTip(self.translations.get("delete_button_tooltip", "Delete entry, Ctrl+D"))
        self.duplicates_button.setToolTip(self.translations.get("duplicates_button_tooltip", "Check for duplicate entries"))
        search_criteria_combo.setToolTip(window.translations.get("select_search_criteria", "Select search criteria"))
        search_criteria_combo.clear()
        search_criteria_combo.addItems([
                                window.translations.get("search_all", "All"),
                                window.translations.get("headword_label", "Headword"),
                                window.translations.get("pos_label", "Part of Speech"),
                                window.translations.get("variation_label", "Variation"),
                                window.translations.get("meaning_label", "Meaning"),
                                ])

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if isinstance(obj, QLineEdit):
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
