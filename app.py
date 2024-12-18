"""
# Install required libraries
 sudo apt-get install python-crypto python-pip  # for RPi, Linux
 python3 -m pip install pycryptodome            # or pycrypto or Crypto or pyaes
 python -m tinytuya scan
https://pypi.org/project/tinytuya/
https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys
python -m tinytuya wizard (get device id and keys)
https://pimylifeup.com/raspberry-pi-flask-web-app/
"""
from flask import Flask, render_template, request, jsonify, redirect#pip install Flask
from flask_restful import Resource, Api
import json
import os
import sys
import tinytuya
from waitress import serve

app = Flask(__name__)
api = Api(app)

"""
devices = {
    63:{"name":'YDSw063',
       "id": "eb6d1c9836fc552104rajh",
        "key": "at(~_uM*LS)@GASP",
        "ip" : "192.168.31.147"},
    36:{"name": "YDSW036",
        "id": "eb19fc8c00ce8b7e46bjjb",
        "key": "t&+c^e+wgJd5BbUk",
        "ip" : "192.168.31.148"},
    42:{"name": "YDSW042",
        "id": "eb6e6020d2f1744361pmkz",
        "key": "sS@0Lk3Pgoo0/Mf)",
        "ip" : "192.168.31.100"},
}
"""
class On(Resource):
    def get(self, pk):
        switch = tinytuya.OutletDevice(dev_id=devices[pk]['id'],
                address=devices[pk]['ip'],
                local_key=devices[pk]['key'],
                version=3.4)
        switch.turn_on()
        return f"{devices[pk]['name']} Switch Turned On"

class Off(Resource):
    def get(self, pk):
        switch = tinytuya.OutletDevice(dev_id=devices[pk]['id'],
                address=devices[pk]['ip'],
                local_key=devices[pk]['key'],
                version=3.4)
        switch.turn_off()
        return f"{devices[pk]['name']} Switch Turned Off"

class Status(Resource):
    def get(self, pk):
        print(devices[pk]['name'])
        switch = tinytuya.OutletDevice(dev_id=devices[pk]['id'],
                address=devices[pk]['ip'],
                local_key=devices[pk]['key'],
                version=3.4)
        #switch.turn_off()
        if switch.status()['dps']['1']:
            status = "On"
        else:
            status = "Off"
        #print("Switch Turned off")
        return f"{devices[pk]['name']} Status: {status}"

#api.add_resource(Items, '/')
api.add_resource(On, '/on/<pk>')
api.add_resource(Off, '/off/<pk>')
api.add_resource(Status, '/status/<pk>')

@app.route("/")
def index():
    switchInfo = []
    i = 0
    print(switches[0])
    for pk in devices:
        try:
            #print(pk)
            if switches[0] == None:
                switchInfo.append([devices[pk]["name"], pk, "offline", 0])
            else:
                data = switches[i].status()
                #print(data)
                #print(data)
                switch_state = data["dps"]["1"]
                voltage = data["dps"]["20"]
                switchTemp = [devices[pk]["name"], pk, switch_state, voltage/10]
                switchInfo.append(switchTemp)
            i = i + 1
        except Exception as error:
            print("An exception occurred:", error)
        #print(switchInfo)
    return render_template("index.html", switches=switchInfo, title=title)

# Route for toggling a switch
@app.route("/toggle/<device_id>")
def toggle_switch(device_id):
    i = int(device_id) - 1
    current_state = switches[i].status()["dps"]["1"]
    #new_state = 1 if current_state == 0 else 0
    if current_state:
        switches[i].turn_off()
    else:
        switches[i].turn_on()
    return redirect("/")

def readConfig():
    settingsFile = os.path.join(cwd, "config.json")
    if os.path.isfile(settingsFile):
        with open(settingsFile) as json_file:
            data = json.load(json_file)
    else:
        data = {
                "title" : "Title",
                "devices": {
                    "YDSw063":{
                        "name":"Solution1",
                        "id":"abcefghijklmnop",
                        "ip":"192.168.31.147",
                        "key":"key_password"
                    },
                    "YDSw036":{
                        "name":"Solution2",
                        "id":"abcefghijklmnop",
                        "ip":"192.168.31.148",
                        "key":"key_password"
                    },
                }
        }
        # Serializing json
        json_object = json.dumps(data, indent=4)

        # Writing to config.json
        with open(settingsFile, "w") as outfile:
            outfile.write(json_object)
    return data

# Get the current working
# directory (CWD)
try:
    this_file = __file__
except NameError:
    this_file = sys.argv[0]
this_file = os.path.abspath(this_file)
if getattr(sys, 'frozen', False):
    cwd = os.path.dirname(sys.executable)
else:
    cwd = os.path.dirname(this_file)
    
#print("Current working directory:", cwd)

# Read Config File
config = readConfig()
devices = config["devices"]
title = config["title"]

switches = list()
for pk in devices:
    try:
        new_device = tinytuya.OutletDevice(dev_id=devices[pk]['id'],
                address=devices[pk]['ip'],
                local_key=devices[pk]['key'],
                version=3.4)
        switches.append(new_device)
    except:
        print(f"{item[0]} not found")
        switches.append(None)

if __name__ == '__main__':
    print("Server Running on http://localhost")
    app.run(host='0.0.0.0', debug=True)
    #serve(app, host="0.0.0.0", port=80)
