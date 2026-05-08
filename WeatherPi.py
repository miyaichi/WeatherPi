#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, unused-import, broad-except
# pylint: disable=too-many-locals, too-many-nested-blocks, too-many-branches
# pylint: disable=too-many-statements
"""Weather Station for Raspberry Pi and Small LCDs
"""

import argparse
import gettext
import importlib
import json
import locale
import logging
import mmap
import os
import struct
import subprocess
import sys
import time

import pygame
import requests
from PIL import Image

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from modules.BuiltIn import (Alerts, Clock, Location, MoonPhase, SunriseSuset,
                             Weather, WeatherForecast, Wind)
from modules.RepeatedTimer import RepeatedTimer


class FrameBuffer:
    """Write pygame.Surface directly to a Linux framebuffer device via mmap."""

    def __init__(self, device, width, height):
        self.width = width
        self.height = height
        self._cursor_hidden = False

        try:
            with open("/dev/tty1", "wb") as tty:
                tty.write(b"\033[?25l")
            self._cursor_hidden = True
        except OSError:
            pass

        fb_name = os.path.basename(device)
        try:
            with open("/sys/class/graphics/{}/bits_per_pixel".format(fb_name)) as f:
                self.bpp = int(f.read().strip())
        except OSError:
            self.bpp = 16

        try:
            self._size = width * height * (self.bpp // 8)
            self._file = open(device, "r+b")
            self._mmap = mmap.mmap(self._file.fileno(), self._size)
        except OSError:
            self._restore_console()
            raise
        logging.info("framebuffer %s: %dx%d %dbpp", device, width, height, self.bpp)

    def write(self, surface):
        """Convert pygame.Surface to the framebuffer pixel format and write via mmap."""
        raw = pygame.image.tobytes(surface, "RGB")
        image = Image.frombytes("RGB", (self.width, self.height), raw)
        data = self._to_rgb565(image) if self.bpp == 16 else image.convert("RGBX").tobytes()
        self._mmap.seek(0)
        self._mmap.write(data)

    def blank(self):
        """Fill the framebuffer with black."""
        self._mmap.seek(0)
        self._mmap.write(b'\x00' * self._size)

    def close(self):
        self.blank()
        try:
            self._mmap.close()
        finally:
            self._file.close()
        self._restore_console()

    def _restore_console(self):
        """Restore cursor and reset the framebuffer console."""
        if not self._cursor_hidden:
            return
        try:
            with open("/dev/tty1", "wb") as tty:
                tty.write(b"\033[?25h\033[H\033[2J")
            self._cursor_hidden = False
        except OSError:
            pass

    @staticmethod
    def _to_rgb565(image):
        """Convert a PIL RGB image to little-endian RGB565 bytes."""
        if _NUMPY_AVAILABLE:
            arr = np.array(image, dtype=np.uint16)
            rgb565 = ((arr[:, :, 0] & 0xF8) << 8) | \
                     ((arr[:, :, 1] & 0xFC) << 3) | \
                     (arr[:, :, 2] >> 3)
            return rgb565.astype('<u2').tobytes()
        else:
            pixels = list(image.getdata())
            buf = bytearray(len(pixels) * 2)
            for i, (r, g, b) in enumerate(pixels):
                struct.pack_into('<H', buf, i * 2,
                                 ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3))
            return bytes(buf)


def weather_forecast(appid, latitude, longitude, language, units):
    """get weather forcast data using openweather api
    """
    try:
        response = requests.get(
            "https://api.openweathermap.org/data/3.0/onecall" +
            "?appid={}&lat={}&lon={}&lang={}&units={}".format(
                appid, latitude, longitude, language, units),
            timeout=10)
        response.raise_for_status()
        return response.json()

    except Exception as e:
        logging.error(e, exc_info=True)
        return None


def geocode(key, language, address, latitude, longitude):
    """get latitude, longitude from address using google geocode api
    """
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": address,
                "language": language,
                "latlng": "{},{}".format(latitude, longitude),
                "key": key
            },
            timeout=10)
        response.raise_for_status()
        data = response.json()
        location = data["results"][0]["geometry"]["location"]
        components = []
        for component in data["results"][0]["address_components"]:
            if component["types"][0] in [
                    "locality", "administrative_area_level_1"
            ]:
                components.append(component["short_name"])
        address = ",".join(components)
        return location["lat"], location["lng"], address

    except Exception as e:
        logging.error(e, exc_info=True)
        return None


def main():
    """main program
    """

    # initialize logger
    parser = argparse.ArgumentParser(description=__file__)
    parser.add_argument("--debug",
                        "-d",
                        action="store_const",
                        const=True,
                        default=False)
    parser.add_argument("--screenshot", "-s")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")

    # initialize thread
    timer_thread = None

    # initialize modules
    modules = []

    # initialize restart flag
    restart = False

    # initialize reboot flag
    reboot = False

    # initialize framebuffer
    fb = None

    try:
        # load config file
        file = "/boot/WeatherPi.json"
        if not os.path.exists(file):
            file = "{}/config.json".format(sys.path[0])
        with open(file, "r") as f:
            config = json.load(f)
        logging.info("%s loaded", file)

        # initialize locale, gettext
        language = config["locale"].split("_")[0]
        locale.setlocale(locale.LC_ALL, config["locale"])
        trans = gettext.translation("messages",
                                    localedir="{}/locale".format(sys.path[0]),
                                    languages=[language],
                                    fallback=True)
        trans.install()

        # initialize address, latitude and longitude
        if "google_api_key" in config and config["google_api_key"]:
            results = geocode(config["google_api_key"], language,
                              config["address"], config["latitude"],
                              config["longitude"])
            if results is not None:
                latitude, longitude, address = results
                config["latitude"] = latitude
                config["longitude"] = longitude
                config["address"] = address
                logging.info("location: %s,%s %s", latitude, longitude,
                             address)

        # start weather forecast thread
        timer_thread = RepeatedTimer(600, weather_forecast, [
            config["openweather_appid"], config["latitude"],
            config["longitude"], language, config["units"]
        ])
        timer_thread.start()

        # initialize pygame
        use_framebuffer = "SDL_FBDEV" in config
        scale = None
        if use_framebuffer:
            # Headless mode: render to Surface, push pixels to /dev/fb1 via mmap
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            pygame.init()
            screen = pygame.Surface(config["display"])
            display = screen
            fb = FrameBuffer(config["SDL_FBDEV"], *config["display"])
        else:
            if "DISPLAY_NO" in config:
                os.environ["DISPLAY"] = config["DISPLAY_NO"]
            pygame.init()
            pygame.mouse.set_visible(False)
            if pygame.display.mode_ok(config["display"]):
                display = screen = pygame.display.set_mode(config["display"])
            else:
                display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                screen = pygame.Surface(config["display"])
                display_w, display_h = display.get_size()
                screen_w, screen_h = screen.get_size()
                if display_w / screen_w * screen_h <= display_h:
                    scale = (display_w, int(display_w / screen_w * screen_h))
                else:
                    scale = (int(display_h / screen_h * screen_w), display_h)
        DISPLAY_SLEEP = pygame.USEREVENT + 1
        DISPLAY_WAKEUP = pygame.USEREVENT + 2
        RESTART = pygame.USEREVENT + 3
        REBOOT = pygame.USEREVENT + 4
        logging.info("pygame initialized. screen:%s fb:%s scale:%s",
                     screen.get_size(), config.get("SDL_FBDEV"), scale)

        # load modules
        location = {
            "latitude": config["latitude"],
            "longitude": config["longitude"],
            "address": config["address"]
        }
        units = config["units"]
        fonts = config["fonts"]
        modules = []
        for module in config["modules"]:
            name = module["module"]
            conf = module["config"]
            if name in globals():
                logging.info("load built-in module: %s", name)
                mod = (globals()[name])
            else:
                logging.info("load external module: %s", name)
                mod = getattr(
                    importlib.import_module("modules.{}".format(name)), name)
            modules.append((mod)(fonts, location, language, units, conf))
        logging.info("modules loaded")

        # main loop
        display_wakeup = True
        last_hash_value = None
        running = True
        while running:
            # weather data check
            weather = timer_thread.get_result()
            updated = False
            if weather:
                hash_value = timer_thread.get_hash_value()
                if last_hash_value != hash_value:
                    logging.info("weather data updated")
                    last_hash_value = hash_value
                    updated = True

            # update screen
            for module in modules:
                module.draw(screen, weather, updated)

            # update display
            if display_wakeup:
                if fb:
                    fb.write(screen)
                else:
                    if scale:
                        display.blit(pygame.transform.scale(screen, scale), (0, 0))
                    pygame.display.flip()

            # event check
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == RESTART:
                    running = False
                    restart = True
                elif event.type == REBOOT:
                    running = False
                    reboot = True
                elif event.type == DISPLAY_SLEEP:
                    if display_wakeup:
                        if fb:
                            fb.blank()
                        else:
                            display.fill(pygame.Color("black"))
                            pygame.display.flip()
                        display_wakeup = False
                elif event.type == DISPLAY_WAKEUP:
                    if not display_wakeup:
                        last_hash_value = None
                        display_wakeup = True

            time.sleep(1)

    except Exception as e:
        logging.error(e, exc_info=True)

    finally:
        if args.screenshot:
            if fb:
                raw = pygame.image.tobytes(screen, "RGB")
                Image.frombytes("RGB", screen.get_size(), raw).save(args.screenshot)
            else:
                pygame.image.save(display, args.screenshot)
        if fb:
            fb.close()
        if timer_thread:
            timer_thread.quit()
        for module in modules:
            module.quit()
        pygame.quit()
        if restart:
            logging.info("restarting..")
            os.execl(sys.executable, sys.executable, *sys.argv)
        if reboot:
            subprocess.run(["sudo", "reboot"])
        sys.exit()


if __name__ == "__main__":
    main()
