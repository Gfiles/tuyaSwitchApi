import sqlite3
import os
import json
import logging
from uuid import uuid4

class TuyaDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Legacy fields check for migration
            columns = [info['name'] for info in cursor.execute('PRAGMA table_info(devices)').fetchall()]
            if 'ip' in columns:
                cursor.execute('DROP TABLE devices')
                cursor.execute('DROP TABLE IF EXISTS excluded_devices')
                cursor.execute('DROP TABLE IF EXISTS schedule_devices')

            # Devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    solution TEXT,
                    domain TEXT
                )
            ''')
            # Excluded devices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS excluded_devices (
                    device_id TEXT PRIMARY KEY,
                    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
                )
            ''')
            # Schedules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    action TEXT,
                    time TEXT
                )
            ''')
            # Schedule days mapping
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_days (
                    schedule_id TEXT,
                    day TEXT,
                    PRIMARY KEY (schedule_id, day),
                    FOREIGN KEY (schedule_id) REFERENCES schedules (id) ON DELETE CASCADE
                )
            ''')
            # Schedule devices mapping
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schedule_devices (
                    schedule_id TEXT,
                    device_id TEXT,
                    PRIMARY KEY (schedule_id, device_id),
                    FOREIGN KEY (schedule_id) REFERENCES schedules (id) ON DELETE CASCADE,
                    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()

    def get_settings(self):
        with self.get_connection() as conn:
            return {row['key']: row['value'] for row in conn.execute('SELECT * FROM settings').fetchall()}

    def update_setting(self, key, value):
        with self.get_connection() as conn:
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
            conn.commit()

    def get_devices(self):
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM devices ORDER BY solution COLLATE NOCASE').fetchall()
            return [dict(row) for row in rows]

    def update_device_solution(self, device_id, solution):
        with self.get_connection() as conn:
            conn.execute('UPDATE devices SET solution = ? WHERE id = ?', (solution, device_id))
            conn.commit()

    def delete_device(self, device_id):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM devices WHERE id = ?', (device_id,))
            conn.commit()

    def get_schedules(self):
        schedules_list = []
        with self.get_connection() as conn:
            schedules = conn.execute('SELECT * FROM schedules').fetchall()
            for s in schedules:
                sd = dict(s)
                days = conn.execute('SELECT day FROM schedule_days WHERE schedule_id = ?', (s['id'],)).fetchall()
                sd['days'] = [row['day'] for row in days]
                devs = conn.execute('SELECT device_id FROM schedule_devices WHERE schedule_id = ?', (s['id'],)).fetchall()
                sd['devices'] = [row['device_id'] for row in devs]
                schedules_list.append(sd)
        return schedules_list

    def save_schedules(self, schedules):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM schedules')
            cursor.execute('DELETE FROM schedule_days')
            cursor.execute('DELETE FROM schedule_devices')
            for s in schedules:
                sid = s.get('id') or str(uuid4())
                cursor.execute('INSERT INTO schedules (id, name, action, time) VALUES (?, ?, ?, ?)', 
                               (sid, s['name'], s['action'], s['time']))
                for day in s.get('days', []):
                    cursor.execute('INSERT INTO schedule_days (schedule_id, day) VALUES (?, ?)', (sid, day))
                for dev_id in s.get('devices', []):
                    cursor.execute('INSERT INTO schedule_devices (schedule_id, device_id) VALUES (?, ?)', (sid, dev_id))
            conn.commit()

    def get_excluded_devices(self):
        with self.get_connection() as conn:
            return [row['device_id'] for row in conn.execute('SELECT device_id FROM excluded_devices').fetchall()]

    def update_excluded_devices(self, device_ids):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM excluded_devices')
            for did in device_ids:
                conn.execute('INSERT INTO excluded_devices (device_id) VALUES (?)', (did,))
            conn.commit()

    def upsert_scanned_devices(self, scanned_devices):
        with self.get_connection() as conn:
            for _, dev in scanned_devices.items():
                if dev.get('id'):
                    conn.execute('INSERT OR IGNORE INTO devices (id, name, solution, domain) VALUES (?, ?, ?, ?)',
                                (dev['id'], dev['name'], dev['name'], dev['domain']))
                    conn.execute('UPDATE devices SET name = ?, domain = ? WHERE id = ?', (dev['name'], dev['domain'], dev['id']))
            conn.commit()
