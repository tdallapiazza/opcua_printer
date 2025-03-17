# OPC UA printer

This project is an OPC UA server for a klipper/moonraker 3D printer (my personnal needs).

## Description

Some data and commands from the Moonraker API are made accessible througe an OPC UA server. This will ease the integration of 3D printer in an automatized factory floor.

## Getting Started

### Dependencies

* Of course this depends on opcua-asyncio. Simply install using

´´´
uv pip install asyncua
´´´

### Executing program

Simply run the server script
```
python3 server.py
```

## Authors

Thomas Dalla Piazza

## Version History

* 0.1
    * Comming (soon or later...)

## License

This project is licensed under the [LGPL-3.0] License.