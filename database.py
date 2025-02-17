import sqlite3, os, json, datetime, logging
from shutil import copyfile
from PyQt5.QtWidgets import QMessageBox, QFileDialog, QInputDialog

class DatabaseManager:
    def __init__(self, translations, status_callback):
        self.conn = None
        self.cursor = None
        self.last_loaded_db = "last_loaded_db.json"
        self.translations = translations
        self.status_callback = status_callback

    def connect_db(self, db_name):
        try:
            self.conn = sqlite3.connect(db_name)
            self.cursor = self.conn.cursor()
        except Exception as e:
            QMessageBox.critical(None, self.translations.get("error", "Error"),
                                 f"Failed to connect to database: {e}")
            return False
        return True

    def check_db_structure(self):
        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Entry'")
            entry_table = self.cursor.fetchone()
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Senses'")
            senses_table = self.cursor.fetchone()
            return entry_table and senses_table
        except sqlite3.Error as e:
            QMessageBox.critical(
                None, 
                self.translations.get("db_error", "Database Error"),
                self.translations.get("error_structure", "Structure check failed: {error_message}").format(error_message=e)
            )
            return False

    def save_last_db(self, db_name):
        with open(self.last_loaded_db, "w") as f:
            json.dump({"db_name": db_name}, f)

    def load_last_db(self):
        if os.path.exists(self.last_loaded_db):
            with open(self.last_loaded_db) as f:
                return json.load(f).get("db_name")
        return None

    def create_database(self, parent):
        db_name, ok = QInputDialog.getText(
            parent, 
            self.translations.get("new_db", "New Database"),
            self.translations.get("enter_db_name", "Enter database name:")
        )
        if not ok or not db_name:
            return None

        if not db_name.endswith(".db"):
            db_name += ".db"

        if os.path.exists(db_name):
            QMessageBox.warning(
                parent, 
                self.translations.get("exists", "Exists"),
                self.translations.get("db_exists", "Database already exists!")
            )
            return None

        try:
            if self.connect_db(db_name):
                self.cursor.execute('''CREATE TABLE Entry (
                    id INTEGER PRIMARY KEY,
                    headword TEXT,
                    variation TEXT,
                    part_of_speech TEXT,
                    notes TEXT)''')
                self.cursor.execute('''CREATE TABLE Senses (
                    id INTEGER PRIMARY KEY,
                    entry_id INTEGER,
                    meaning TEXT,
                    FOREIGN KEY(entry_id) REFERENCES Entry(id))''')
                self.conn.commit()
                self.save_last_db(db_name)
                self.status_callback(
                    self.translations.get("created_new_db", "Created new database: {database}").format(database=db_name)
                )
                return db_name
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.translations.get("error", "Error"),
                self.translations.get("failed_to_create_db", "Failed to create database: {error_message}").format(error_message=e)
            )
            if self.conn:
                self.conn.close()
        return None

    def load_database(self, parent, db_name=None):
        if not db_name:
            db_name, _ = QFileDialog.getOpenFileName(
                parent, 
                self.translations.get("select_db", "Select Database"), 
                "", 
                self.translations.get("db_file_filter", "Database files (*.db);;All files (*.*)")
            )
        if db_name and os.path.exists(db_name):
            try:
                if self.connect_db(db_name):
                    if not self.check_db_structure():
                        QMessageBox.critical(
                            parent,
                            self.translations.get("invalid", "Invalid"),
                            self.translations.get("not_valid", "Not a valid dictionary database!")
                        )
                        self.conn.close()
                        return None
                    self.save_last_db(db_name)
                    self.status_callback(
                        self.translations.get("status_loaded", "Loaded: {database}").format(database=os.path.basename(db_name))
                    )
                    return db_name
            except Exception as e:
                QMessageBox.critical(
                    parent, 
                    self.translations.get("error", "Error"),
                    self.translations.get("load_failed", "Load failed: {error_message}").format(error_message=e)
                )
                if self.conn:
                    self.conn.close()
        return None

    def backup_database(self):
        if self.conn is None:
            return
        db_name = self.load_last_db()
        if not db_name or not os.path.exists(db_name):
            return
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"{os.path.basename(db_name)}_{timestamp}.bak")
        try:
            from shutil import copyfile
            copyfile(db_name, backup_path)
            logging.info(f"Database backed up to {backup_path}")
        except Exception as e:
            logging.exception("Database backup failed")

    def merge_duplicates(self):
        self.cursor.execute(
            "SELECT LOWER(TRIM(headword)) as norm_headword, COUNT(*) as cnt FROM Entry GROUP BY norm_headword HAVING cnt > 1"
        )
        duplicates = self.cursor.fetchall()
        for norm_headword, count in duplicates:
            self.cursor.execute(
                "SELECT id, headword FROM Entry WHERE LOWER(TRIM(headword)) = ? ORDER BY id ASC",
                (norm_headword,)
            )
            entries = self.cursor.fetchall()
            if entries:
                master_id = entries[0][0]
                for duplicate in entries[1:]:
                    duplicate_id = duplicate[0]
                    self.cursor.execute(
                        "UPDATE Senses SET entry_id = ? WHERE entry_id = ?",
                        (master_id, duplicate_id)
                    )
                    self.cursor.execute(
                        "DELETE FROM Entry WHERE id = ?",
                        (duplicate_id,)
                    )
        self.conn.commit()

    def delete_duplicates(self):
        self.cursor.execute(
            "SELECT LOWER(TRIM(headword)) as norm_headword, COUNT(*) as cnt FROM Entry GROUP BY norm_headword HAVING cnt > 1"
        )
        duplicates = self.cursor.fetchall()
        for norm_headword, count in duplicates:
            self.cursor.execute(
                "SELECT id, headword FROM Entry WHERE LOWER(TRIM(headword)) = ? ORDER BY id ASC",
                (norm_headword,)
            )
            entries = self.cursor.fetchall()
            if entries:
                master_id = entries[0][0]
                for duplicate in entries[1:]:
                    duplicate_id = duplicate[0]
                    self.cursor.execute(
                        "DELETE FROM Senses WHERE entry_id = ?",
                        (duplicate_id,)
                    )
                    self.cursor.execute(
                        "DELETE FROM Entry WHERE id = ?",
                        (duplicate_id,)
                    )
        self.conn.commit()
