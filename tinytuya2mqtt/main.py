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
TIME_SLEEP = 5


@dataclasses.dataclass
class Device:
    name: str
    id: str
    key: str
    mac: str
    ip: str
    dps: dict = dataclasses.field(default=None)
    tuya: tinytuya.OutletDevice = dataclasses.field(default=None)


def autoconfigure_ha_fan(device: Device):
    '''
    Send discovery messages to auto configure the fans in HA

    Params:
        device:  An instance of Device dataclass
    '''
    data = {
        'name': device.name,
        'unique_id': device.id,
        'availability_topic': f'home/{device.id}/online',
        'state_topic': f'home/{device.id}/fan/state',  # fan ON/OFF
        'command_topic': f'home/{device.id}/fan/command',
        'percentage_state_topic': f'home/{device.id}/fan/speed/state',
        'percentage_command_topic': f'home/{device.id}/fan/speed/command',
        'device': {
            'identifiers': [device.id, device.mac],
            'name': device.name,
            'manufacturer': 'Fanco',
            'model': 'Infinity iD DC',
            'sw_version': f'tinytuya {tinytuya.version}',
        }
    }
    publish.single(
        f'homeassistant/fan/{device.id}/config', json.dumps(data), hostname=MQTT_BROKER, retain=True,
    )

    # Publish fan light discovery topic, if the fan has a light
    if device.dps.get('light_state'):
        data = {
            'name': f'{device.name} Light',
            'unique_id': device.id,#f'{device.id}_light',
            'availability_topic': f'home/{device.id}/online',
            'state_topic': f'home/{device.id}/light/state',  # light ON/OFF
            'command_topic': f'home/{device.id}/light/command',
            'brightness_scale': 100,
            'brightness_state_topic': f'home/{device.id}/light/brightness/state',
            'brightness_command_topic': f'home/{device.id}/light/brightness/command',
            'device': {
                'identifiers': [device.id, device.mac],
                'name': device.name,
                'manufacturer': 'Fanco',
                'model': 'Infinity iD DC',
                'sw_version': f'tinytuya {tinytuya.version}',
            }
        }
        publish.single(
            f'homeassistant/light/{device.id}/config', json.dumps(data), hostname=MQTT_BROKER, retain=True,
        )

    logger.info('Autodiscovery topic published for %s at %s', device.name, device.id)


def read_config() -> List[Device]:
    '''
    Read & parse tinytuya2mqtt.ini and snapshot.json
    '''
    # Validate files are present
    snapshot_conf_path = tinytuya2mqtt_conf_path = None

    for fn in ('snapshot.json', '/snapshot.json'):
        if os.path.exists(fn):
            snapshot_conf_path = fn
            break

    if snapshot_conf_path is None:
        logger.error('Missing snapshot.json')
        sys.exit(2)

    for fn in ('tinytuya2mqtt.ini', '/tinytuya2mqtt.ini'):
        if os.path.exists(fn):
            tinytuya2mqtt_conf_path = fn
            break

    if tinytuya2mqtt_conf_path is None:
        logger.error('Missing tinytuya2mqtt.ini')
        sys.exit(2)

    try:
        # Read snapshop.json
        with open(snapshot_conf_path, encoding='utf8') as f:
            snapshot = json.load(f)
    except json.decoder.JSONDecodeError:
        logger.error('Invalid snapshot.json!')
        sys.exit(3)

    # Create a dict of Device objects from snapshot.json
    devices = {
        d['id']: Device(d['name'], d['id'], d['key'], d['mac'], d['ip'])
        for d in snapshot['devices']
    }

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
                devices[device_id].dps = dict(cfg.items(section))

            elif parts[0] == 'broker':
                global MQTT_BROKER  # pylint: disable=global-statement
                MQTT_BROKER = dict(cfg.items(section))['hostname']

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
        autoconfigure_ha_fan(device)

        # Starting polling this device on a thread
        t = threading.Thread(target=poll, args=(device,))
        t.start()


def on_connect(client, userdata, _1, _2):
    '''
    On broker connected, subscribe to the command topics
    '''
    for cmd in ('fan', 'fan/speed', 'light', 'light/brightness'):
        command_topic = f"home/{userdata['device'].id}/{cmd}/command"
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

    # Fan on/off
    if msg.topic.endswith('/fan/command'):
        dps = device.dps['fan_state']
        val = bool(msg.payload == b'ON')

        logger.debug('Setting %s to %s', dps, val)
        device.tuya.set_status(val, switch=dps)

    # Fan speed
    elif msg.topic.endswith('/fan/speed/command'):
        dps = device.dps['fan_speed']
        val = pct_to_speed(int(msg.payload), device.dps['fan_speed_steps'][-1])

        logger.debug('Setting %s to %s', dps, val)
        device.tuya.set_value(dps, val)

    # Light on/off
    elif msg.topic.endswith('/light/command'):
        dps = device.dps['light_state']
        val = bool(msg.payload == b'ON')

        logger.debug('Setting %s to %s', dps, val)
        device.tuya.set_status(val, switch=dps)

    # Light brightness
    elif msg.topic.endswith('/light/brightness/command'):
        dps = device.dps['light_brightness']
        val = pct_to_speed(int(msg.payload), device.dps['light_brightness_steps'][-1])

        logger.debug('Setting %s to %s', dps, val)
        device.tuya.set_value(dps, val)

    # Immediately publish status back to HA
    read_and_publish_status(userdata['device'])


def poll(device: Device):
    '''
    Start MQTT threads, and then poll a device for status updates.

    Params:
        device:  An instance of Device dataclass
    '''
    logger.debug('Connecting to %s', device.ip)

    device.tuya = tinytuya.OutletDevice(device.id, device.ip, device.key)
    device.tuya.set_version(3.3)
    device.tuya.set_socketPersistent(True)

    # Connect to the broker and hookup the MQTT message event handler
    client = mqtt.Client(device.id, userdata={'device': device})
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER)
    client.loop_start()

    try:
        while True:
            read_and_publish_status(device)

            time.sleep(TIME_SLEEP)
    finally:
        client.loop_stop()
        logger.info('fin')


def read_and_publish_status(device: Device):
    '''
    Fetch device current status and publish on MQTT

    Params:
        device:  An instance of Device dataclass
    '''
    status = device.tuya.status().get('dps')
    logger.debug('STATUS:  %s', status)
    if not status:
        logger.error('Failed getting device status %s', device.id)
        return

    # Make all keys integers, for convenience compat with Device.dps integers
    status = {int(k):v for k,v in status.items()}

    msgs = [
        (f'home/{device.id}/online', 'online')
    ]

    # Publish fan state
    if device.dps.get('fan_state') in status:
        msgs.append(
            (f'home/{device.id}/fan/state', 'ON' if status[device.dps['fan_state']] else 'OFF')
        )

    # Publish light state
    if device.dps.get('light_state') in status:
        msgs.append(
            (f'home/{device.id}/light/state', 'ON' if status[device.dps['light_state']] else 'OFF')
        )

    # Publish fan speed
    if device.dps.get('fan_speed') in status:
        msgs.append(
            (
                f'home/{device.id}/fan/speed/state',
                speed_to_pct(
                    status[device.dps['fan_speed']],
                    device.dps['fan_speed_steps'][-1],
                ),
            )
        )

    # Publish light brightness
    if device.dps.get('light_brightness') in status:
        msgs.append(
            (
                f'home/{device.id}/light/brightness/state',
                speed_to_pct(
                    status[device.dps['light_brightness']],
                    device.dps['light_brightness_steps'][-1],
                ),
            )
        )

    logger.debug('PUBLISH: %s', msgs)
    publish.multiple(msgs, hostname=MQTT_BROKER)


def speed_to_pct(raw: int, max_: int) -> int:
    'Convert a raw value to a percentage'
    return round(raw / max_ * 100)


def pct_to_speed(percentage: int, max_: int) -> int:
    'Convert a percentage to a raw value'
    return round(percentage / 100 * max_)
