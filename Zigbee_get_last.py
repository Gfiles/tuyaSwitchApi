import paho.mqtt.client as mqttc
import paho.mqtt.enums as version

# Publisher example
def publish_retained_message(broker_address, topic, payload):
    client = mqtt.Client()
    client.connect(broker_address, 1883, 60)
    # Publish with retain=True
    client.publish(topic, payload, qos=1, retain=True)
    client.disconnect()
    print(f"Published retained message '{payload}' to topic '{topic}'")

# Subscriber example
def subscribe_and_get_last_state(broker_address, topic):
    def on_connect(client, userdata, flags, rc, properties):
        print(f"Connected with result code {rc}")
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        print(f"Received message: Topic='{msg.topic}', Payload='{msg.payload.decode()}', Retained={msg.retain}")

    client = mqttc.Client(version.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker_address)
    client.loop_forever()

# Example usage
# publish_retained_message("localhost", "sensor/temperature", "25.5C")
subscribe_and_get_last_state("localhost", "zigbee2mqtt")
