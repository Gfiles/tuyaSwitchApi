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
        switchInfo.append([device["solution"], device["name"], device["state"], device["voltage"]])
    return render_template("index.html", switches=switchInfo, title=title)

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
    global config, devices, title, refresh, port
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
        current_config["devices"] = devices_list
        with open(settingsFile, "w") as outfile:
            json.dump(current_config, outfile, indent=4)
        # Reload global config variables
        config = current_config
        #devices = config.get("devices", [])
        title = config.get("title", title)
        refresh = int(config.get("refresh", refresh))
        port = int(config.get("port", port))
        return redirect("/")
    
    # Load current settings
    with open(settingsFile, "r") as infile:
        current_config = json.load(infile)
    #devices = current_config.get("devices", [])
    # Pass devices separately and config without devices
    config_without_devices = {k: v for k, v in current_config.items() if k != "devices"}
    return render_template("settings.html", config=config_without_devices, devices=devices, title="Settings")

def readConfig(settingsFile):
    
    if os.path.isfile(settingsFile):
        with open(settingsFile) as json_file:
            data = json.load(json_file)
    else:
        data = {
                "title" : "Title",
                "refresh" : 5,
                "port" : 8080,
                "devices": []
        }
        #print(data)
        for i, device in enumerate(snapShotDevices):
            if device["ip"] != "":
                data["devices"].append({"name": device["name"], "solution": f"solution {i}"})
        # Serializing json
        json_object = json.dumps(data, indent=4)
        #print(json_object)
        # Writing to config.json
        with open(settingsFile, "w") as outfile:
            outfile.write(json_object)
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
                    print(f"{device["name"]} not found")
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
    if not os.path.isfile(devicesFile):
        devicesFile = os.path.join(bundle_dir, "devices.json")
        if os.path.isfile(devicesFile):
            #copy devices.json to cwd
            with open(devicesFile, "r") as f:
                data = f.read()
            with open(os.path.join(cwd, "devices.json"), "w") as f:
                f.write(data)
else:
    cwd = os.path.dirname(this_file)
    
#print("Current working directory:", cwd)
#index file
#templateFolder = os.path.join(cwd, "templates")

# Read Snapshot File
snapShotFile = os.path.join(cwd, "snapshot.json")
if not os.path.isfile(snapShotFile):
    print("Snapshot file not found, scanning for devices")
    tinytuya.scan()
snapShotJson = readConfig(snapShotFile)
snapShotDevices = snapShotJson["devices"]

# Read Config File
settingsFile = os.path.join(cwd, "appConfig.json")
config = readConfig(settingsFile)
devices = config["devices"]
title = config["title"]
refresh = int(config["refresh"])
port = int(config["port"])

updateSwitches()
# create schedluer to run every 5 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(func=updateSwitches, trigger="interval", minutes=refresh)
scheduler.start()
print("Scheduler Started")
print("Finished Getting Devices")

if __name__ == '__main__':
    print("Server Running on http://localhost")
    #app.run(host='0.0.0.0', port=port, debug=True)
    serve(app, host="0.0.0.0", port=port)
