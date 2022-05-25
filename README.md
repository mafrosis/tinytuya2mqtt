tinytuya2mqtt
==========

A bridge between [jasonacox/tinytuya](https://github.com/jasonacox/tinytuya) and Home Assistant via
MQTT.

Leveraging Home Assistant's autodiscovery means there is no configuration required on the HA side.
Once this is setup, your devices will just appear, and will be controllable from HA.

```
┌───────────┐      ┌──────┐      ┌───────────────┐
│ Home      │      │ MQTT │      │ tinytuya2mqtt │
│ Assistant │◀────▶│      │◀────▶│               │
└───────────┘      └──────┘      └──┬────────┬───┘
                                   ┌┘        └──┐
                                   ▼            ▼
                               ┌───────┐    ┌───────┐
                               │ Tuya  │    │ Tuya  │
                               │ Fan   │    │ Light │
                               └───────┘    └───────┘
```

Running
----------

Ensure `tinytuya2mqtt.ini` and `snapshot.json` are in the current directory. Ensure your broker IP
has been set in `docker-compose.yml`:

```
docker compose up
```

Or, without `docker`:
```
tinytuya2mqtt
```

Setup
----------

```
docker compose build
```

Or, without `docker`:
```
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

Config
----------

Two things are required:

 1. `snapshot.json`
 2. `tinytuya2mqtt.ini`

#### snapshot.json

Follow the setup process for
[tinytuya](https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys) using the
`wizard` which is part of that project. This will create a file `snapshot.json` which is used by
`tinytuya2mqtt`.

```
python -m tinytuya wizard
```

#### tinytuya2mqtt.ini

Create a `tinytuya2mqtt.ini` config file, mapping your device pins to the named capabilities. Also
ensure to include your MQTT broker hostname. For example:

```ini
[broker]
hostname = 192.168.1.198

[device bf7bf4939779bbd9afllck]
fan_state_pin = 1
fan_speed_pin = 3
fan_speed_steps = 1,2,3,4,5,6
light_state_pin = 15
light_brightness_pin = 16
light_brightness_steps = 25,125,275,425,575,725,900,1000
light_temp_pin = 17

[device bf66790922f582082fao6p]
fan_state = 1
fan_speed = 3
fan_speed_steps = 1,2,3,4,5,6
```

Devices
----------

Device types and capabilities supported by `tinytuya2mqtt`:

|Type|Subtype|Name|Example|
|---|---|---|---|
|Fan|Fan|`fan_state_pin`|`1`|
|Fan|Fan|`fan_speed_pin`|`3`|
|Fan|Fan|`fan_speed_steps`|`1,2,3,4,5,6`|
|Fan|Light|`light_state_pin`|`15`|
|Fan|Light|`light_brightness_pin`|`16`|
|Fan|Light|`light_brightness_steps`|`25,125,275,425,575,725,900,1000`|
|Fan|Light|`light_temp_pin`|`17`|
