import tinytuya
import logging
import socket

socket.setdefaulttimeout(2.0)

class TuyaClient:
    def __init__(self):
        self.switches = {}

    def get_device(self, device_data):
        dev_id = device_data['id']
        # Always create/update the device instance to ensure latest IP/Key
        try:
            device = tinytuya.OutletDevice(
                dev_id=dev_id,
                address=device_data['ip'],
                local_key=device_data['key'],
                version=device_data.get('ver', '3.3')
            )
            device.set_socketTimeout(2)
            self.switches[dev_id] = device
            return device
        except Exception as e:
            logging.error(f"Error initializing device {dev_id}: {e}")
            return None

    def update_device_status(self, device_data):
        device = self.get_device(device_data)
        if not device:
            return self._offline_status()

        try:
            # tinytuya.status() can be slow or fail if device is offline
            status = device.status()
            if 'dps' in status:
                dps = status['dps']
                return {
                    "state": dps.get("1", False),
                    "voltage": int(dps.get("20", 0)) / 10,
                    "power": int(dps.get("19", 0)),
                    "online": True
                }
        except Exception as e:
            logging.error(f"Error getting status for {device_data['id']}: {e}")
        
        return self._offline_status()

    def _offline_status(self):
        return {
            "state": "offline",
            "voltage": 0,
            "power": 0,
            "online": False
        }

    def turn_on(self, device_data):
        device = self.get_device(device_data)
        if device:
            device.turn_on()
            return True
        return False

    def turn_off(self, device_data):
        device = self.get_device(device_data)
        if device:
            device.turn_off()
            return True
        return False

    def toggle(self, device_data):
        status = self.update_device_status(device_data)
        if status['online']:
            if status['state']:
                return self.turn_off(device_data), False
            else:
                return self.turn_on(device_data), True
        return False, "offline"

    @staticmethod
    def scan_devices():
        logging.info("Scanning for Tuya devices on local network...")
        return tinytuya.deviceScan(False, 20)
