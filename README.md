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

### Run it in a Docker container

The project includes a Dockerfile to run the server in a docker container. Issue the following commands to build and run the container.

´´´
docker build -t opcua-printer  .
docker run -d -p 127.0.0.1:4840:4840 opcua-printer
´´´

## Authors

Thomas Dalla Piazza

## Version History

* 0.1
    * Comming (soon or later...)

## License

This project is licensed under the [LGPL-3.0] License.