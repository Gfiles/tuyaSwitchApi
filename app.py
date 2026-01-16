# Install required libraries
# sudo apt-get install python-crypto python-pip  # for RPi, Linux
# python3 -m pip install pycryptodome            # or pycrypto or Crypto or pyaes
# python -m tinytuya scan  #scan to get list of local devices
# https://pypi.org/project/tinytuya/
# https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys
# python -m tinytuya wizard (get device id and keys) #Run this command to get the device id and keys
# https://pimylifeup.com/raspberry-pi-flask-web-app/
# UV Installation:
# Windows PowerShell:
#   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# Linux:
#   curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
#  pyinstaller --clean --onefile --add-data "templates*;." --add-data "devices.json;." -n tuyaServer app.py
# Linux:
# .venv/bin/pyinstaller --clean --onefile --add-data "templates*:." --add-data "devices.json:." -n tuyaServer_deb app.py
import logging
import subprocess
from uuid import uuid4
from flask import Flask, render_template, request, jsonify, redirect #pip install Flask
from flask_restful import Resource, Api #pip install Flask-RESTful
import json
from datetime import datetime
import os
import sys
import jinja2
import sqlite3
import requests #pip install requests
import tinytuya #pip install tinytuya
from waitress import serve #pip install waitress
from apscheduler.schedulers.background import BackgroundScheduler #pip install apscheduler
from threading import Thread
import platform
import shutil

# ---------- Start Configurations ---------- #
VERSION = "2026.01.16"
print(f"Switch Server Version: {VERSION}")

DEVICES_URL = "https://proj.ydreams.global/ydreams/apps/servers/devices.json"

try:
    this_file = __file__
except NameError:
    this_file = sys.argv[0]
this_file = os.path.abspath(this_file)

template_loader = ''
if getattr(sys, 'frozen', False):
    # for the case of running in pyInstaller's exe
    bundle_dir = sys._MEIPASS
    #template_loader = jinja2.FileSystemLoader(os.path.join(bundle_dir, 'templates'))
    cwd = os.path.dirname(sys.executable)
else:
    # for running locally
    #template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.path.dirname(this_file)
template_folder = os.path.join(bundle_dir, 'templates')
template_loader = jinja2.FileSystemLoader(template_folder)
print(f"template_loader - {template_folder}")
template_env = jinja2.Environment(loader=template_loader)

app = Flask(__name__)
api = Api(app)
# ---------- End Configurations ---------- #
# ---------- Start Classes ---------- #
class On(Resource):
    def get(self, pk):
        try:
            switch = switches.get(pk)
            switch.turn_on()
            logging.info(f"Switch {pk} turned on")
            #device["state"] = True
        except:
            return "error"
        return f"{pk} Switch Turned On"

class Off(Resource):
    def get(self, pk):
        try:
            switch = switches.get(pk)
            switch.turn_off()
            logging.info(f"Switch {pk} turned off")
            logging.info(f"Request info: {getRequestInfo()}")
            #device["state"] = False
        except:
            return "error"
        return f"{pk} Switch Turned Off"

class Status(Resource):
    def get(self, pk):
        for device in devices:
            if device["id"] == pk:
                try:
                    switch = switches.get(pk)
                    if switch.status()['dps']['1']:
                        status = "On"
                        #device["state"] = True
                    else:
                        status = "Off"
                        #device["state"] = False
                except:
                    return f"{device['name']} Status: Offline"
                logging.info(f"Status of {pk} returned as {status}")
                logging.info(f"Request info: {getRequestInfo()}")
                return f"{device['name']} Status: {status}"
            break

#api.add_resource(Items, '/')
api.add_resource(On, '/on/<pk>')
api.add_resource(Off, '/off/<pk>')
api.add_resource(Status, '/status/<pk>')
# ---------- End Classes ---------- #
# ---------- Start Routing Functions ---------- #
@app.route("/")
def index():
    switchInfo = []
    for device in devices:
        switchInfo.append([
            device.get("solution", ""),
            device.get("name", ""),
            device.get("state", "offline"),
            device.get("voltage", 0),
            device.get("id", "")
        ])
    return render_template("index.html", switches=switchInfo, title=title, minButtonWidth=minButtonWidth)

# Route for toggling a switch
@app.route("/toggle/<pk>")
def toggle_switch(pk):
    #i = int(device_id) - 1
    print(f"get Toggle input {pk}")
    for device in devices:
        if device["id"] == pk:
            #print(f"Device {pk} found")
            switch = switches.get(pk)
            #print(switch)
            #print(switch.status())
            try:
                current_state = switch.status()["dps"]["1"]
                print(f"Current State: {current_state}")
                #new_state = 1 if current_state == 0 else 0
                if current_state:
                    switch.turn_off()
                    logging.info(f"Switch {device['name']} toggled to off")
                    device["state"] = False
                else:
                    switch.turn_on()
                    logging.info(f"Switch {device['name']} toggled to on")
                    device["state"] = True
            except:
                print("Sem Conexão com a Tomada")
                logging.error(f"Error toggling switch {pk}")
            logging.info(f"Request info: {getRequestInfo()}")
            break
    return redirect("/")

@app.route("/all/<action>")
def all_switches(action):
    if action not in ["on", "off"]:
        return "Invalid action", 400

    excluded_devices = config.get("exclude_from_all", [])

    for device in devices:
        if device['id'] in excluded_devices:
            logging.info(f"Skipping device {device['name']} as it is in the exclusion list for 'all' actions.")
            continue
        switch = switches.get(device['id'])
        if switch:
            try:
                if action == "on":
                    switch.turn_on()
                    device["state"] = True
                    logging.info(f"Switch {device['name']} turned on")
                elif action == "off":
                    switch.turn_off()
                    device["state"] = False
                    logging.info(f"Switch {device['name']} turned off")
            except Exception as e:
                logging.error(f"Error controlling switch {device['name']}: {e}")
                device["state"] = "offline"
    return redirect("/")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    global config, devices, title, refresh, port, minButtonWidth
    db = get_db_conn()
    cursor = db.cursor()
    if request.method == "POST":
        # Update general settings
        for key in ['title', 'refresh', 'port', 'minButtonWidth', 'autoUpdate', 'autoUpdateURL']:
            if key in request.form:
                update_setting(key, request.form[key])

        # Update device solutions
        for i, device in enumerate(devices):
            solution_key = f"device_solution_{i}"
            if solution_key in request.form:
                update_device_solution(device['id'], request.form[solution_key])

        # Update 'exclude_from_all' list
        excluded_ids = request.form.getlist("exclude_from_all")
        cursor.execute('DELETE FROM excluded_devices')
        for device_id in excluded_ids:
            cursor.execute('INSERT INTO excluded_devices (device_id) VALUES (?)', (device_id,))
        db.commit()

        # Reload global config variables
        load_config_from_db()
        updateSwitches()
        logging.info("Settings updated successfully")
        return redirect("/")
    
    # Load current settings
    config_for_template = get_all_settings()

    # Ensure essential settings are displayed even if not in DB
    defaults = {
        'title': title,
        'refresh': refresh,
        'port': port,
        'minButtonWidth': minButtonWidth,
        'autoUpdate': config.get('autoUpdate', 'False'),
        'autoUpdateURL': config.get('autoUpdateURL', '')
    }
    for key, value in defaults.items():
        if key not in config_for_template:
            config_for_template[key] = value

    config_for_template['exclude_from_all'] = [row[0] for row in cursor.execute('SELECT device_id FROM excluded_devices').fetchall()]
    db.close()
    return render_template("settings.html", config=config_for_template, devices=devices, title="Settings")

@app.route("/delete_device/<device_id>")
def delete_device(device_id):
    global config, devices, switches

    # Find and remove the device from the global 'devices' list
    device_to_remove = next((d for d in devices if d.get('id') == device_id), None)
    if device_to_remove:
        devices.remove(device_to_remove)
        logging.info(f"Removed device {device_to_remove.get('name')} from runtime list.")

    # Remove from switches dictionary
    if device_id in switches:
        del switches[device_id]
        logging.info(f"Removed switch {device_id} from runtime dictionary.")

    # Remove from database
    db = get_db_conn()
    db.execute('DELETE FROM devices WHERE id = ?', (device_id,))
    db.commit()
    db.close()
    return redirect("/settings")

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    global devices, config
    if request.method == "POST":
        schedules = []
        schedule_ids = request.form.getlist("schedule_id")
        schedule_names = request.form.getlist("schedule_name")
        schedule_actions = request.form.getlist("schedule_action")
        schedule_times = request.form.getlist("schedule_time")

        for i in range(len(schedule_ids)):
            sid = schedule_ids[i]
            if not sid:
                sid = str(uuid4())
            name = schedule_names[i]
            action = schedule_actions[i].lower()
            days = request.form.getlist(f"schedule_days_{i}")
            time_str = schedule_times[i]
            device_list = request.form.getlist(f"schedule_devices_{i}")
            schedules.append({
                "id": sid,
                "name": name,
                "action": action,
                "days": days,
                "time": time_str,
                "devices": device_list
            })
        
        # Save schedules to DB
        db = get_db_conn()
        cursor = db.cursor()
        cursor.execute('DELETE FROM schedules')
        cursor.execute('DELETE FROM schedule_days')
        cursor.execute('DELETE FROM schedule_devices')
        for s in schedules:
            cursor.execute('INSERT INTO schedules (id, name, action, time) VALUES (?, ?, ?, ?)', (s['id'], s['name'], s['action'], s['time']))
            for day in s['days']:
                cursor.execute('INSERT INTO schedule_days (schedule_id, day) VALUES (?, ?)', (s['id'], day))
            for dev_id in s['devices']:
                cursor.execute('INSERT INTO schedule_devices (schedule_id, device_id) VALUES (?, ?)', (s['id'], dev_id))
        db.commit()
        db.close()

        updateApScheduler()
        return redirect("/")
    
    # GET method: show schedules and devices
    schedules = get_schedules_from_db()
    return render_template("schedule.html", schedules=schedules, devices=devices, title="Schedule Configuration")

# ---------- End Routing Functions ---------- #
# ---------- Start Functions ---------- #

def getRequestInfo():
    # Get IP address
    forwarded_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Get browser details
    user_agent = request.user_agent.string

    return {
        "IP Address": forwarded_ip,
        "Browser": user_agent
    }

def updateApScheduler():
    """
    Updates the APScheduler with the current schedules.
    This function should be called whenever schedules are modified.
    """
    scheduler.remove_all_jobs()
    # create schedluer to run every 5 minutes
    scheduler.add_job(func=updateSwitches, trigger="interval", minutes=int(refresh))
    # create schedluer to run once a day
    scheduler.add_job(func=scan_and_save_new_devices, trigger="interval", hours=1)

    for schedule in config.get("schedules", []):
        days_of_week = schedule.get('days')
        if days_of_week:  # Only add job if days are specified
            scheduler.add_job(
                func=executeSchedule,
                trigger='cron',
                day_of_week=','.join(days_of_week),
                hour=int(schedule['time'].split(':')[0]),
                minute=int(schedule['time'].split(':')[1]),
                args=[schedule['action'], schedule['devices']],
            )
        else:
            logging.warning(f"Skipping schedule '{schedule.get('name')}' because no days are configured.")

    print("Scheduler updated with new schedules.")
    logging.info("Scheduler updated with new schedules.")

def executeSchedule(action, scheduledDevices):
    """
    Executes the action for the given schedule.
    This function should be called by the scheduler.
    """
    #print(f"Executing action: {action}")
    #print(f"Devices to control: {scheduledDevices}")
    # Here you would add the logic to turn on/off devices
    #print(devices)
    #print("--------------")
    #print(config["devices"])
    for device_id in scheduledDevices:
        for device in devices:
            if device["id"] == device_id:
                switch = switches.get(device_id)
                try:
                    if action == "on":
                        switch.turn_on()
                        device["state"] = True
                    elif action == "off":
                        switch.turn_off()
                        device["state"] = False
                    print(f"Action {action} executed on device {device['name']}")
                    logging.info(f"Action {action} executed on device {device['name']}")
                except Exception as e:
                    print(f"Error executing action {action} on device {device['name']}: {e}")
                    logging.error(f"Error executing action {action} on device {device['name']}: {e}")
                break  # Exit the loop after finding the device

def sortDevicesByName(newDict):
    """
    Sorts the devices list by the 'solution' key.
    """
    return sorted(newDict, key=lambda x: x.get('solution', '').lower())

def search_partial_key(dictionary, partial_key):
    matching_keys = [key for key in dictionary.keys() if partial_key in key]
    return matching_keys

# ---------- Database Functions ---------- #

def get_db_conn():
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    # Devices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            name TEXT,
            solution TEXT,
            ip TEXT,
            key TEXT,
            ver TEXT
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
    conn.close()

def migrate_json_to_db():
    if not os.path.isfile(settingsFile):
        return # No JSON file to migrate

    print("Migrating data from appConfig.json to tuya.db...")
    with open(settingsFile, 'r') as f:
        json_config = json.load(f)

    db = get_db_conn()
    cursor = db.cursor()

    # Migrate settings
    for key, value in json_config.items():
        if key not in ['devices', 'schedules', 'exclude_from_all']:
            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))

    # Migrate devices
    for device in json_config.get('devices', []):
        cursor.execute('INSERT OR REPLACE INTO devices (id, name, solution, ip, key, ver) VALUES (?, ?, ?, ?, ?, ?)',
                       (device['id'], device['name'], device.get('solution', device['name']), device['ip'], device['key'], device.get('ver', '3.3')))

    # Migrate excluded devices
    for device_id in json_config.get('exclude_from_all', []):
        cursor.execute('INSERT OR REPLACE INTO excluded_devices (device_id) VALUES (?)', (device_id,))

    # Migrate schedules
    for schedule in json_config.get('schedules', []):
        cursor.execute('INSERT OR REPLACE INTO schedules (id, name, action, time) VALUES (?, ?, ?, ?)',
                       (schedule['id'], schedule['name'], schedule['action'], schedule['time']))
        for day in schedule.get('days', []):
            cursor.execute('INSERT OR REPLACE INTO schedule_days (schedule_id, day) VALUES (?, ?)', (schedule['id'], day))
        for dev_id in schedule.get('devices', []):
            cursor.execute('INSERT OR REPLACE INTO schedule_devices (schedule_id, device_id) VALUES (?, ?)', (schedule['id'], dev_id))

    db.commit()
    db.close()
    # Rename old config file to prevent re-migration
    os.rename(settingsFile, settingsFile + '.migrated')
    print("Migration complete. Old config file renamed to appConfig.json.migrated")

def get_all_settings():
    db = get_db_conn()
    settings_dict = {row['key']: row['value'] for row in db.execute('SELECT * FROM settings').fetchall()}
    db.close()
    return settings_dict

def update_setting(key, value):
    db = get_db_conn()
    db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    db.commit()
    db.close()

def update_device_solution(device_id, solution):
    db = get_db_conn()
    db.execute('UPDATE devices SET solution = ? WHERE id = ?', (solution, device_id))
    db.commit()
    db.close()

def get_schedules_from_db():
    db = get_db_conn()
    schedules_list = []
    schedules = db.execute('SELECT * FROM schedules').fetchall()
    for s in schedules:
        schedule_dict = dict(s)
        days = db.execute('SELECT day FROM schedule_days WHERE schedule_id = ?', (s['id'],)).fetchall()
        schedule_dict['days'] = [row['day'] for row in days]
        devices_in_schedule = db.execute('SELECT device_id FROM schedule_devices WHERE schedule_id = ?', (s['id'],)).fetchall()
        schedule_dict['devices'] = [row['device_id'] for row in devices_in_schedule]
        schedules_list.append(schedule_dict)
    db.close()
    return schedules_list

# ---------- End Database Functions ---------- #

def get_modified_date(url):
    try:
        response = requests.head(url)  # Use HEAD request to get headers
        if 'Last-Modified' in response.headers:
            return response.headers['Last-Modified']
        else:
            return "No Last-Modified header found."
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"

def check_update(fileURL):
    getFileDate = get_modified_date(fileURL)
    if "An error occurred" in getFileDate or "No Last-Modified header found." in getFileDate:
        print(getFileDate)
        return
    
    newVersionDT = datetime.strptime(getFileDate, "%a, %d %b %Y %H:%M:%S %Z")
    versionDt = datetime.strptime(VERSION, "%Y.%m.%d")
    print(f"Current Version Date: {versionDt}")
    print(f"New Version Date: {newVersionDT}")
    if versionDt.date() < newVersionDT.date():
        logging.info("Update available!")
        print(f"Download link: {fileURL}")
        download_and_replace(fileURL)
    else:
        print("You are using the latest version.")

def download_and_replace(download_url):
    exe_path = sys.argv[0]
    tmp_path = exe_path + ".new"
    print(f"Downloading update from {download_url}...")
    r = requests.get(download_url, stream=True)
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(r.raw, f)
    print("Download complete.")
    # Create a batch file to replace the running exe after exit for windows
    bat_path = exe_path + ".bat"
    with open(bat_path, "w") as bat:
        bat.write(f"""@echo off
ping 127.0.0.1 -n 3 > nul
move /Y "{tmp_path}" "{exe_path}"
start "" "{exe_path}"
del "%~f0"
""")
    print("Restarting with update...")
    os.startfile(bat_path)

    # Create a batch file to replace the running exe after exit for linux
    if OS == "Linux":
        bat_path = exe_path + ".sh"
        with open(bat_path, "w") as bat:
            bat.write(f"""#!/bin/bash
sleep 3
mv -f "{tmp_path}" "{exe_path}"
"./{exe_path}"
""")
        os.chmod(tmp_path, 0o755)
        print("Restarting with update...")
        os.system(f"sh {bat_path}")

    sys.exit(0)

def updateSwitches():
    for device in devices:
        try:
            switch = tinytuya.OutletDevice(dev_id=device['id'],
                address=device['ip'],
                local_key=device['key'],
                version=device['ver'])
            switches[device['id']] = switch
            data = switch.status()["dps"]
            #print(data)
            device["state"] = data.get("1", "offline")
            device["voltage"] = int(data.get("20", 0))/10
            device["power"] = int(data.get("19", 0))
        except Exception as error:
            logging.error(f"Error updating switch {device['id']}: {error}")
            switches[device['id']] = None
            device["state"] = "offline"
            device["voltage"] = 0
            device["power"] = 0

def mergeDevices(dict1, dict2):
    """
    Merges two dictionaries recursively.
    If a key exists in both dictionaries, the value from dict2 will not overwrite the value from dict1.
    Update IP adrress from 2 dictionary
    """
    #print(dict1)
    #print("----------")
    #print(dict2)
    for item2 in dict2:
        deviceNotFound = True
        for item1 in dict1["devices"]:
            # ... (This function is now replaced by DB logic)
            pass
        if deviceNotFound:
            # ... (This function is now replaced by DB logic)
            pass

def scanNewDevices():
    logging.info("Scanning for new devices...")
    return tinytuya.deviceScan(False, 20)

def scan_and_save_new_devices():
    """Scans for new devices and adds them to the database."""
    logging.info("Executing scheduled scan for new devices...")
    newly_scanned_devices = scanNewDevices()
    if not newly_scanned_devices:
        logging.info("No new devices found during scheduled scan.")
        return

    db = get_db_conn()
    for key, device_data in newly_scanned_devices.items():
        if device_data.get("ip"):
            logging.info(f"Found device: {device_data['name']}. Adding/updating in DB.")
            db.execute('INSERT OR IGNORE INTO devices (id, name, solution, ip, key, ver) VALUES (?, ?, ?, ?, ?, ?)',
                       (device_data['id'], device_data['name'], device_data['name'], device_data['ip'], device_data['key'], device_data.get('version', '3.3')))
            db.execute('UPDATE devices SET ip = ? WHERE id = ?', (device_data['ip'], device_data['id']))
    db.commit()
    db.close()
    logging.info("Finished processing devices from scheduled scan.")

def start_scheduler():
    scheduler.start()

def load_config_from_db():
    global config, devices, title, refresh, port, minButtonWidth
    
    db = get_db_conn()
    
    # Load settings
    settings_from_db = {row['key']: row['value'] for row in db.execute('SELECT * FROM settings').fetchall()}
    title = settings_from_db.get("title", "Tuya App")
    refresh = int(settings_from_db.get("refresh", 5))
    port = int(settings_from_db.get("port", 8080))
    minButtonWidth = int(settings_from_db.get("minButtonWidth", 300))

    # Load devices
    devices_from_db = db.execute('SELECT * FROM devices ORDER BY solution COLLATE NOCASE').fetchall()
    devices = [dict(row) for row in devices_from_db]

    # Load schedules into a config-like dictionary for the scheduler
    schedules = get_schedules_from_db()
    
    # Load excluded devices
    excluded_from_db = db.execute('SELECT device_id FROM excluded_devices').fetchall()
    excluded_devices = [row['device_id'] for row in excluded_from_db]

    config = {
        **settings_from_db,
        "devices": devices,
        "schedules": schedules,
        "exclude_from_all": excluded_devices
    }
    db.close()

def download_file_with_progress(url, destination_path):
    """Downloads a file from a URL to a destination, showing a progress bar."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        total_size = int(response.headers.get('content-length', 0))
        
        with open(destination_path, 'wb') as f:
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded_size += len(chunk)
                done = int(50 * downloaded_size / total_size) if total_size > 0 else 0
                sys.stdout.write(f'\r[{"#" * done}{"-" * (50 - done)}] {downloaded_size / 1048576:.2f} MB / {total_size / 1048576:.2f} MB')
                sys.stdout.flush()
        print(f"\nDownloaded {os.path.basename(destination_path)} successfully.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"\nError downloading {url}: {e}")
        return False
    
# ---------- End Functions ---------- #

OS = platform.system()
# Get the current working
# directory (CWD)

#download devices.json file
download_file_with_progress(DEVICES_URL, os.path.join(cwd, "devices.json"))

"""
try:
    this_file = __file__
except NameError:
    this_file = sys.argv[0]
this_file = os.path.abspath(this_file)
if getattr(sys, 'frozen', False):
    cwd = os.path.dirname(sys.executable)
    #copy devices.json to cwd
    
    devicesFile = os.path.join(cwd, "devices.json")
    if not os.path.isfile(devicesFile):
        devicesFileCopy = os.path.join(bundle_dir, "devices.json")
        if os.path.isfile(devicesFileCopy):
            #copy devices.json to cwd
            #print("Copying devices.json to cwd")
            with open(devicesFileCopy, "r") as f:
                data = f.read()
            with open(devicesFile, "w") as f:
                f.write(data)

else:
    cwd = os.path.dirname(this_file)
"""

print("Current working directory:", cwd)
#index file
db_file = os.path.join(cwd, 'tuya.db')
settingsFile = os.path.join(cwd, "appConfig.json")

#templateFolder = os.path.join(cwd, "templates")

#Create logging system anda save to log file
# Create a logger
logging.basicConfig(
    filename=os.path.join(cwd, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize DB and migrate if necessary
init_db()
#migrate_json_to_db()

"""
# Read Snapshot File
snapShotFile = os.path.join(cwd, "snapshot.json")
need_scan = False
if not os.path.isfile(snapShotFile):
    print("Snapshot file not found, scanning for devices")
    need_scan = True
else:
    # Check if snapshot.json is older than 1 day
    file_mtime = datetime.fromtimestamp(os.path.getmtime(snapShotFile))
    if (datetime.now() - file_mtime).days >= 1:
        print("Snapshot file is older than 1 day, scanning for devices")
        need_scan = True
"""
snapShotDevices = scanNewDevices()

#make small version of snapshot devices with only name and ip
snapShotDevicesSmall = list()
for key, device in snapShotDevices.items():
    if device["ip"] != "":
        toAdd = {
            "name": device["name"],
            "ip": device["ip"],
            "id": device["id"],
            "key": device["key"],
            "ver": device["version"]
        }
        snapShotDevicesSmall.append(toAdd)

#print("Devices found in snapshot:", snapShotDevicesSmall)

# Load configuration from the database
load_config_from_db()

#check if update is available
if config.get("autoUpdate", False):
    check_update(config["autoUpdateURL"])

# merge newly scanned devices into DB
db = get_db_conn()
for device in snapShotDevicesSmall:
    db.execute('INSERT OR IGNORE INTO devices (id, name, solution, ip, key, ver) VALUES (?, ?, ?, ?, ?, ?)',
               (device['id'], device['name'], device['name'], device['ip'], device['key'], device['ver']))
    db.execute('UPDATE devices SET ip = ? WHERE id = ?', (device['ip'], device['id']))
db.commit()
db.close()

#print(f"Number of columns: {number_columns}")
switches = dict()
updateSwitches()
print("Finished Getting Devices")

#print(devices)
scheduler = BackgroundScheduler()
updateApScheduler()
# Run the scheduler in a separate thread
Thread(target=start_scheduler).start()
print("Scheduler Started")

# Call schedule_device_jobs on startup to schedule existing jobs
#schedule_device_jobs()

if __name__ == '__main__':
    print(f"Tuya Server Running on http://localhost:{port}")
    #app.run(host='0.0.0.0', port=port, debug=True)
    if OS == "Windows":
        os.system(f"start http://localhost:{port}")
    else:
        subprocess.run(["xdg-open", f"http://localhost:{port}"], stderr=subprocess.DEVNULL)
    serve(app, host="0.0.0.0", port=port)
