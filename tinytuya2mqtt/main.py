import configparser
import dataclasses
import json
import logging
import os
import sys
import threading
import time
from typing import List

from paho.mqtt import publish
import paho.mqtt.client as mqtt
import tinytuya


logger = logging.getLogger(__name__)
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.INFO)

if os.environ.get('DEBUG'):
    logger.setLevel(logging.DEBUG)

if os.environ.get('TINYTUYA_DEBUG'):
    tinytuya.set_debug()


MQTT_BROKER = None
MQTT_USERNAME = None
MQTT_PASSWORD = None
TIME_SLEEP = 5


class Device:
    name: str
    id: str
    key: str
    mac: str
    ip: str
    manufacturer: str
    model: str
    hb_interval: int
    hb_time: int
    tuya: tinytuya.OutletDevice = dataclasses.field(default=None)

    def __init__(self, id, config):
        self.id = id
        self.name = config['name']
        self.key = config['key']
        self.mac = config['mac']
        self.ip = config['ip']
        self.hb_interval = 20
        self.hb_time = time.time() + self.hb_interval

    def connect(self):
        self.tuya = tinytuya.OutletDevice(self.id, self.ip, self.key)
        self.tuya.set_version(3.3)
        self.tuya.set_socketPersistent(True)
        self.tuya.set_socketTimeout(TIME_SLEEP)

    def send_heartbeat(self):
        if self.hb_time <= time.time():
            payload = self.tuya.generate_payload(tinytuya.HEART_BEAT)
            logger.debug('Send heartbeat to %s (%s)', self.name, self.id)
            self.tuya.send(payload)
            self.hb_time = time.time() + self.hb_interval

    def poll_status(self):
        return self.tuya.status().get('dps')

    def get_ha_device(self):
        return {
            'identifiers': [self.id, self.mac],
            'name': self.name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'sw_version': f'tinytuya {tinytuya.version}',
        }


class FanDevice(Device):
    fan_state = 1
    fan_speed = 3
    fan_speed_steps = 1,2,3,4,5,6

    def __init__(self, id, config):
        self.manufacturer = "Fanco"
        self.model = "Infinity iD DC"
        super().__init__(id, config)

    def ha_config(self):
        configs = []
        fan = {
            'config': {
                'name': self.name,
                'unique_id': self.id,
                'availability_topic': f'home/{self.id}/online',
                'state_topic': f'home/{self.id}/fan/state',  # fan ON/OFF
                'command_topic': f'home/{self.id}/fan/command',
                'percentage_state_topic': f'home/{self.id}/fan/speed/state',
                'percentage_command_topic': f'home/{self.id}/fan/speed/command',
                'device': self.get_ha_device()
            },
            'topic': f'homeassistant/fan/{self.id}/config'
        }
        configs.append(fan)
        return configs

    def get_topics(self):
        topics = []
        topics.append(f'home/{self.id}/fan/command')
        topics.append(f'home/{self.id}/fan/speed/command')
        return topics

    def speed_to_pct(self, raw: int, max_: int) -> int:
        'Convert a raw value to a percentage'
        return round(raw / max_ * 100)

    def pct_to_speed(self, percentage: int, max_: int) -> int:
        'Convert a percentage to a raw value'
        return round(percentage / 100 * max_)

    def handle_command(self, msg):
        # Fan on/off
        if msg.topic.endswith('/fan/command'):
            dps = self.fan_state
            val = bool(msg.payload == b'ON')

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_status(val, switch=dps)

        # Fan speed
        elif msg.topic.endswith('/fan/speed/command'):
            dps = self.fan_speed
            val = self.pct_to_speed(int(msg.payload), self.fan_speed_steps[-1])

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_value(dps, val)

        return { dps: val }

    def parse_status(self, status):
        msgs = []

        # Publish fan state
        if self.fan_state in status:
            msgs.append((f'home/{self.id}/fan/state', 'ON' if status[self.fan_state] else 'OFF'))

        # Publish fan speed
        if self.fan_speed in status:
            state = self.speed_to_pct(status[self.fan_speed], self.fan_speed_steps[-1])
            msgs.append((f'home/{self.id}/fan/speed/state', state))

        return msgs


class FanWithLightDevice(FanDevice):
    light_state = 15
    light_brightness = 16
    light_brightness_steps = 25,125,275,425,575,725,900,1000

    def __init__(self, id, config):
        super().__init__(id, config)

    def ha_config(self):
        configs = super().ha_config()
        light = {
           'config': {
                'name': f'{self.name} Light',
                'unique_id': self.id,#f'{self.id}_light',
                'availability_topic': f'home/{self.id}/online',
                'state_topic': f'home/{self.id}/light/state',  # light ON/OFF
                'command_topic': f'home/{self.id}/light/command',
                'brightness_scale': 100,
                'brightness_state_topic': f'home/{self.id}/light/brightness/state',
                'brightness_command_topic': f'home/{self.id}/light/brightness/command',
                'device': self.get_ha_device()
            },
            'topic': f'homeassistant/light/{self.id}/config'
        }
        configs.append(light)
        return configs

    def get_topics(self):
        topics = super().get_topics()
        topics.append(f'home/{self.id}/light/command')
        topics.append(f'home/{self.id}/light/brightness/command')
        return topics

    def handle_command(self, msg):
        # Light on/off
        if msg.topic.endswith('/light/command'):
            dps = self.light_state
            val = bool(msg.payload == b'ON')

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_status(val, switch=dps)

        # Light brightness
        elif msg.topic.endswith('/light/brightness/command'):
            dps = self.light_brightness
            val = self.pct_to_speed(int(msg.payload), self.light_brightness_steps[-1])

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_value(dps, val)
        else:
            return super().handle_command(msg)

        return { dps: val }

    def parse_status(self, status):
        msgs = super().parse_status(status)

        # Publish light state
        if self.light_state in status:
            msgs.append((f'home/{self.id}/light/state', 'ON' if status[self.light_state] else 'OFF'))

        # Publish light brightness
        if self.light_brightness in status:
            state = self.speed_to_pct(status[self.light_brightness], self.light_brightness_steps[-1])
            msgs.append((f'home/{self.id}/light/brightness/state', state))

        return msgs


class ClimateDevice(Device):
    climate_state = 1
    set_temperature = 2
    current_temperature = 3
    action = 5

    def __init__(self, id, config):
        self.manufacturer = "Beok"
        self.model = "Thermostat"
        super().__init__(id, config)

    def ha_config(self):
        climate = {
            'config': {
                'name': self.name,
                'unique_id': self.id,
                'availability_topic': f'home/{self.id}/online',
                'mode_state_topic': f'home/{self.id}/climate/mode/state',
                'mode_command_topic': f'home/{self.id}/climate/mode/command',
                'action_topic': f'home/{self.id}/climate/action',
                'current_temperature_topic': f'home/{self.id}/climate/current_temperature',
                'temperature_state_topic': f'home/{self.id}/climate/temperature/state',
                'temperature_command_topic': f'home/{self.id}/climate/temperature/command',
                'temp_step': 0.1,
                'modes': ['off','heat'],
                'device': self.get_ha_device()
            },
            'topic': f'homeassistant/climate/{self.id}/config'
        }
        return [ climate ]

    def get_topics(self):
        topics = []
        topics.append(f'home/{self.id}/climate/temperature/command')
        topics.append(f'home/{self.id}/climate/mode/command')
        return topics

    def handle_msg(self, msg):
        # Climate temp
        if msg.topic.endswith('/climate/temperature/command'):
            dps = self.set_temperature
            val = int(float(msg.payload)*10)

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_value(dps, val)

        # Climate mode
        elif msg.topic.endswith('/climate/mode/command'):
            dps = self.climate_state
            val = bool(msg.payload == b'heat')

            logger.debug('Setting %s to %s', dps, val)
            self.tuya.set_value(dps, val)

        return { dps: val }

    def parse_status(self, status):
        msgs = []
        if self.climate_state in status:
            msgs.append((f'home/{self.id}/climate/mode/state', 'heat' if status[self.climate_state] else 'off'))
        if self.action in status:
            msgs.append((f'home/{self.id}/climate/action', 'heating' if int(status[self.action]) else 'off'))
        if self.current_temperature in status:
            msgs.append((f'home/{self.id}/climate/current_temperature', status[self.current_temperature]/10))
        if self.set_temperature in status:
            msgs.append((f'home/{self.id}/climate/temperature/state', status[self.set_temperature]/10))

        return msgs


def autoconfigure_ha(device: Device):
    '''
    Send discovery messages to auto configure the device in HA

    Params:
        device:  An instance of Device
    '''

    for config in device.ha_config():
        publish.single(config['topic'], json.dumps(config['config']), hostname=MQTT_BROKER, retain=True, auth={'username':MQTT_USERNAME, 'password':MQTT_PASSWORD})

    logger.info('Autodiscovery topic published for %s at %s', device.name, device.id)


def read_config() -> List[Device]:
    '''
    Read & parse tinytuya2mqtt.ini
    '''
    # Validate files are present
    tinytuya2mqtt_conf_path = None

    for fn in ('tinytuya2mqtt.ini', '/tinytuya2mqtt.ini'):
        if os.path.exists(fn):
            tinytuya2mqtt_conf_path = fn
            break

    if tinytuya2mqtt_conf_path is None:
        logger.error('Missing tinytuya2mqtt.ini')
        sys.exit(2)

    devices = {}

    # Read tinytuya2mqtt.ini
    cfg = configparser.ConfigParser(inline_comment_prefixes='#')

    with open(tinytuya2mqtt_conf_path, encoding='utf8') as f:
        cfg.read_string(f.read())

    try:
        # Map the device pin configurations into the Device class
        for section in cfg.sections():
            parts = section.split(' ')

            if parts[0] == 'device':
                device_id = parts[1]
                type = dict(cfg.items(section))['type']
                if type == 'climate':
                    devices[device_id] = ClimateDevice(device_id, dict(cfg.items(section)))
                if type == 'fan':
                    devices[device_id] = FanDevice(device_id, dict(cfg.items(section)))
                if type == 'fanwlight':
                    devices[device_id] = FanWithLightDevice(device_id, dict(cfg.items(section)))

            elif parts[0] == 'broker':
                global MQTT_BROKER,MQTT_USERNAME,MQTT_PASSWORD  # pylint: disable=global-statement
                MQTT_BROKER = dict(cfg.items(section))['hostname']
                MQTT_USERNAME = dict(cfg.items(section))['username']
                MQTT_PASSWORD = dict(cfg.items(section))['password']

    except KeyError:
        logger.error('Malformed broker section in tinytuya2mqtt.ini')
        sys.exit(3)
    except IndexError:
        logger.error('Malformed section name in tinytuya2mqtt.ini')
        sys.exit(3)

    return devices.values()


def main():
    '''
    Read config and start the app
    '''
    for device in read_config():
        autoconfigure_ha(device)

        # Starting polling this device on a thread
        t = threading.Thread(target=poll, args=(device,))
        t.start()


def on_connect(client, userdata, _1, _2):
    '''
    On broker connected, subscribe to the command topics
    '''
    for command_topic in userdata['device'].get_topics():
        client.subscribe(command_topic, 0)
        logger.info('Subscribed to %s', command_topic)


def on_message(_, userdata: dict, msg: bytes):
    '''
    On command message received, take some action

    Params:
        client:    paho.mqtt.client
        userdata:  Arbitrary data passed on this Paho event loop
        msg:       Message received on MQTT topic sub
    '''
    logger.debug('Received %s on %s', msg.payload, msg.topic)
    if not msg.payload:
        return

    device: Device = userdata['device']

    status = device.handle_msg(msg)
    # Immediately publish status back to HA
    read_and_publish_status(userdata['device'], status)


def poll(device: Device):
    '''
    Start MQTT threads, and then poll a device for status updates.

    Params:
        device:  An instance of Device
    '''
    logger.debug('Connecting to %s', device.ip)

    device.connect()

    # Connect to the broker and hookup the MQTT message event handler
    client = mqtt.Client(device.id, userdata={'device': device})
    client.on_connect = on_connect
    client.on_message = on_message
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.connect(MQTT_BROKER)
    client.loop_start()

    read_and_publish_status(device, device.poll_status())

    try:
        while True:
            device.send_heartbeat()
            data = device.tuya.receive()
            if data:
                read_and_publish_status(device, data.get('dps'))
    finally:
        client.loop_stop()
        logger.info('fin')


def read_and_publish_status(device: Device, status: dict):
    '''
    Fetch device current status and publish on MQTT

    Params:
        device:  An instance of Device
    '''
    logger.debug('STATUS:  %s', status)
    if not status:
        logger.error('Failed getting device status %s', device.id)
        return

    # Make all keys integers, for convenience compat with Device.dps integers
    status = {int(k):v for k,v in status.items()}

    msgs = [
        (f'home/{device.id}/online', 'online')
    ]

    for msg in device.parse_status(status):
        msgs.append(msg)

    logger.debug('PUBLISH: %s', msgs)
    publish.multiple(msgs, hostname=MQTT_BROKER, auth={'username':MQTT_USERNAME, 'password':MQTT_PASSWORD})
