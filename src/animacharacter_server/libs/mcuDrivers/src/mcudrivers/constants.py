# SerialDevice packet ids (0-199, 231-255)   
PSP_PACKID_MOTION = 1
PSP_PACKID_LEDS = 2
PSP_PACKID_PARAMETERS = 3
PSP_PACKID_CONTROL_FLAGS = 4 # hardware related (start, stop, reset)
PSP_PACKID_DIAGNOSTICS = 5


#### = custom diagnostic error codes (1 byte)
DGN_ERR_HARDWARE_INIT_FAIL = bytes([0x00]) # error during hardware initialization
DGN_HARDWARE_INIT_OK = bytes([0x01])
DGN_BEGINALL_OK = bytes([0x02])
DGN_HARDWARE_DEINIT_ACK = bytes([0x03])
# = ----- Body only
DGN_WRN_MOTOR_R = bytes([0x04])
DGN_WRN_MOTOR_L = bytes([0x05])


# = lifecycle request flag bitmasks
INIT_HARDWARE = bytes([0x01])
BEGIN_ALL = bytes([0x02])
DEINIT_HARDWARE = bytes([0x04])