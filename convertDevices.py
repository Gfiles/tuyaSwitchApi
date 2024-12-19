import json

with open("devices.json") as json_file:
    devices = json.load(json_file)

deviceList = dict()
for device in devices:
    if device["ip"] != "":
        item = dict()
        item["name"] = device["name"]
        item["id"] = device["id"]
        item["key"] = device["key"]
        item["ip"] = device["ip"]
        item["version"] = device["version"]
        deviceList[device["name"].upper()] = item
    
config = dict()
config["title"] = "Title"
config["devices"] = deviceList
#print(config)
json_object = json.dumps(config, indent=4)

# Writing to config.json
with open("config.json", "w") as outfile:
    outfile.write(json_object)

print("Finished")
