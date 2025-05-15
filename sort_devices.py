import json
import tinytuya
import tinytuya.wizard

def sort_devices_by_name():
    with open('devices.json', 'r', encoding='utf-8') as f:
        devices = json.load(f)

    devices_sorted = sorted(devices, key=lambda d: d.get('name', '').lower())

    with open('devices.json', 'w', encoding='utf-8') as f:
        json.dump(devices_sorted, f, indent=4, ensure_ascii=False)

    print("devices.json has been sorted by 'name'.")

def print_names():
    with open('devices.json', 'r', encoding='utf-8') as f:
        devices = json.load(f)

    testName = list()
    for i in range(1, 9):
            testName.append(f"ydsw00{str(i)}")
    for i in range(10, 99):
            testName.append(f"ydsw0{str(i)}")
    #for i in range(100, 199):
    #        testName.append(f"ydsw{str(i)}")
    

    #print(testName)
    deviceName = list()
    for device in devices:
        #print numbers that doent exist
        deviceName.append(device.get('name', 'No name found').lower())
        #print(deviceName)
    
    for item in testName:    
        if item not in deviceName:
            print(item)
                
if __name__ == "__main__":
    sort_devices_by_name()
    print_names()

