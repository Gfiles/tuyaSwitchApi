from flask import Blueprint, render_template, request, redirect, current_app, url_for
import logging
from uuid import uuid4

web_bp = Blueprint('web', __name__)

@web_bp.route("/")
def index():
    db = current_app.config['DB']
    client = current_app.config['HA_CLIENT']
    
    devices = db.get_devices()
    # Update status for each device (could be slow, consider caching)
    for device in devices:
        status = client.update_device_status(device)
        device['state'] = status['state']
        device['voltage'] = status['voltage']
        device['power'] = status['power']
        device['current'] = status.get('current', 0)
        device['has_energy'] = status.get('has_energy', False)
        
    title = db.get_settings().get('title', 'Tuya App')
    min_width = db.get_settings().get('minButtonWidth', 300)
    
    grouped = {}
    for dev in devices:
        area = dev.get('area') or 'Ungrouped'
        if area not in grouped:
            grouped[area] = []
        grouped[area].append(dev)
    
    return render_template("index.html", grouped_switches=grouped, title=title, minButtonWidth=min_width)

@web_bp.route("/toggle/<pk>")
def toggle(pk):
    db = current_app.config['DB']
    client = current_app.config['HA_CLIENT']
    
    devices = db.get_devices()
    device_data = next((d for d in devices if d['id'] == pk), None)
    
    if device_data:
        client.toggle(device_data)
        
    return redirect(url_for('web.index'))

@web_bp.route("/all/<action>")
def toggle_all(action):
    db = current_app.config['DB']
    client = current_app.config['HA_CLIENT']
    
    if action not in ['on', 'off']:
        return redirect(url_for('web.index'))
        
    devices = db.get_devices()
    excluded = db.get_excluded_devices()
    
    for device in devices:
        if device['id'] not in excluded:
            if action == 'on':
                client.turn_on(device)
            elif action == 'off':
                client.turn_off(device)
                
    return redirect(url_for('web.index'))

@web_bp.route("/settings", methods=["GET", "POST"])
def settings():
    db = current_app.config['DB']
    if request.method == "POST":
        # Update settings
        for key in ['title', 'refresh', 'port', 'minButtonWidth', 'ha_url', 'ha_token']:
            if key in request.form:
                db.update_setting(key, request.form[key])
        
        # Update devices
        devices = db.get_devices()
        for i, device in enumerate(devices):
            sol_key = f"device_solution_{i}"
            if sol_key in request.form:
                db.update_device_solution(device['id'], request.form[sol_key])
        
        # Excluded devices
        excluded_ids = request.form.getlist("exclude_from_all")
        db.update_excluded_devices(excluded_ids)
        
        return redirect(url_for('web.index'))
        
    config = db.get_settings()
    devices = db.get_devices()
    excluded = db.get_excluded_devices()
    config['exclude_from_all'] = excluded
    config.setdefault('ha_url', 'http://homeassistant.local:8123')
    config.setdefault('ha_token', '')
    
    return render_template("settings.html", config=config, devices=devices, title="Settings")

@web_bp.route("/schedule", methods=["GET", "POST"])
def schedule():
    db = current_app.config['DB']
    if request.method == "POST":
        schedules = []
        ids = request.form.getlist("schedule_id")
        names = request.form.getlist("schedule_name")
        actions = request.form.getlist("schedule_action")
        times = request.form.getlist("schedule_time")
        
        for i in range(len(ids)):
            s_id = ids[i] or str(uuid4())
            days = request.form.getlist(f"schedule_days_{i}")
            dev_list = request.form.getlist(f"schedule_devices_{i}")
            schedules.append({
                "id": s_id,
                "name": names[i],
                "action": actions[i],
                "days": days,
                "time": times[i],
                "devices": dev_list
            })
        db.save_schedules(schedules)
        # Sceduler update logic should be in a separate service/manager
        current_app.config['SCHEDULER_UPDATE_FUNC']()
        return redirect(url_for('web.index'))
        
    schedules = db.get_schedules()
    devices = db.get_devices()
    return render_template("schedule.html", schedules=schedules, devices=devices, title="Schedule Configuration")

@web_bp.route("/delete_device/<pk>")
def delete_device(pk):
    db = current_app.config['DB']
    db.delete_device(pk)
    return redirect(url_for('web.settings'))
