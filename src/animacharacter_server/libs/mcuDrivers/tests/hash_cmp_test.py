import zlib
import random
import time

N = 10000000
print("generating")
tests_bytearrays = [memoryview(bytearray(random.getrandbits(8) for _ in range(15))) for _ in range(N)]
results = [0 for _ in range(N)]


print("starting")
start = time.perf_counter()

for i, b in enumerate(tests_bytearrays):
    results[i] = zlib.crc32(b)

end = time.perf_counter()

print(f"Elapsed: {end - start:.6f} seconds, {(end-start)/N * 1000:.6f} ms per crc.")


print("starting comp")
start = time.perf_counter()

for i in range(len(results)-1):
    t = results[i] == results[i+1]

end = time.perf_counter()

print(f"Elapsed: {end - start:.6f} seconds, {(end-start)/N * 1000:.6f} ms per cmp.")