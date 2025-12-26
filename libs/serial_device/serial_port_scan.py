import sys
import glob
import serial

def list_serial_ports():
    """ List all serial port names available on the system """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % i for i in range(1, 257)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform: {}'.format(sys.platform))

    available_ports = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            available_ports.append(port)
        except (OSError, serial.SerialException):
            pass
    return available_ports

if __name__ == '__main__':
    print(list_serial_ports())
