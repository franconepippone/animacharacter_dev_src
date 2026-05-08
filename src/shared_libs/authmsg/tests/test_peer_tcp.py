from authmsg import PeerTCP, IsAlreadyInitialized, IsNotInitialized
import pytest
import asyncio
import time


KEY1 = b"hello"
KEY2 = b"there"

def test_normal_usage():
    with pytest.raises(ValueError):
        peer = PeerTCP(recv_timeout=-1)

    peer1 = PeerTCP(psk=KEY1)
    peer2 = PeerTCP(psk=KEY1)

    with pytest.raises(IsNotInitialized):
        peer1.send(b"test")
    
    with pytest.raises(IsNotInitialized):
        peer2.recv()

    peer1.listen(8001)
    peer2.dial('127.0.0.1', 8001)

    time.sleep(.5)

    print(peer1.local_address)
    print(peer2.local_address)
    print(peer1.remote_address)
    print(peer2.remote_address)

    with pytest.raises(IsAlreadyInitialized):
        peer1.dial('', -1)

    assert peer1.send(b"hello there")
    assert peer2.send(b"hi")
    assert peer2.recv() == b"hello there"
    assert peer1.recv() == b"hi"

    peer1.close()
    peer2.close()


def test_wrong_key():
    peer1 = PeerTCP(psk=KEY1, recv_timeout=.5)
    peer2 = PeerTCP(psk=KEY2, recv_timeout=1)

    peer1.listen(8001)
    peer2.dial('127.0.0.1', 8001)

    assert peer1.send(b"try")
    assert peer2.recv() == b"" # receives empty

    assert peer2.send(b"again")
    assert peer1.recv() == b""

    peer1.close()
    peer2.close()


@pytest.mark.asyncio
async def test_async():
    peer1 = PeerTCP()
    peer2 = PeerTCP()

    peer1.listen(8001)
    peer2.dial('127.0.0.1', 8001)

    async def deffered_send():
        await asyncio.sleep(2.0)
        await peer1.asend(b"last")

    await peer1.asend(b"hello")
    await peer1.asend(b"there")
    task = asyncio.create_task(deffered_send())

    assert (await peer2.arecv()) == b"hello"
    assert (await peer2.arecv()) == b"there"
    
    print("im waiting")
    assert (await peer2.arecv()) == b"last"
    print("got it")
    await task