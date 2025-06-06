"""
# Install required libraries
 sudo apt-get install python-crypto python-pip  # for RPi, Linux
 python3 -m pip install pycryptodome            # or pycrypto or Crypto or pyaes
 python -m tinytuya scan  #scan to get list of local devices
https://pypi.org/project/tinytuya/
https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys
python -m tinytuya wizard (get device id and keys) #Run this command to get the device id and keys
https://pimylifeup.com/raspberry-pi-flask-web-app/

pyinstaller --clean --onefile --add-data "templates*;templates." --add-data "devices.json;." -n tuyaServer app.py
"""
from flask import Flask, render_template, request, jsonify, redirect#pip install Flask
from flask_restful import Resource, Api #pip install Flask-RESTful
import json
import datetime
import os
import sys
import jinja2
import tinytuya #pip install tinytuya
from waitress import serve #pip install waitress
from apscheduler.schedulers.background import BackgroundScheduler #pip install apscheduler

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

class On(Resource):
    def get(self, pk):
        pk = pk.upper()
        print(f"get On input {pk}")
        for device in devices:
            if device["name"].upper() == pk:
                try:
                    switch = device["switch"]
                    switch.turn_on()
                    device["state"] = True
                except:
                    return "error"
                return f"{device['name']} Switch Turned On"

class Off(Resource):
    def get(self, pk):
        pk = pk.upper()
        for device in devices:
            if device["name"].upper() == pk:
                try:
                    switch = device["switch"]
                    switch.turn_off()
                    device["state"] = False
                except:
                    return "error"
                return f"{device['name']} Switch Turned Off"

class Status(Resource):
    def get(self, pk):
        pk = pk.upper()
        for device in devices:
            if device["name"].upper() == pk:
                try:
                    switch = device["switch"]
                    if switch.status()['dps']['1']:
                        status = "On"
                        #device["state"] = True
                    else:
                        status = "Off"
                        #device["state"] = False
                except:
                    return f"{device['name']} Status: Offline"
                return f"{device['name']} Status: {status}"

#api.add_resource(Items, '/')
api.add_resource(On, '/on/<pk>')
api.add_resource(Off, '/off/<pk>')
api.add_resource(Status, '/status/<pk>')

@app.route("/")
def index():
    switchInfo = []
    for device in devices:
        switchInfo.append([
            device.get("solution", ""),
            device.get("name", ""),
            device.get("state", False),
            device.get("voltage", 0)
        ])
    return render_template("index.html", switches=switchInfo, title=title, minButtonWidth=minButtonWidth)

# Route for toggling a switch
@app.route("/toggle/<pk>")
def toggle_switch(pk):
    #i = int(device_id) - 1
    print(f"get Toggle input {pk}")
    for device in devices:
        if device["name"].upper() == pk.upper():
            #print(f"Device {pk} found")
            switch = device["switch"]
            print(switch)
            #print(switch.status())
            try:
                current_state = switch.status()["dps"]["1"]
                print(f"Current State: {current_state}")
                #new_state = 1 if current_state == 0 else 0
                if current_state:
                    switch.turn_off()
                    device["state"] = False
                else:
                    switch.turn_on()
                    device["state"] = True
            except:
                print("Sem Conexão com a Tomada")
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
        return redirect("/")
    
    # Load current settings
    with open(settingsFile, "r") as infile:
        current_config = json.load(infile)
    #devices = current_config.get("devices", [])
    # Pass devices separately and config without devices
    config_without_devices = {k: v for k, v in current_config.items() if k != "devices"}
    return render_template("settings.html", config=config_without_devices, devices=devices, title="Settings")

def saveConfig(config, settingsFile):
    # Serializing json
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
                "devices": []
        }
        #print(data)
        # Serializing json
        json_object = json.dumps(data, indent=4)
        #print(json_object)
        # Writing to config.json
        saveConfig(json_object, settingsFile)
        #with open(settingsFile, "w") as outfile:
            #outfile.write(json_object)
    return data

def updateSwitches():
    for device in devices:
        noDevice = True
        for snap in snapShotDevices:
            if device["name"] == snap["name"]:
                try:
                    switch = tinytuya.OutletDevice(dev_id=snap['id'],
                        address=snap['ip'],
                        local_key=snap['key'],
                        version=snap['ver'])
                    device["switch"] = switch
                    data = switch.status()
                    device["state"] = data["dps"]["1"]
                    device["voltage"] = data["dps"]["20"]/10
                    noDevice = False
                except:
                    pass
                    #print(f"{device["name"]} not found")
                    #device["switch"] = None
                #print(f"Device {device} found")
                break
        if noDevice:
            print(f"{device["name"]} not found in snapshot")
            device["switch"] = None
            device["state"] = "offline"
            device["voltage"] = 0
    return redirect("/")

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
    #print(devicesFile)
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
    tinytuya.scan()

snapShotJson = readConfig(snapShotFile)
snapShotDevices = snapShotJson["devices"]

#make small version of snapshot devices with only name
snapShotDevicesSmall = {"devices": []}
for device in snapShotDevices:
    if ("ip" in device) and (device["ip"] != ""):
        toAdd = {
            "name": device["name"],
            "solution": device["name"]    
        }
        snapShotDevicesSmall["devices"].append(toAdd)

#print("Devices found in snapshot:", snapShotDevicesSmall)
# Read Config File
settingsFile = os.path.join(cwd, "appConfig.json")
config = readConfig(settingsFile)
# merge snapShotDevicesSmall into config
snapShotDevicesSmall.update(config)  # Merge snapshot devices into config
#print(snapShotDevicesSmall)
config = snapShotDevicesSmall  # Update config with snapshot devices
saveConfig(config, settingsFile)
devices = config["devices"]
title = config["title"]
refresh = int(config["refresh"])
port = int(config["port"])
minButtonWidth = int(config.get("minButtonWidth", 300))
#print(f"Number of columns: {number_columns}")

updateSwitches()
# create schedluer to run every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(func=updateSwitches, trigger="interval", minutes=refresh)
scheduler.start()
print("Scheduler Started")
print("Finished Getting Devices")

from flask import flash, url_for

# Dictionary to keep track of scheduled jobs by device name
scheduled_jobs = {}

def clear_scheduled_jobs():
    for job_id in list(scheduled_jobs.values()):
        try:
            scheduler.remove_job(job_id)
        except:
            pass
    scheduled_jobs.clear()

def schedule_device_jobs():
    clear_scheduled_jobs()
    for device in devices:
        schedule_list = device.get("schedule", [])
        for idx, entry in enumerate(schedule_list):
            time_str = entry.get("time")
            action = entry.get("action", "").lower()
            if not time_str or action not in ["on", "off"]:
                continue
            try:
                hour, minute = map(int, time_str.split(":"))
            except:
                continue
            job_id = f"{device['name']}_{idx}"
            # Remove existing job if any
            if job_id in scheduled_jobs:
                try:
                    scheduler.remove_job(job_id)
                except:
                    pass
            # Schedule job
            if action == "on":
                scheduler.add_job(func=lambda d=device: d["switch"].turn_on() if d["switch"] else None,
                                  trigger="cron", hour=hour, minute=minute, id=job_id)
            else:
                scheduler.add_job(func=lambda d=device: d["switch"].turn_off() if d["switch"] else None,
                                  trigger="cron", hour=hour, minute=minute, id=job_id)
            scheduled_jobs[job_id] = job_id

from uuid import uuid4

def get_schedule_by_id(schedule_id):
    for schedule in config.get("schedules", []):
        if schedule["id"] == schedule_id:
            return schedule
    return None

def schedule_device_jobs():
    clear_scheduled_jobs()
    schedules = config.get("schedules", [])
    devices_map = {device["name"]: device for device in devices}
    for schedule in schedules:
        schedule_id = schedule["id"]
        action = schedule.get("action", "").lower()
        days = schedule.get("days", [])
        time_str = schedule.get("time", "")
        if not time_str or action not in ["on", "off"] or not days:
            continue
        try:
            hour, minute = map(int, time_str.split(":"))
        except:
            continue
        # Find devices associated with this schedule
        associated_devices = [device for device in devices if schedule_id in device.get("schedules", [])]
        for device in associated_devices:
            job_id = f"{device['name']}_{schedule_id}"
            if job_id in scheduled_jobs:
                try:
                    scheduler.remove_job(job_id)
                except:
                    pass
            # Schedule job for each day
            for day in days:
                scheduler.add_job(func=lambda d=device, a=action: d["switch"].turn_on() if a == "on" and d["switch"] else d["switch"].turn_off() if d["switch"] else None,
                                  trigger="cron", day_of_week=day.lower(), hour=hour, minute=minute, id=job_id)
            scheduled_jobs[job_id] = job_id

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    global devices, config
    if request.method == "POST":
        # Parse form data to update schedules and device associations
        schedules = []
        schedule_ids = request.form.getlist("schedule_id")
        schedule_names = request.form.getlist("schedule_name")
        schedule_actions = request.form.getlist("schedule_action")
        schedule_days = request.form.getlist("schedule_days")
        schedule_times = request.form.getlist("schedule_time")
        #schedule_devices = request.form.getlist("device_schedule_ids")
        # Remove empty schedule names and their corresponding data

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
                "time": time_str
            })
        config["schedules"] = schedules

        # Update device schedule associations
        for device in devices:
            device_schedule_ids = request.form.getlist(f"device_{device['name']}_schedules")
            device["schedules"] = device_schedule_ids

        # Remove non-serializable keys before saving
        for device in devices:
            if "switch" in device:
                device["switch"] = None

        config["devices"] = devices
        saveConfig(config, settingsFile)
        # delete
        #with open(settingsFile, "w") as outfile:
            #json.dump(config, outfile, indent=4)
        schedule_device_jobs()
        flash("Schedules updated successfully.")
        return redirect(url_for("schedule"))

    # GET method: show schedules and devices
    schedules = config.get("schedules", [])
    """
    #devices_map = {device["name"]: device for device in devices}
    # Prepare schedule info with associated devices
    schedule_info = []
    for schedule in schedules:
        #associated_devices = [device["name"] for device in devices if schedule["id"] in device.get("schedules", [])]
        schedule_info.append({
            "id": schedule.get("id", ""),
            "name": schedule.get("name", ""),
            "action": schedule.get("action", ""),
            "days": schedule.get("days", []),
            "time": schedule.get("time", ""),
            "devices": schedule.get("devices", ""),
        })
    """
    return render_template("schedule.html", schedules=schedules, devices=devices, title="Schedule Configuration")

# Call schedule_device_jobs on startup to schedule existing jobs
#schedule_device_jobs()

if __name__ == '__main__':
    print("Server Running on http://localhost")
    app.run(host='0.0.0.0', port=port, debug=True)
    #serve(app, host="0.0.0.0", port=port)
