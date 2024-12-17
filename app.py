from flask import Flask
from flask_restful import Resource, Api
import tinytuya

app = Flask(__name__)
api = Api(app)

devices = {
    1:{'name':'YDExt001',
       "id": "ebb06a927c1e101691y87x",
        "key": ")oiWK.=H+US)n>H5"},
    2:{'name':'Write blog'},
    3:{'name':'Start stream'},
}
class Items(Resource):
    def get(self):
        return devices
    
class On(Resource):
    def get(self, pk):
        print(devices[pk]["name"])
        #switch = tinytuya.OutletDevice(dev_id=devices[pk]["id"], address="auto",local_key=devices[pk]["key"],version=3.3)
        #switch.turn_on()
        #print(switch.status()['mapping']['1']["values"])
        #print("Switch Turned off")
        return f"{devices[pk]["name"]} Switch Turned On"

class Off(Resource):
    def get(self, pk):
        print(devices[pk]["name"])
        #switch = tinytuya.OutletDevice(dev_id=devices[pk]["id"], address="auto",local_key=devices[pk]["key"],version=3.3)
        #switch.turn_off()
        #print(switch.status()['mapping']['1']["values"])
        #print("Switch Turned off")
        return f"{devices[pk]["name"]} Switch Turned Off"

api.add_resource(Items, '/')
api.add_resource(On, '/on/<int:pk>')
api.add_resource(Off, '/off/<int:pk>')

@app.route('/')
def hello():
    return '<h1>Hello, World!</h1>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)