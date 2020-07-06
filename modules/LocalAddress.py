# pylint: disable=invalid-name, broad-except
"""Local IP Address module
"""

import logging
import socket
from modules.WeatherModule import WeatherModule, Utils


def get_local_address():
    """Get local ip address
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 1))  # 8.8.8.8 is Google Public DNS
            return s.getsockname()[0]

    except Exception as e:
        logging.error(e, exc_info=True)
        return None


class LocalAddress(WeatherModule):
    """Local IP address display and Network connection monitor module

    This module can display the local ip address and also monitor the network connection.

    example config:
    {
      "module": "LocalAddress",
      "config": {
        "rect": [x, y, width, height],
        "seconds_to_reboot": 180
       }
    }
    """
    def __init__(self, fonts, location, language, units, config):
        super().__init__(fonts, location, language, units, config)
        self.seconds = 0
        self.seconds_to_reboot = 0
        if isinstance(config["seconds_to_reboot"], int):
            self.seconds_to_reboot = config["seconds_to_reboot"]

    def draw(self, screen, weather, updated):
        message = get_local_address()
        if message:
            self.seconds = 0
        else:
            message = "connection lost"
            self.seconds += 1
            if self.seconds_to_reboot and self.seconds > self.seconds_to_reboot:
                Utils.reboot()

        self.clear_surface()
        logging.info("%s: %s", __class__.__name__, message)
        for size in ("large", "medium", "small"):
            width, height = self.text_size(message, size, bold=True)
            if width <= self.rect.width and height <= self.rect.height:
                break
        self.draw_text(message, (0, 0),
                       size,
                       "white",
                       bold=True,
                       align="center")
        self.update_screen(screen)
