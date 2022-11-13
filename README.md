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

Config file is required:

 1. `tinytuya2mqtt.ini`

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
username = user
password = password

[device bf7bf4939779bbd9afllck]
type = fan
name = Fan
ip = 192.168.1.10
key = xxxxxxxxxxxxxxx
mac = 00:11:22:33:44:55

[device bf66790922f582082fao6p]
type = fanwlight
name = "Fan with light"
ip = 192.168.1.11
key = xxxxxxxxxxxxxxx
mac = 00:11:22:33:44:55

[device bf66790922f582082fef61]
type = climate
name = Thermostat
ip = 192.168.1.12
key = xxxxxxxxxxxxxxx
mac = 00:11:22:33:44:55
```
