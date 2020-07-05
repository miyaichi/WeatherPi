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
    """Local IP Address
    """

    def __init__(self, fonts, location, language, units, config):
        super().__init__(fonts, location, language, units, config)
        self.retries = 0
        self.max_retries = 60

    def draw(self, screen, weather, updated):
        if weather is None or not updated:
            return

        message = get_local_address()

        self.clear_surface()
        if message:
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
        else:
            self.retries += 1
            if self.max_retries and self.retries > self.max_retries:
                Utils.reboot()
        self.update_screen(screen)
