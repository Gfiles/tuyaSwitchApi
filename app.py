import os
from tuya_server.server import TuyaServer

if __name__ == "__main__":
    # Get the directory where app.py is located
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    server = TuyaServer(root_dir)
    server.setup()
    server.run()
