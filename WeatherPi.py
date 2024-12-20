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
import os
import sys
import time

import pygame
import requests

from modules.BuiltIn import (Alerts, Clock, Location, MoonPhase, SunriseSuset,
                             Weather, WeatherForecast, Wind)
from modules.RepeatedTimer import RepeatedTimer


def weather_forecast(appid, latitude, longitude, language, units):
    """get weather forcast data using openweather api
    """
    try:
        resopnse = requests.get(
            "https://api.openweathermap.org/data/3.0/onecall" +
            "?appid={}&lat={}&lon={}&lang={}&units={}".format(
                appid, latitude, longitude, language, units))
        resopnse.raise_for_status()
        return resopnse.json()

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
            })
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

    try:
        # load config file
        file = "/boot/WeatherPi.json"
        if not os.path.exists(file):
            file = "{}/config.json".format(sys.path[0])
        with open(file, "r") as f:
            config = json.loads(f.read())
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
        if "DISPLAY_NO" in config:
            os.putenv("DISPLAY", config["DISPLAY_NO"])
        if "SDL_FBDEV" in config:
            os.putenv("SDL_FBDEV", config["SDL_FBDEV"])
        pygame.init()
        pygame.mouse.set_visible(False)
        if pygame.display.mode_ok(config["display"]):
            display = screen = pygame.display.set_mode(config["display"])
            scale = None
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
        logging.info("pygame initialized. display:%s screen:%s scale:%s",
                     display.get_size(), screen.get_size(), scale)

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
                if scale:
                    # fit to display
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
            pygame.image.save(display, args.screenshot)
        if timer_thread:
            timer_thread.quit()
        for module in modules:
            module.quit()
        pygame.quit()
        if restart:
            logging.info("restarting..")
            os.execl(sys.executable, sys.executable, *sys.argv)
        if reboot:
            os.system('sudo reboot')
        sys.exit()


if __name__ == "__main__":
    main()
