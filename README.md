tinytuya2mqtt
==========

A bridge between [jasonacox/tinytuya](https://github.com/jasonacox/tinytuya) and Home Assistant via
MQTT.


Install
----------

```
python3 -m venv venv && source venv/bin/activate
pip install .
```

Config
----------

Follow the setup process for
[tinytuya](https://github.com/jasonacox/tinytuya#setup-wizard---getting-local-keys) using the
`wizard` which is part of that project. This will create a file `snapshot.json` which is used by
`tinytuya2mqtt`.

```
python -m tinytuya wizard
```

Create a `tinytuya2mqtt.ini` config file, mapping your device pins to the named capabilities. For
example:

```ini
[device bf7bf4939779bbd9afllck]
fan_state = 1
fan_speed = 3
fan_speed_steps = 1,2,3,4,5,6
light_state = 15
light_brightness = 16
light_brightness_steps = 25,125,275,425,575,725,900,1000
light_temp = 17

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
|Fan|Fan|`fan_state`|`1`|
|Fan|Fan|`fan_speed`|`3`|
|Fan|Fan|`fan_speed_steps`|`1,2,3,4,5,6`|
|Fan|Light|`light_state`|`15`|
|Fan|Light|`light_brightness`|`16`|
|Fan|Light|`light_brightness_steps`|`25,125,275,425,575,725,900,1000`|
|Fan|Light|`light_temp`|`17`|
