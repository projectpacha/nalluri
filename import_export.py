import json, csv, os, logging
from PyQt5.QtWidgets import QMessageBox, QFileDialog

class ImportExportManager:
    def __init__(self, db_manager, translations, status_callback):
        self.db_manager = db_manager
        self.translations = translations
        self.status_callback = status_callback

    def export_csv(self, parent):
        path, _ = QFileDialog.getSaveFileName(
            parent, 
            self.translations.get("export_csv", "Export CSV"),
            self.translations.get("csv_file_filter", "CSV files (*.csv);;All files (*.*)")
        )
        if not path:
            return
        try:
            self.db_manager.cursor.execute('''
                SELECT Entry.*, GROUP_CONCAT(Senses.meaning, ';;') AS meanings 
                FROM Entry 
                LEFT JOIN Senses ON Entry.id = Senses.entry_id 
                GROUP BY Entry.id
            ''')
            entries = self.db_manager.cursor.fetchall()
            headers = [description[0] for description in self.db_manager.cursor.description]
            with open(path, "w", newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                for row in entries:
                    writer.writerow(row)
            self.status_callback(self.translations.get("csv_exported", "CSV exported successfully"))
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.translations.get("error", "Error"),
                self.translations.get("csv_failed", "CSV export failed: {error_message}").format(error_message=e)
            )

    def export_json(self, parent):
        path, _ = QFileDialog.getSaveFileName(
            parent, 
            self.translations.get("export_json", "Export JSON"),
            self.translations.get("json_file_filter", "JSON files (*.json);;All files (*.*)")
        )
        if not path:
            return
        try:
            self.db_manager.cursor.execute('''
                SELECT Entry.*, GROUP_CONCAT(Senses.meaning, ';;') AS meanings 
                FROM Entry 
                LEFT JOIN Senses ON Entry.id = Senses.entry_id 
                GROUP BY Entry.id
            ''')
            entries = self.db_manager.cursor.fetchall()
            headers = [description[0] for description in self.db_manager.cursor.description]
            data = []
            for row in entries:
                entry_dict = dict(zip(headers, row))
                entry_dict['meanings'] = entry_dict['meanings'].split(';;') if entry_dict['meanings'] else []
                data.append(entry_dict)
            with open(path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.status_callback(self.translations.get("json_exported", "JSON exported successfully"))
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.translations.get("error", "Error"),
                self.translations.get("json_failed", "JSON export failed: {error_message}").format(error_message=e)
            )

    def import_csv(self, parent):
        path, _ = QFileDialog.getOpenFileName(
            parent, 
            self.translations.get("import_csv", "Import CSV"),
            self.translations.get("csv_file_filter", "CSV files (*.csv);;All files (*.*)")
        )
        if not path:
            return

        reply = QMessageBox.question(
            parent,
            self.translations.get("confirm_import", "Confirm Import"),
            self.translations.get(
            "confirm_message",
            "Do you wish to import data from external file? This may create duplicates of your existing headwords."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            with open(path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    self.db_manager.cursor.execute('''
                        INSERT INTO Entry (headword, variation, part_of_speech, notes)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        row.get('headword', ''),
                        row.get('variation', ''),
                        row.get('part_of_speech', ''),
                        row.get('notes', '')
                    ))
                    entry_id = self.db_manager.cursor.lastrowid
                    meanings = row.get('meanings', '')
                    if meanings:
                        for meaning in meanings.split(';;'):
                            self.db_manager.cursor.execute('''
                                INSERT INTO Senses (entry_id, meaning)
                                VALUES (?, ?)
                            ''', (entry_id, meaning.strip()))
                self.db_manager.conn.commit()
            self.status_callback(self.translations.get("csv_imported", "CSV imported successfully"))
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.translations.get("error", "Error"),
                self.translations.get("csv_import_failed", "CSV import failed: {error_message}").format(error_message=e)
            )

    def import_json(self, parent):
        path, _ = QFileDialog.getOpenFileName(
            parent, 
            self.translations.get("import_json", "Import JSON"),
            self.translations.get("json_file_filter", "JSON files (*.json);;All files (*.*)")
        )
        if not path:
            return
        reply = QMessageBox.question(
            parent,
            self.translations.get("confirm_import", "Confirm Import"),
            self.translations.get(
            "confirm_message",
            "Do you wish to import data from external file? This may create duplicates of your existing headwords."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            with open(path, "r", encoding='utf-8') as f:
                data = json.load(f)
            for item in data:
                self.db_manager.cursor.execute('''
                    INSERT INTO Entry (headword, variation, part_of_speech, notes)
                    VALUES (?, ?, ?, ?)
                ''', (
                    item.get('headword', ''),
                    item.get('variation', ''),
                    item.get('part_of_speech', ''),
                    item.get('notes', '')
                ))
                entry_id = self.db_manager.cursor.lastrowid
                for meaning in item.get('meanings', []):
                    self.db_manager.cursor.execute('''
                        INSERT INTO Senses (entry_id, meaning)
                        VALUES (?, ?)
                    ''', (entry_id, meaning.strip()))
            self.db_manager.conn.commit()
            self.status_callback(self.translations.get("json_imported", "JSON imported successfully"))
        except Exception as e:
            QMessageBox.critical(
                parent,
                self.translations.get("error", "Error"),
                self.translations.get("json_import_failed", "JSON import failed: {error_message}").format(error_message=e)
            )
