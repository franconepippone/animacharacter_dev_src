import pygame
import time

def main():
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick detected")
        return

    js = pygame.joystick.Joystick(0)
    js.init()

    print("Using joystick:", js.get_name())
    print("Axes:", js.get_numaxes())

    while True:
        pygame.event.pump()  # required to update joystick state

        axis_values = [js.get_axis(i) for i in range(js.get_numaxes())]
        print(axis_values)

        time.sleep(0.02)  # 50 Hz polling

if __name__ == "__main__":
    main()
