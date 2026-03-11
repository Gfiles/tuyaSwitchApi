import os
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from .models import TuyaDatabase
from .client import TuyaClient

class TuyaServer:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.db_path = os.path.join(root_dir, 'tuya.db')
        self.db = TuyaDatabase(self.db_path)
        self.client = TuyaClient()
        self.scheduler = BackgroundScheduler()
        self.app = Flask(__name__, 
                         template_folder=os.path.join(root_dir, 'templates'),
                         static_folder=os.path.join(root_dir, 'static'))

    def setup(self):
        # Configure app
        self.app.config['DB'] = self.db
        self.app.config['TUYA_CLIENT'] = self.client
        self.app.config['ROOT_DIR'] = self.root_dir
        self.app.config['SCHEDULER_UPDATE_FUNC'] = self.update_scheduler
        
        # Register Blueprints
        from .routes.api import api_bp
        from .routes.web import web_bp
        self.app.register_blueprint(api_bp)
        self.app.register_blueprint(web_bp)
        
        # Ensure API Key exists
        settings = self.db.get_settings()
        if 'api_key' not in settings:
            from .security import generate_api_key
            new_key = generate_api_key()
            self.db.update_setting('api_key', new_key)
            logging.info(f"Generated new API Key: {new_key}")
            print(f"--- API SECURITY ENABLED ---")
            print(f"Generated API Key: {new_key}")
            print(f"Please save this key for API access.")
            print(f"-----------------------------")
        
        # Setup Logger
        logging.basicConfig(
            filename=os.path.join(self.root_dir, 'app.log'),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        self.setup_scheduler()

    def setup_scheduler(self):
        self.scheduler.start()
        self.update_scheduler()

    def update_scheduler(self):
        self.scheduler.remove_all_jobs()
        settings = self.db.get_settings()
        refresh = int(settings.get('refresh', 5))
        
        # Core update jobs
        self.scheduler.add_job(
            func=self.client.scan_devices, 
            trigger="interval", 
            hours=1,
            id="scan_devices"
        )
        
        # Dynamic schedules from DB
        schedules = self.db.get_schedules()
        for s in schedules:
            if not s.get('days'): continue
            
            self.scheduler.add_job(
                func=self.execute_schedule_job,
                trigger='cron',
                day_of_week=','.join(s['days']),
                hour=int(s['time'].split(':')[0]),
                minute=int(s['time'].split(':')[1]),
                args=[s['action'], s['devices']],
                id=f"job_{s['id']}"
            )
        logging.info("Scheduler jobs updated.")

    def execute_schedule_job(self, action, device_ids):
        devices = self.db.get_devices()
        for did in device_ids:
            device_data = next((d for d in devices if d['id'] == did), None)
            if device_data:
                if action == 'on':
                    self.client.turn_on(device_data)
                elif action == 'off':
                    self.client.turn_off(device_data)
        logging.info(f"Executed scheduled action '{action}' for {len(device_ids)} devices.")

    def run(self):
        from waitress import serve
        settings = self.db.get_settings()
        port = int(settings.get('port', 8080))
        logging.info(f"Starting server on port {port}")
        serve(self.app, host='0.0.0.0', port=port)
