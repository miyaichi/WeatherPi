#!/usr/bin/python3
# -*- coding: utf-8 -*-

import gettext
import hashlib
import importlib
import json
import locale
import logging
import os
import pygame
import requests
import sys
import time
from modules.BuiltIn import Alerts, Clock, Weather, WeatherForecast, SunriseSuset, MoonPhase, Wind
from modules.RepeatedTimer import RepeatedTimer


def weather_forecast(api_key, latitude, longitude, language, units):
    try:
        resopnse = requests.get(
            "https://api.forecast.io/forecast/{}/{},{}".format(
                api_key, latitude, longitude),
            params={
                "lang": language,
                "units": units,
                "exclude": "minutely,hourly,flags"
            })
        resopnse.raise_for_status()
        data = resopnse.json()
        hash = hashlib.md5(json.dumps(data).encode()).hexdigest()
        return data, hash

    except Exception as e:
        logging.error("darksky weather forecast api failed: {}".format(e))
        return None, None


def geolocode(key, address, latlng):
    try:
        response = response.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": address,
                "key": key
            })
        resopnse.raise_for_status()
        data = response.json()
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]

    except Exception as e:
        logging.error("google geocode api failed: {}".format(e))
        return None, None


def main():
    # initialize logger
    logging.basicConfig(level=logging.INFO,
                        stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")

    # initialize thread
    timer_thread = None

    # initialize modules
    modules = []

    try:
        # load config file
        file = "/boot/WeatherPi.json"
        if not os.path.exists(file):
            file = "{}/config.json".format(sys.path[0])
        with open(file, "r") as f:
            config = json.loads(f.read())
        logging.info("config.json loaded")

        # initialize locale, gettext
        language = config["locale"].split("_")[0]
        locale.setlocale(locale.LC_ALL, config["locale"])
        trans = gettext.translation("messages",
                                    localedir="{}/locale".format(sys.path[0]),
                                    languages=[language],
                                    fallback=True)
        trans.install()

        # start weather forecast thread
        timer_thread = RepeatedTimer(300, weather_forecast, [
            config["darksky_api_key"], config["latitude"], config["longitude"],
            language, config["units"]
        ])
        timer_thread.start()
        logging.info("weather forecast thread started")

        # initialize pygame
        os.putenv("SDL_FBDEV", config["SDL_FBDEV"])
        pygame.init()
        pygame.mouse.set_visible(False)
        screen = pygame.display.set_mode(config["display"])
        logging.info("pygame initialized")

        # load modules
        units = config["units"]
        fonts = {}
        for style in ["regular", "bold"]:
            fonts[style] = "{}/fonts/{}".format(sys.path[0],
                                                config["fonts"][style])
        modules = []
        for module in config["modules"]:
            name = module["module"]
            conf = module["config"]
            if name in globals():
                logging.info("load built-in module: {}".format(name))
                m = (globals()[name])
            else:
                logging.info("load external module: {}".format(name))
                m = getattr(importlib.import_module("modules.{}".format(name)),
                            name)
            modules.append((m)(fonts, language, units, conf))
        logging.info("modules loaded")

        # main loop
        running = True
        last_hash = None
        while running:
            # weather data check
            result = timer_thread.result()
            (weather, hash) = result if result is not None else (None, None)
            if last_hash == hash:
                updated = False
            else:
                logging.info("weather data updated")
                last_hash = hash
                updated = True

            # update screen
            for module in modules:
                module.draw(screen, weather, updated)
            pygame.display.update()

            # event check
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

            time.sleep(1)

    except Exception as e:
        logging.error(e)

    finally:
        if timer_thread:
            logging.info("weather forecast thread stopped")
            timer_thread.quit()
        for module in modules:
            module.quit()
        pygame.quit()
        quit()


if __name__ == "__main__":
    main()
