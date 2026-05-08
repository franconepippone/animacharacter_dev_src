from authmsg import PeerTCP, PeerUDP, IsAlreadyInitialized, IsNotInitialized
import pytest
import asyncio

KEY1 = b"hello"
KEY2 = b"there"

def test_normal_usage():
    with pytest.raises(ValueError):
        peer = PeerUDP(timeout=-1)

    peer1 = PeerUDP(psk=KEY1)
    peer2 = PeerUDP(psk=KEY1)

    with pytest.raises(IsNotInitialized):
        peer1.send(b"test")
    
    with pytest.raises(IsNotInitialized):
        peer2.recv()

    peer1.dial(*peer2.local_address)
    peer2.dial(*peer1.local_address)

    with pytest.raises(IsAlreadyInitialized):
        peer1.dial('', -1)

    assert peer1.send(b"hello there")
    assert peer2.send(b"hi")
    assert peer2.recv() == b"hello there"
    assert peer1.recv() == b"hi"

    peer1.close()
    peer2.close()


def test_wrong_key():
    peer1 = PeerUDP(psk=KEY1, timeout=.5)
    peer2 = PeerUDP(psk=KEY2, timeout=1)

    peer1.dial(*peer2.local_address)
    peer2.dial(*peer1.local_address)

    assert peer1.send(b"try")
    assert peer2.recv() == b"" # receives empty

    assert peer2.send(b"again")
    assert peer1.recv() == b""


@pytest.mark.asyncio
async def test_async():
    udp1 = PeerUDP()
    udp2 = PeerUDP()

    udp1.dial(*udp2.local_address)
    udp2.dial(*udp1.local_address)

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