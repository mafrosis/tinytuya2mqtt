import configparser
import dataclasses
import json
import logging
import os
import sys
import threading
import time
from typing import cast, List, Optional, Tuple, Union

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


MQTT_BROKER = 'localhost'
TIME_SLEEP = 5


@dataclasses.dataclass
class Device:
    name: str
    id: str
    key: str
    mac: str
    ip: str
    tuya: tinytuya.OutletDevice
    entities: List['Entity'] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class Entity:
    state_pin: str
    device: Device

@dataclasses.dataclass
class Fan(Entity):
    speed_pin: str
    speed_steps: List[int]

@dataclasses.dataclass
class Light(Entity):
    brightness_pin: str
    brightness_steps: List[int]
    temp_pin: str



def autoconfigure_fan(device: Device):
    '''
    Send MQTT discovery messages for a fan entity

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

    logger.info('Autodiscovery topic published for %s on %s', device.name, device.id)


def autoconfigure_light(device: Device):
    '''
    Send MQTT discovery messages for a light entity

    Params:
        device:  An instance of Device dataclass
    '''
    device_name = f'{device.name} Light'

    data = {
        'name': device_name,
        'unique_id': device.id,
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

    logger.info('Autodiscovery topic published for %s on %s', device_name, device.id)


def autoconfigure_device_entities(device: Device):
    '''
    Send MQTT discovery messages to autoconfigure devices in HA

    Params:
        device:  An instance of Device dataclass
    '''
    for entity in device.entities:
        if isinstance(entity, Fan):
            autoconfigure_fan(device)
        elif isinstance(entity, Light):
            autoconfigure_light(device)


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

    def _create_tinytuya(id_, ip, key):
        t = tinytuya.OutletDevice(id_, ip, key)
        t.set_version(3.3)
        t.set_socketPersistent(True)
        return t

    # Create a dict of Device objects from snapshot.json
    devices = {
        d['id']: Device(
            d['name'], d['id'], d['key'], d['mac'], d['ip'],
            _create_tinytuya(d['id'], d['ip'], d['key'])
        )
        for d in snapshot['devices']
    }

    # Read tinytuya2mqtt.ini
    cfg = configparser.ConfigParser(inline_comment_prefixes='#')

    with open(tinytuya2mqtt_conf_path, encoding='utf8') as f:
        cfg.read_string(f.read())

    try:
        # Map the device entity configurations into the Device class
        for section in cfg.sections():
            parts = section.split(' ')

            if parts[0] == 'device':
                device_id = parts[1]

                if not devices[device_id].entities:
                    devices[device_id].entities = []

                try:
                    entity: Entity

                    # Inflate INI section into Entity dataclasses
                    entities = dict(cfg.items(section))

                    if 'fan_state_pin' in entities:
                        entity = Fan(
                            state_pin=entities['fan_state_pin'],
                            speed_pin=entities['fan_speed_pin'],
                            speed_steps=[int(i) for i in entities['fan_speed_steps'].split(',')],
                            device=devices[device_id],
                        )
                        devices[device_id].entities.append(entity)

                    if 'light_state_pin' in entities:
                        entity = Light(
                            state_pin=entities['light_state_pin'],
                            brightness_pin=entities['light_brightness_pin'],
                            brightness_steps=[int(i) for i in entities['light_brightness_steps'].split(',')],
                            temp_pin=entities['light_temp_pin'],
                            device=devices[device_id],
                        )
                        devices[device_id].entities.append(entity)

                except TypeError as e:
                    val = str(e).rsplit(' ', maxsplit=1)[-1]
                    logger.error('Invalid pin name in tinytuya2mqtt.ini: %s', val)
                    sys.exit(3)

            elif parts[0] == 'broker':
                global MQTT_BROKER  # pylint: disable=global-statement
                MQTT_BROKER = dict(cfg.items(section))['hostname']

    except KeyError:
        logger.error('Malformed broker section in tinytuya2mqtt.ini')
        sys.exit(3)
    except IndexError:
        logger.error('Malformed section name in tinytuya2mqtt.ini')
        sys.exit(3)

    return list(devices.values())


def main():
    '''
    Read config and start the app
    '''
    for device in read_config():
        autoconfigure_device_entities(device)

        # Starting polling this device on a thread
        t = threading.Thread(target=poll, args=(device,))
        t.start()


def on_connect(client, userdata, flags, rc):  # pylint: disable=unused-argument
    '''
    On broker connected, subscribe to the command topics
    '''
    command_topics = []

    for cmd in ('fan', 'fan/speed', 'light', 'light/brightness'):
        command_topic = f"home/{userdata['device'].id}/{cmd}/command"
        command_topics.append((command_topic, 0))

    ret = client.subscribe(command_topics, 0)
    logger.info('Subscribing to %s: %s', command_topics, ret)


def on_disconnect(client, userdata, rc):  # pylint: disable=unused-argument
    'Debug logging of disconnects'
    logger.debug('Disconnect: %s', rc)


def on_log(client, userdata, level, buf):  # pylint: disable=unused-argument
    'Debug logging of MQTT messages from the Paho client'
    logger.debug(buf)


def on_message(_, userdata: dict, msg: mqtt.MQTTMessage):
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

    if msg.topic.startswith(f'home/{device.id}/fan'):
        fan = cast(Fan, next((e for e in device.entities if isinstance(e, Fan)), None))

        # Fan on/off
        if msg.topic.endswith('/command'):
            _set_status(device, fan.state_pin, bool(msg.payload == b'ON'))

        # Fan speed
        elif msg.topic.endswith('/speed/command'):
            val = pct_to_speed(int(msg.payload), fan.speed_steps[-1])
            _set_value(device, fan.speed_pin, val)


    elif msg.topic.startswith(f'home/{device.id}/light'):
        light = cast(Light, next((e for e in device.entities if isinstance(e, Light)), None))

        # Light on/off
        if msg.topic.endswith('/command'):
            _set_status(device, light.state_pin, bool(msg.payload == b'ON'))

        # Light brightness
        elif msg.topic.endswith('/brightness/command'):
            val = pct_to_speed(int(msg.payload), light.brightness_steps[-1])
            _set_value(device, light.brightness_pin, val)

    else:
        logger.error('Unrecognized command: %s', msg.topic)
        return

    # Immediately publish status
    read_and_publish_status(userdata['device'])


def _set_status(device: Device, pin: str, val: bool):
    'Set a tinytuya boolean status'
    logger.debug('Setting %s to %s on %s', pin, val, device.id)
    device.tuya.set_status(val, switch=int(pin))


def _set_value(device: Device, pin: str, val: int):
    'Set a tinytuya integer value'
    logger.debug('Setting %s to %s on %s', pin, val, device.id)
    device.tuya.set_value(pin, val)


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
    client.on_disconnect = on_disconnect
    client.on_log = on_log
    client.connect(MQTT_BROKER)
    client.loop_start()

    try:
        while True:
            read_and_publish_status(device)

            time.sleep(TIME_SLEEP)
    finally:
        client.loop_stop()
        logger.info('fin')


def build_fan_msgs(status: dict, fan: Fan) -> List[Tuple[str, str, int, bool]]:
    '''
    Return the state of the fan as MQTT messages

    Params:
        status:  Status dict returned from tinytuya
        fan:  The fan fan
    '''
    if fan.state_pin not in status:
        logger.error('Fan.state_pin %s absent in status: %s', fan.state_pin, status)
        return []

    msgs = [(
        f'home/{fan.device.id}/fan/state', 'ON' if status[fan.state_pin] else 'OFF', 0, False,
    )]

    if fan.speed_pin in status:
        msgs.append((
            f'home/{fan.device.id}/fan/speed/state',
            str(speed_to_pct(status[fan.speed_pin], fan.speed_steps[-1])), 0, False,
        ))
    return msgs


def build_light_msgs(status: dict, light: Light) -> List[Tuple[str, str, int, bool]]:
    '''
    Return the state of the light as MQTT messages

    Params:
        status:  Status dict returned from tinytuya
        light:  The light light
    '''
    if light.state_pin not in status:
        logger.error('Light.state_pin %s absent in status: %s', light.state_pin, status)
        return []

    msgs = [(
        f'home/{light.device.id}/light/state', 'ON' if status[light.state_pin] else 'OFF', 0, False,
    )]

    if light.brightness_pin in status:
        msgs.append((
            f'home/{light.device.id}/light/brightness/state',
            str(speed_to_pct(status[light.brightness_pin], light.brightness_steps[-1])), 0, False,
        ))
    return msgs


def read_and_publish_status(device: Device):
    '''
    Fetch device current status and publish on MQTT

    Params:
        device:  An instance of Device dataclass
    '''
    try:
        status = device.tuya.status().get('dps')
    except AttributeError:
        return

    logger.debug('RAW:     %s', status)
    logger.debug('STATUS:  %s', _get_friendly_status(device, status))

    if not status:
        logger.error('Failed getting device status %s', device.id)
        return

    msgs = [(f'home/{device.id}/online', 'online', 0, False)]

    for entity in device.entities:
        if isinstance(entity, Fan):
            entity_msgs = build_fan_msgs(status, entity)
        elif isinstance(entity, Light):
            entity_msgs = build_light_msgs(status, entity)

        msgs += entity_msgs

    logger.debug('PUBLISH: %s', msgs)
    publish.multiple(msgs, hostname=MQTT_BROKER)


def speed_to_pct(raw: int, max_: int) -> int:
    'Convert a raw value to a percentage'
    return round(raw / max_ * 100)


def pct_to_speed(percentage: int, max_: int) -> int:
    'Convert a percentage to a raw value'
    return round(percentage / 100 * max_)


def _get_friendly_status(device: Device, status: dict) -> dict:
    'Return a friendly device status mapped to the user configuration'
    output = {}

    if not status:
        logger.error('Empty status returned from device %s!', device.name)
        return {}

    def _get_state(pin):
        state = status.get(pin)
        if state is None:
            logger.error('Failed getting state on pin %s', pin)
            return None
        return state

    for entity in device.entities:
        # Return entity.state_pin status
        state = _get_state(entity.state_pin)
        if state is None:
            continue

        output[f'{type(entity).__name__.lower()}_state'] = state

        # Return entity type-specific pin statuses
        if isinstance(entity, Fan):
            state = _get_state(entity.speed_pin)
            if state is None:
                continue
            output['fan_speed_pin'] = status[entity.speed_pin]

        elif isinstance(entity, Light):
            state = _get_state(entity.brightness_pin)
            if state is None:
                continue
            output['light_brightness_pin'] = status[entity.brightness_pin]

    return output
