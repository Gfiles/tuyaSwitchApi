import secrets
import functools
from flask import request, current_app, jsonify

def generate_api_key():
    return secrets.token_urlsafe(32)

def require_api_key(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        db = current_app.config['DB']
        settings = db.get_settings()
        stored_key = settings.get('api_key')
        
        # If no key is set, we assume security is disabled (or should be configured)
        if not stored_key:
            return f(*args, **kwargs)
            
        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if provided_key != stored_key:
            return jsonify({"error": "Unauthorized. Invalid or missing API Key"}), 401
            
        return f(*args, **kwargs)
    return decorated_function
