import requests
import logging

class HomeAssistantClient:
    def __init__(self, ha_url, ha_token):
        self.ha_url = ha_url.rstrip('/')
        self.ha_token = ha_token
        self.headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

    def _get_api_url(self, endpoint):
        return f"{self.ha_url}/api{endpoint}"

    def update_device_status(self, device_data):
        entity_id = device_data.get('id')
        if not entity_id or not self.ha_url or not self.ha_token:
            return self._offline_status()

        try:
            url = self._get_api_url(f"/states/{entity_id}")
            response = requests.get(url, headers=self.headers, timeout=5)
            response.raise_for_status()
            
            state_data = response.json()
            state = state_data.get('state') == 'on'
            
            # Additional attributes might not exist or might be called something else. Use what HA provides.
            attributes = state_data.get('attributes', {})
            
            # Start with default checking attributes on the main entity itself
            voltage = attributes.get('voltage', 0)
            power = attributes.get('current_consumption', attributes.get('power', 0))
            current = attributes.get('current', 0)
            
            # For Tuya devices, these metrics are usually split into separate `sensor` entities
            # e.g. switch.yd_switch_1 -> sensor.yd_switch_1_voltage
            # For multi-relay switches like switch.tz3000_..._2, it usually maps to sensor.tz3000_..._voltage_2
            domain = entity_id.split('.')[0]
            if domain in ('switch', 'light'):
                basename = entity_id.split('.')[1]
                
                # Check if it ends with an underscore and a number
                import re
                match = re.search(r'_(\d+)$', basename)
                if match:
                    index = match.group(1)
                    base_without_index = basename[:-len(match.group(0))]
                    sensor_suffix_format = "{suffix}_{index}"
                else:
                    base_without_index = basename
                    index = ""
                    sensor_suffix_format = "{suffix}"
                
                # Helper function to fetch a related sensor value
                def fetch_sensor(suffix):
                    try:
                        suffix_part = sensor_suffix_format.format(suffix=suffix, index=index)
                        sensor_url = self._get_api_url(f"/states/sensor.{base_without_index}_{suffix_part}")
                        res = requests.get(sensor_url, headers=self.headers, timeout=2)
                        if res.status_code == 200:
                            return float(res.json().get('state', 0))
                    except Exception as e:
                        logging.debug(f"Failed to fetch sensor {suffix} for {entity_id}: {e}")
                    return None

                vol_sensor = fetch_sensor('voltage')
                if vol_sensor is not None:
                    voltage = vol_sensor
                    
                pow_sensor = fetch_sensor('power')
                if pow_sensor is not None:
                    power = pow_sensor
                    
                cur_sensor = fetch_sensor('current')
                if cur_sensor is not None:
                    current = cur_sensor
            
            return {
                "state": state,
                "voltage": voltage,
                "power": power,
                "current": current,
                "online": state_data.get('state') not in ['unavailable', 'unknown']
            }
        except Exception as e:
            logging.error(f"Error getting status for {entity_id}: {e}")
            return self._offline_status()

    def _offline_status(self):
        return {
            "state": "offline",
            "voltage": 0,
            "power": 0,
            "current": 0,
            "online": False
        }

    def turn_on(self, device_data):
        return self._call_service(device_data.get('id'), 'turn_on')

    def turn_off(self, device_data):
        return self._call_service(device_data.get('id'), 'turn_off')

    def toggle(self, device_data):
        return self._call_service(device_data.get('id'), 'toggle')

    def _call_service(self, entity_id, action):
        if not entity_id or not self.ha_url or not self.ha_token:
            return False

        try:
            domain = entity_id.split('.')[0]
            url = self._get_api_url(f"/services/{domain}/{action}")
            payload = {"entity_id": entity_id}
            
            response = requests.post(url, headers=self.headers, json=payload, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Error calling {action} for {entity_id}: {e}")
            return False

    def scan_devices(self):
        if not self.ha_url or not self.ha_token:
            logging.warning("Home Assistant URL or Token not configured, skipping scan.")
            return {}

        logging.info("Scanning for entities from Home Assistant...")
        try:
            url = self._get_api_url("/states")
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            entities = response.json()
            scanned = {}
            for entity in entities:
                entity_id = entity.get('entity_id')
                domain = entity_id.split('.')[0]
                
                # Filter for manageable devices (e.g. switch, light, fan)
                if domain in ['switch', 'light', 'fan'] and entity.get('state') not in ['unavailable']:
                    friendly_name = entity.get('attributes', {}).get('friendly_name', entity_id)
                    
                    if friendly_name.upper().startswith('YD'):
                        scanned[entity_id] = {
                            'id': entity_id,
                            'name': friendly_name,
                            'domain': domain
                        }
            return scanned
        except Exception as e:
            logging.error(f"Error scanning Home Assistant entities: {e}")
            return {}
