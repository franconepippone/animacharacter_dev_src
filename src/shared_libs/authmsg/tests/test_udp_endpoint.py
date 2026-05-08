from authmsg.udp_endpoint import UDPEndpoint
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async():
    udp1 = UDPEndpoint(0)
    udp2 = UDPEndpoint(0)

    udp1.connect('127.0.0.1', udp2.local_port)
    udp2.connect('127.0.0.1', udp1.local_port)

    async def deffered_send():
        await asyncio.sleep(2.0)
        await udp1.asend(b"last")

    await udp1.asend(b"hello")
    await udp1.asend(b"there")
    task = asyncio.create_task(deffered_send())

    assert (await udp2.arecv()) == b"hello"
    assert (await udp2.arecv()) == b"there"
    
    print("im waiting")
    assert (await udp2.arecv()) == b"last"
    print("got it")
    await task

def test_sync():
    udp1 = UDPEndpoint(0)
    udp2 = UDPEndpoint(0)

    print(udp1.local_port, udp2.local_port)

    udp1.connect('127.0.0.1', udp2.local_port)
    udp2.connect('127.0.0.1', udp1.local_port)

    udp1.send(b"hello")
    assert udp2.recv() == b"hello"

    udp2.send(b"world")
    assert udp1.recv() == b"world"

    udp1.close()
    udp2.close()

def test_intruder():
    udp1 = UDPEndpoint(0, timeout=1.0)
    udp2 = UDPEndpoint(0)
    udp_intruder = UDPEndpoint(0)

    udp1.connect('127.0.0.1', udp2.local_port)
    udp2.connect('127.0.0.1', udp1.local_port)
    # intruder wants to talk to udp1
    udp_intruder.connect('127.0.0.1', udp1.local_port)

    udp2.send(b"udp2")
    udp_intruder.send(b"udp intruder")

    assert udp1.recv() == b"udp2"
    assert udp1.recv() == None # this hangs for 1 second

def test_without_connection():
    udp1 = UDPEndpoint(0)
    udp2 = UDPEndpoint(0)

    #udp1.connect('127.0.0.1', udp2.local_port)
    #udp2.connect('127.0.0.1', udp1.local_port)
    with pytest.raises(ValueError):
        udp1.send(b"hello")
    
    with pytest.raises(ValueError):
        udp2.send(b"world")

    udp1.close()
    udp2.close()

def test_connect_to_unexistant_peer():
    udp = UDPEndpoint(0)
    udp.connect('123.12.2.31', 5320)