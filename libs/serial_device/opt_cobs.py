# optimized_cobs.py


START_BYTE = 0x7E
STOP_BYTE  = 0x81

MAX_PACKET_SIZE = 0xFE

class OptimizedCOBS:
    def __init__(self, buffer_size=MAX_PACKET_SIZE):
        self.tx_array = bytearray(buffer_size)
        self.tx_buff = memoryview(self.tx_array)
        self.overhead_byte = 0xFF

    def calc_overhead(self, pay_len: int) -> None:
        tx = self.tx_buff
        start = START_BYTE

        overhead = 0xFF
        for i in range(pay_len):
            if tx[i] == start:
                overhead = i
                break

        self.overhead_byte = overhead

    def find_last(self, pay_len: int) -> int:
        if pay_len > MAX_PACKET_SIZE:
            return -1

        tx = self.tx_buff
        start = START_BYTE

        for i in range(pay_len - 1, -1, -1):
            if tx[i] == start:
                return i
        return -1

    def __stuff_packet(self, pay_len: int) -> None:
        if pay_len > MAX_PACKET_SIZE:
            return

        tx = self.tx_buff
        start = START_BYTE

        ref = -1
        for i in range(pay_len - 1, -1, -1):
            if tx[i] == start:
                if ref == -1:
                    ref = i
                else:
                    tx[i] = ref - i
                    ref = i
    
    def stuff_packet(self, pay_len: int) -> None:
        if pay_len > MAX_PACKET_SIZE:
            return

        tx = self.tx_buff
        start = START_BYTE

        ref = -1

        for i in range(pay_len - 1, -1, -1):
            if tx[i] == start:
                if ref == -1:
                    # last START_BYTE → write 0
                    tx[i] = 0
                else:
                    tx[i] = ref - i
                ref = i

