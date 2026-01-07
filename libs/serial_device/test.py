import time
import random
import copy

from opt_cobs import OptimizedCOBS

# IMPORT YOUR ORIGINAL CLASS HERE
# from original_cobs import OriginalCOBS


START_BYTE = 0x00
MAX_PACKET_SIZE = 256

ITERATIONS = 500000
TEST_CASES = 100


def generate_test_payloads():
    """Generate a variety of payloads including edge cases"""
    payloads = []

    # No START_BYTE
    payloads.append(bytearray([random.randint(1, 255) for _ in range(64)]))

    # All START_BYTE
    payloads.append(bytearray([START_BYTE] * 64))

    # Alternating
    payloads.append(bytearray(
        START_BYTE if i % 2 == 0 else random.randint(1, 255)
        for i in range(64)
    ))

    # Random
    for _ in range(TEST_CASES):
        payloads.append(bytearray(
            random.randint(0, 255) for _ in range(random.randint(1, 128))
        ))

    # START_BYTE at edges
    payloads.append(bytearray([START_BYTE] + [1] * 62 + [START_BYTE]))

    return payloads


def run_correctness_test(orig_cls, opt_cls):
    print("Running correctness tests...")

    payloads = generate_test_payloads()

    for idx, payload in enumerate(payloads):
        pay_len = len(payload)

        orig = orig_cls('COM3', restrict_ports = False)
        opt = opt_cls()

        orig.tx_buff[:pay_len] = payload
        opt.tx_buff[:pay_len] = payload

        orig.calc_overhead(pay_len)
        opt.calc_overhead(pay_len)

        if orig.overhead_byte != opt.overhead_byte:
            raise AssertionError(f"Overhead mismatch in test {idx}: {orig.overhead_byte} {opt.overhead_byte}")

        orig.stuff_packet(pay_len)
        opt.stuff_packet(pay_len)

        if orig.tx_buff[:pay_len] != opt.tx_buff[:pay_len]:
            raise AssertionError(f"Packet mismatch in test {idx}")

    print("✅ Correctness tests passed")


def benchmark(label, cls, *args, **kwargs):
    payloads = generate_test_payloads()
    print(*args)
    obj = cls(*args, **kwargs)

    start = time.perf_counter()

    for _ in range(ITERATIONS):
        payload = random.choice(payloads)
        pay_len = len(payload)
        obj.tx_buff[:pay_len] = payload
        obj.calc_overhead(pay_len)
        obj.stuff_packet(pay_len)

    elapsed = time.perf_counter() - start
    print(f"{label}: {elapsed:.4f}s")
    print(f"Time per iteration: {elapsed/ITERATIONS/1000}ms")
    return elapsed

def report_timing(label, total_time, iterations):
    t_iter = total_time / iterations

    print(
        f"{label}: "
        f"{total_time:.6f}s total | "
        f"{t_iter * 1e6:.2f} µs/iter | "
        f"{t_iter * 1e9:.1f} ns/iter"
    )

    return t_iter

def main():
    # Replace OriginalCOBS with your actual class
    from pySerialTransfer.pySerialTransfer import SerialTransfer

    run_correctness_test(SerialTransfer, OptimizedCOBS)

    print("\nRunning benchmarks...")
    t_orig = benchmark("Original", SerialTransfer, 'COM3', restrict_ports = False)
    t_opt = benchmark("Optimized", OptimizedCOBS, )

    print("\nPer-iteration timing:")
    tpi_orig = report_timing("Original", t_orig, ITERATIONS)
    tpi_opt  = report_timing("Optimized", t_opt, ITERATIONS)

    speedup = t_orig / t_opt
    print(f"\nSpeedup: {speedup:.2f}x")


if __name__ == "__main__":
    main()
