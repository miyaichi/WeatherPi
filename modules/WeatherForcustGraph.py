# pylint: disable=invalid-name
""" Weather forcust graph class
"""

import datetime
import logging
from modules.WeatherModule import WeatherModule, Utils
from modules.GraphUtils import GraphUtils


def check_condition(block, condition):
    """check block and condition
    """
    hourly = [
        "temp", "feels_like", "pressure", "humidity", "dew_point", "clouds",
        "wind_speed", "wind_deg"
    ]
    daily = [
        "temp.day", "temp.min", "temp.max", "temp.night", "temp.eve",
        "temp.morn", "feels_like.day", "feels_like.night", "feels_like.eve",
        "feels_like.morn", "pressure", "humidity", "dew_point", "clouds",
        "wind_speed", "wind_deg", "clouds", "rain", "uvi"
    ]
    if condition:
        if block == "hourly":
            if condition not in hourly:
                raise ValueError("{} {} not in {}".format(
                    block, condition, " ,".join(hourly)))
        elif block == "daily":
            if condition not in daily:
                raise ValueError("{} {} must be one of {}".format(
                    block, condition, ", ".join(daily)))
        else:
            raise ValueError("{} must be hourly or daily".format(block))


def adjust_unit(values, condition, units):
    """adjust values units
    """
    value = values
    for key in condition.split("."):
        value = value[key] if key in value else None
    if condition == "dt":
        return datetime.datetime.fromtimestamp(value)
    if value is not None:
        value = float(value)
    if condition.startswith("temp") or condition == "dew_point":
        return value if units == "metric" else Utils.fahrenheit(value)
    if condition in ("wind_speed", "wind_deg"):
        return round(Utils.kilometer(value) if units == "metric" else value, 1)
    return value


def label_name(condition):
    """format label name
    """
    label = condition.replace("_", " ").split(".")
    label[0] = label[0].capitalize()
    return " ".join(label)


class WeatherForcustGraph(WeatherModule):
    """
    Weather forcust graph Module

    This module plots weather condition data for the next 48 hours or 7 days.
    When two weather conditions are specified, a two-axis graph is plotted.

    example config:
    {
      "module": "WeatherForcustGraph",
      "config": {
        "rect": [x, y, width, height],
        "block": "hourly",
        "conditions": ["temp", "humidity"]
      }
     }

    Available weather conditions is following:
        hourly:
            temp, feels_like, pressure, humidity, dew_point, clouds,
            wind_speed, wind_deg
        daily:
            temp.day, temp.min, temp.max, temp.night, temp.eve,
            temp.morn, feels_like.day, feels_like.night, feels_like.eve,
            feels_like.morn, pressure, humidity, dew_point, clouds,
            wind_speed, wind_deg, clouds, rain, uvi

        https://openweathermap.org/api/one-call-api
    """

    def __init__(self, fonts, location, language, units, config):
        super().__init__(fonts, location, language, units, config)

        self.block = None
        if "block" in config:
            self.block = config["block"]

        self.conditions = []
        for condition in config["conditions"]:
            check_condition(self.block, condition)
            self.conditions.append(condition)
        if len(self.conditions) < 2:
            self.conditions.append(None)

        logging.info("weather forcust graph (%s. %s)", self.block,
                     ",".join(self.conditions))

    def draw(self, screen, weather, updated):
        if weather is None or not updated:
            return

        data = weather[self.block]
        times = list(map(lambda x: adjust_unit(x, "dt", self.units), data))
        y1 = ylabel1 = None
        if self.conditions[0]:
            y1 = list(
                map(lambda x: adjust_unit(x, self.conditions[0], self.units),
                    data))
            ylabel1 = label_name(self.conditions[0])
        y2 = ylabel2 = None
        if self.conditions[1]:
            y2 = list(
                map(lambda x: adjust_unit(x, self.conditions[1], self.units),
                    data))
            ylabel2 = label_name(self.conditions[1])

        self.clear_surface()
        GraphUtils.set_font(self.fonts["name"])
        GraphUtils.draw_2axis_graph(screen, self.surface, self.rect, times, y1,
                                    _(ylabel1), y2, _(ylabel2))
