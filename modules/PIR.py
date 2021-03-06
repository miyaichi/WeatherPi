# pylint: disable=invalid-name, super-init-not-called
"""PIR(Passive Infrared Ray) motion sensor module
"""

import logging
import RPi.GPIO as GPIO
from modules.WeatherModule import WeatherModule, Utils


class PIR(WeatherModule):
    """
    PIR(Passive Infrared Ray) motion sensor module

    This module can monitor a PIR motion sensor and put display to sleep.

    example config:
    {
      "module": "PIR",
      "config": {
        "pin": 26,
        "power_save_delay": 300
      }
    }
    """

    def __init__(self, fonts, location, language, units, config):
        self.pin = None
        self.power_save_delay = None
        self.power_save_timer = 0

        if isinstance(config["pin"], int):
            self.pin = config["pin"]
        if isinstance(config["power_save_delay"], int):
            self.power_save_delay = config["power_save_delay"]
        if self.pin is None or self.power_save_delay is None:
            raise ValueError(__class__.__name__)

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.IN)

    def draw(self, screen, weather, updated):
        if GPIO.input(self.pin):
            Utils.display_wakeup()
            self.power_save_timer = 0
        else:
            self.power_save_timer += 1
            if self.power_save_timer > self.power_save_delay:
                logging.info("%s: screen sleep.", __class__.__name__)
                Utils.display_sleep()
