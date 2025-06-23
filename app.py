"""
# Install required libraries
 sudo apt-get install python-crypto python-pip  # for RPi, Linux
 python3 -m pip install pycryptodome            # or pycrypto or Crypto or pyaes
 python -m tinytuya scan  #scan to get list of local devices
https://pypi.org/project/tinytuya/
https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys
python -m tinytuya wizard (get device id and keys) #Run this command to get the device id and keys
https://pimylifeup.com/raspberry-pi-flask-web-app/
Windows:
pyinstaller --clean --onefile --add-data "templates*;templates." --add-data "devices.json;." -n tuyaServer app.py
Linux:
pyinstaller --clean --onefile --add-data "templates*:." --add-data "devices.json:." -n tuyaServer app.py
"""
import logging
from uuid import uuid4
from flask import Flask, render_template, request, jsonify, redirect #pip install Flask
from flask_restful import Resource, Api #pip install Flask-RESTful
import json
import datetime
import os
import sys
import jinja2
import requests #pip install requests
import tinytuya #pip install tinytuya
from waitress import serve #pip install waitress
from apscheduler.schedulers.background import BackgroundScheduler #pip install apscheduler
from threading import Thread

# ---------- Start Configurations ---------- #
VERSION = "2025.06.21"
print(f"Version: {VERSION}")

template_loader = ''
if getattr(sys, 'frozen', False):
    # for the case of running in pyInstaller's exe
    bundle_dir = sys._MEIPASS
    template_loader = jinja2.FileSystemLoader(
        os.path.join(bundle_dir, 'templates'))
else:
    # for running locally
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

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
            device.get("state", False),
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

@app.route("/settings", methods=["GET", "POST"])
def settings():
    global config, devices, title, refresh, port, minButtonWidth
    if request.method == "POST":
        # Save the updated settings to appConfig.json
        form_data = request.form.to_dict(flat=False)
        # Reconstruct config dict
        with open(settingsFile, "r") as infile:
            current_config = json.load(infile)
        # Update non-devices config keys
        for key in current_config:
            if key != "devices":
                if key in form_data:
                    current_config[key] = form_data[key][0]
        # Update devices list solutions
        devices_list = current_config.get("devices", [])
        for i, device in enumerate(devices_list):
            solution_key = f"device_solution_{i}"
            if solution_key in form_data:
                device["solution"] = form_data[solution_key][0]
                for item in devices:
                    if item["name"] == device["name"]:
                        item["solution"] = device["solution"]
        # Update number_columns setting
        if "minButtonWidth" in form_data:
            try:
                current_config["minButtonWidth"] = int(form_data["minButtonWidth"][0])
            except ValueError:
                pass
        current_config["devices"] = devices_list
        saveConfig(current_config, settingsFile)
        # delete
        #with open(settingsFile, "w") as outfile:
            #json.dump(current_config, outfile, indent=4)

        # Reload global config variables
        config = current_config
        #devices = config.get("devices", [])
        title = config.get("title", title)
        refresh = int(config.get("refresh", refresh))
        port = int(config.get("port", port))
        minButtonWidth = int(current_config.get("minButtonWidth", 3))
        logging.info("Settings updated successfully")
        return redirect("/")
    
    # Load current settings
    with open(settingsFile, "r") as infile:
        current_config = json.load(infile)
    #devices = current_config.get("devices", [])
    # Pass devices separately and config without devices and aschedules
    config_without_devices = {k: v for k, v in current_config.items() if (k != "devices") and (k != "schedules")}
    return render_template("settings.html", config=config_without_devices, devices=devices, title="Settings")

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    global devices, config
    if request.method == "POST":
        form_data = request.form.to_dict(flat=False)
        #print(f"Form Data: {form_data}")
        # Parse form data to update schedules and device associations
        schedules = []
        schedule_ids = request.form.getlist("schedule_id")
        schedule_names = request.form.getlist("schedule_name")
        schedule_actions = request.form.getlist("schedule_action")
        schedule_days = request.form.getlist("schedule_days")
        schedule_times = request.form.getlist("schedule_time")
        deviceKeys = search_partial_key(form_data, "schedule_devices")
        #print(f"List of device Keys: {deviceKeys}")
        deviceList = list()
        for key in deviceKeys:
            deviceList.append(form_data[key])
        #print(f"List of device List: {deviceList}")

        for i in range(len(schedule_ids)):
            sid = schedule_ids[i]
            if not sid:
                sid = str(uuid4())
            name = schedule_names[i]
            action = schedule_actions[i].lower()
            days = schedule_days[i].split(",") if schedule_days[i] else []
            time_str = schedule_times[i]
            schedules.append({
                "id": sid,
                "name": name,
                "action": action,
                "days": days,
                "time": time_str,
                "devices": deviceList[i]
            })
        #config["schedules"] = schedules
        #print(f"Updated Schedules: {schedules}")
        config["schedules"] = schedules
        saveConfig(config, settingsFile)
        updateApScheduler()
        return redirect("/")
    
    # GET method: show schedules and devices
    schedules = config.get("schedules", [])
    
    return render_template("schedule.html", schedules=schedules, devices=devices, title="Schedule Configuration")

# ---------- End Routing Functions ---------- #
# ---------- Start Functions ---------- #

def getRequestInfo():
    # Get IP address
    client_ip = request.remote_addr
    forwarded_ip = request.headers.get('X-Forwarded-For', client_ip)

    # Get browser details
    user_agent = request.user_agent.string

    # Get location data
    #response = requests.get(f"https://ipinfo.io/{forwarded_ip}/json")
    #location_data = response.json()

    return {
        "IP Address": forwarded_ip,
        "Browser": user_agent
    }
    return {
        "IP Address": forwarded_ip,
        "Browser": user_agent,
        "Location": location_data
    }

def updateApScheduler():
    """
    Updates the APScheduler with the current schedules.
    This function should be called whenever schedules are modified.
    """
    scheduler.remove_all_jobs()
    # create schedluer to run every 5 minutes
    scheduler.add_job(func=updateSwitches, trigger="interval", minutes=refresh)
    # create schedluer to run once a day
    scheduler.add_job(func=scanNewDevices, trigger="interval", hours=24)

    for schedule in config.get("schedules", []):
        #print(f"Adding job for schedule: {schedule}")
        scheduler.add_job(
            func=executeSchedule,
            trigger='cron',
            day_of_week=','.join(schedule['days']),
            hour=int(schedule['time'].split(':')[0]),
            minute=int(schedule['time'].split(':')[1]),
            args=[schedule['action'], schedule['devices']],
        )
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

def saveConfig(config, settingsFile):
    # Serializing json
    #sort devices by name
    devices = sortDevicesByName(config["devices"])
    #print(devices)
    #print(f"Saving config:\n {config}")
    json_object = json.dumps(config, indent=4)
    # Writing to config.json
    with open(settingsFile, "w") as outfile:
        outfile.write(json_object)
    print(f"Config saved to {settingsFile}")
    return config

def readConfig(settingsFile):
    
    if os.path.isfile(settingsFile):
        with open(settingsFile) as json_file:
            data = json.load(json_file)
    else:
        data = {
                "title" : "Title",
                "refresh" : 5,
                "port" : 8080,
                "minButtonWidth": 300,
                "schedules": [],
                "devices": []
        }
        #print(data)
        # Serializing json
        #json_object = json.dumps(data, indent=4)
        #print(json_object)
        # Writing to config.json
        saveConfig(data, settingsFile)
        #with open(settingsFile, "w") as outfile:
            #outfile.write(json_object)
    return data

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
            device["voltage"] = int(data.get("20", "0"))/10
        except Exception as error:
            logging.error(f"Error updating switch {device['id']}: {error}")
            switches[device['id']] = None
            device["state"] = "offline"
            device["voltage"] = 0
    return redirect("/")

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
            if item1["id"] == item2["id"]:
                #print(f"Device {item1['name']} already exists, skipping")
                item1["ip"] = item2["ip"]
                deviceNotFound = False
                break
        if deviceNotFound:
            #print(f"Adding device {item2} to dict1")
            dict1["devices"].append({"name": item2["name"],
                                 "solution": item2["name"],
                                 "id": item2["id"],
                                 "ip": item2["ip"],
                                 "key": item2["key"],
                                 "ver": item2["ver"],})

def scanNewDevices():
    tinytuya.scan()
    logging.info("Scanning for new devices...")

def start_scheduler():
    scheduler.start()

# ---------- End Functions ---------- #

# Get the current working
# directory (CWD)
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
    
print("Current working directory:", cwd)
#index file
#templateFolder = os.path.join(cwd, "templates")

#Create logging system anda save to log file
# Create a logger
logging.basicConfig(
    filename=os.path.join(cwd, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Read Snapshot File
snapShotFile = os.path.join(cwd, "snapshot.json")
need_scan = False
if not os.path.isfile(snapShotFile):
    print("Snapshot file not found, scanning for devices")
    need_scan = True
else:
    # Check if snapshot.json is older than 1 day
    file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(snapShotFile))
    if (datetime.datetime.now() - file_mtime).days >= 1:
        print("Snapshot file is older than 1 day, scanning for devices")
        need_scan = True

if need_scan:
    scanNewDevices()

snapShotJson = readConfig(snapShotFile)
snapShotDevices = snapShotJson["devices"]

#make small version of snapshot devices with only name
snapShotDevicesSmall = list()
for device in snapShotDevices:
    if device["ip"] != "":
        toAdd = {
            "name": device["name"],
            "solution": device["name"],
            "ip": device["ip"],
            "id": device["id"],
            "key": device["key"],
            "ver": device["ver"]
        }
        snapShotDevicesSmall.append(toAdd)

#print("Devices found in snapshot:", snapShotDevicesSmall)
# Read Config File
settingsFile = os.path.join(cwd, "appConfig.json")
config = readConfig(settingsFile)
# merge snapShotDevicesSmall into config
mergeDevices(config, snapShotDevicesSmall)
saveConfig(config, settingsFile)

devices = config["devices"]
title = config["title"]
refresh = int(config["refresh"])
port = int(config["port"])
minButtonWidth = int(config.get("minButtonWidth", 300))
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
    print("Server Running on http://localhost")
    #app.run(host='0.0.0.0', port=port, debug=True)
    serve(app, host="0.0.0.0", port=port)
