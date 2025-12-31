import time


class DroneController:
    """Placeholder drone controller. Replace SDK calls with real drone API."""

    def __init__(self):
        self.in_air = False

    def takeoff(self):
        print("Drone taking off")
        self.in_air = True

    def land(self):
        print("Drone landing")
        self.in_air = False

    def goto(self, lat: float, lon: float, alt: float):
        print(f"Navigating to {lat},{lon} at {alt}m")
        time.sleep(1)

    def start_motor(self):
        print("Motor started")

    def stop_motor(self):
        print("Motor stopped")
