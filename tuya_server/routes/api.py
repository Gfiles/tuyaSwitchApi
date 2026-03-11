from flask import Blueprint, jsonify, current_app
from flask_restful import Api, Resource
from ..security import require_api_key

api_bp = Blueprint('api', __name__, url_prefix='/api')
api = Api(api_bp)

class DeviceStatus(Resource):
    def get(self, pk):
        db = current_app.config['DB']
        client = current_app.config['TUYA_CLIENT']
        
        # Get device info from DB
        devices = db.get_devices()
        device_data = next((d for d in devices if d['id'] == pk), None)
        
        if not device_data:
            return {"error": "Device not found"}, 404
            
        status = client.update_device_status(device_data)
        return {
            "name": device_data['name'],
            "status": "On" if status['state'] is True else "Off" if status['state'] is False else "Offline",
            "voltage": status['voltage'],
            "power": status['power']
        }

class DeviceOn(Resource):
    @require_api_key
    def get(self, pk):
        db = current_app.config['DB']
        client = current_app.config['TUYA_CLIENT']
        
        devices = db.get_devices()
        device_data = next((d for d in devices if d['id'] == pk), None)
        
        if not device_data:
            return {"error": "Device not found"}, 404
            
        if client.turn_on(device_data):
            return {"message": f"Switch {pk} turned on"}
        return {"error": "Failed to turn on device"}, 500

class DeviceOff(Resource):
    @require_api_key
    def get(self, pk):
        db = current_app.config['DB']
        client = current_app.config['TUYA_CLIENT']
        
        devices = db.get_devices()
        device_data = next((d for d in devices if d['id'] == pk), None)
        
        if not device_data:
            return {"error": "Device not found"}, 404
            
        if client.turn_off(device_data):
            return {"message": f"Switch {pk} turned off"}
        return {"error": "Failed to turn off device"}, 500

api.add_resource(DeviceStatus, '/status/<pk>')
api.add_resource(DeviceOn, '/on/<pk>')
api.add_resource(DeviceOff, '/off/<pk>')
