from time import sleep
from tabulate import tabulate
import sys
import time

import typer

from serial_port_scan import list_serial_ports
from serial_device import SerialDevice, PACKID_DEBUG_TRIGGER_IDENT_RQST, PACKID_DEBUG_TRIGGER_LARGE_TX


app = typer.Typer()


@app.command()
def discover(
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name")
    ):
    ports = list_serial_ports()
    print("Available ports: ", ports)
    port_name_map = {}
    for port in ports:
        with SerialDevice(name, port, baudrate) as link:
            link.open(1)
            sleep(3)

            peer_name = link.request_peername(3)
            if peer_name:
                port_name_map[port] = peer_name
    
    table = [[k, v] for k, v in port_name_map.items()]

    print(tabulate(table, headers=["Port", "Name"]))

@app.command()
def ping(
    port: str = typer.Option("COM3", help="Serial port on which to connect"),
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name"),
    times: int = typer.Option(5, help="How many times to ping")
    ):
    with SerialDevice(name, port, baudrate) as link:
        link.open(1)
        sleep(3)

        for i in range(times):
            print(f"Pinging device [{i+1}]")
            outcome = link.ping()
            if outcome:
                print(f"Got ping response, latency (round-trip): {outcome:.2f}ms")
            else:
                print("Ping timed out")
            time.sleep(.5)

@app.command()
def get_info(
    port: str = typer.Option("COM3", help="Serial port on which to connect"),
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name")
    ):
    with SerialDevice(name, port, baudrate) as link:
        link.open(1)
        sleep(3)

        print("Requesting info to peer")
        info = link.request_info(5)
        import json
        print(json.dumps(info, indent=4))

@app.command()
def get_name(
    port: str = typer.Option("COM3", help="Serial port on which to connect"),
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name")
    ):
    with SerialDevice(name, port, baudrate) as link:
        link.open(1)
        sleep(3)

        print("Requesting name to peer")
        peer_name = link.request_peername(3)
        print("got:", peer_name)

@app.command()
def trig_name_rqst(
    port: str = typer.Option("COM3", help="Serial port on which to connect"),
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name")
    ):
    with SerialDevice(name, port, baudrate) as link:
        link.open(1)
        sleep(3)    # for stability
        
        link.send(PACKID_DEBUG_TRIGGER_IDENT_RQST, 1) # trigger identity request from board
        print("sent trigger")

        # waits for packet
        p = link.wait_packet(5)
        print("Device has registered our name as: ", p)

@app.command()
def trig_large_tx(
    port: str = typer.Option("COM3", help="Serial port on which to connect"),
    baudrate: int = typer.Option(115200, help="Serial baud rate"),
    name: str = typer.Option("fragolino", help="This serial device name")
    ):
    with SerialDevice(name, port, baudrate) as link:
        link.open(1)
        sleep(3)

        link.send(PACKID_DEBUG_TRIGGER_LARGE_TX, 1)
        print("sent trigger")

        p = link.wait_packet(10)
        print("got packet", p)

if __name__ == '__main__':
    app()