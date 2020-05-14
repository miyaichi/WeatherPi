# pylint: disable=invalid-name, too-many-locals, broad-except
"""Utility class and WeatherModule class
"""

import datetime
import io
import logging
import math
import os
import sys
from functools import lru_cache
import requests
import pygame
import pygame.gfxdraw
from PIL import Image
from PIL import ImageDraw


class Utils:
    """Utility class
    """
    color_maps = [
        # hot: red
        {
            "celsius_a": 28,
            "celsius_b": 99,
            "color_a": pygame.Color("red")[:3],
            "color_b": pygame.Color("red")[:3]
        },
        # fine: orange - red
        {
            "celsius_a": 23,
            "celsius_b": 28,
            "color_a": pygame.Color("orange")[:3],
            "color_b": pygame.Color("red")[:3]
        },
        # chilly: white - orange
        {
            "celsius_a": 15,
            "celsius_b": 23,
            "color_a": pygame.Color("white")[:3],
            "color_b": pygame.Color("orange")[:3]
        },
        # cold: blue - white
        {
            "celsius_a": 0,
            "celsius_b": 15,
            "color_a": pygame.Color("blue")[:3],
            "color_b": pygame.Color("white")[:3]
        },
        # cold: blue
        {
            "celsius_a": -99,
            "celsius_b": 0,
            "color_a": pygame.Color("blue")[:3],
            "color_b": pygame.Color("blue")[:3]
        }
    ]

    @staticmethod
    def strftime(timestamp, fmt):
        """
        Format unix timestamp to text.
        """
        return datetime.datetime.fromtimestamp(int(timestamp)).strftime(fmt)

    @staticmethod
    def percentage_text(value):
        """
        Format percentega value to text.
        """
        return "{}%".format(value)

    @staticmethod
    def pressure_text(value):
        """
        Format pressure value to text.
        """
        return "{}pa".format(value)

    @staticmethod
    def speed_text(value, units):
        """
        Format speed value to text
        """
        return ("{}m/s" if units == "metric" else "{}mi/s").format(value)

    @staticmethod
    def temperature_text(value, units):
        """
        Format temperature value to text
        """
        return ("{}°c" if units == "metric" else "{}°f").format(value)

    @staticmethod
    def color(name):
        """
        Convert Color name to RGB value
        """
        return pygame.Color(name)[:3]

    @staticmethod
    def heat_index(f, h):
        """
        Calculate heat index from temperature and humidity
        """
        if f < 80:
            return f
        return -42.379 + 2.04901523 * f + 10.14333127 * h - 0.22475541 * \
            f * h - 6.83783 * (10 ** -3) * (f ** 2) - 5.481717 * \
            (10 ** -2) * (h ** 2) + 1.22874 * (10 ** -3) * (f ** 2) * \
            h + 8.5282 * (10 ** -4) * f * (h ** 2) - 1.99 * \
            (10 ** -6) * (f ** 2) * (h ** 2)

    @staticmethod
    def celsius(value):
        """
        Convert fahrenheit to celsius
        """
        return (value - 32.0) * 0.555556

    @staticmethod
    def fahrenheit(value):
        """
        Convert celsius to fahrenheit
        """
        return (value * 1.8) + 32.0

    @staticmethod
    def kilometer(value):
        """
        Convert mile to kilometer
        """
        return value * 1.609344

    @staticmethod
    def heat_color(temperature, humidity, units):
        """
        Return heat index color
        """

        def gradation(color_a, color_b, val_a, val_b, val_x):
            def geometric(a, b, p):
                return int((b - a) * p / 100 + a)

            p = (val_x - val_a) / (val_b - val_a) * 100
            color_x = [geometric(color_a[i], color_b[i], p) for i in range(3)]
            return color_x

        fahrenheit = Utils.fahrenheit(
            temperature) if units == "metric" else temperature
        celsius = Utils.celsius(Utils.heat_index(fahrenheit, humidity))

        color = Utils.color("white")
        for color_map in Utils.color_maps:
            if color_map["celsius_a"] <= celsius < color_map["celsius_b"]:
                color = gradation(color_map["color_a"], color_map["color_b"],
                                  color_map["celsius_a"],
                                  color_map["celsius_b"], celsius)
                break
        return color

    @staticmethod
    def uv_color(uv_index):
        """
        Return UV index color
        """
        if uv_index < 3:
            color = "green"
        elif uv_index < 6:
            color = "yellow"
        elif uv_index < 8:
            color = "orange"
        elif uv_index < 11:
            color = "red"
        else:
            color = "violet"
        return Utils.color(color)

    @staticmethod
    def wind_bearing_text(angle):
        """Return wind bearig text
        """
        bearing = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW",
            "WSW", "W", "WNW", "NW", "NNW", "N"
        ]
        text = bearing[int(angle / 22.5)]
        return _(text)

    @staticmethod
    @lru_cache()
    def font(name, size, bold):
        """Create a new Font object
        """
        logging.debug("font %s %spxl loaded", name, size)
        return pygame.font.SysFont(name, size, bold)

    @staticmethod
    @lru_cache()
    def weather_icon(name, size):
        """Create a weather image
        """
        try:
            file = "{}/icons/{}.png".format(sys.path[0], name)
            if os.path.isfile(file):
                # get icons from local folder
                image = Image.open(file)
            else:
                # get icons from OpwnWeather
                response = requests.get(
                    "http://openweathermap.org/img/wn/{}@2x.png".format(name))
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))

            # resize icon
            (width, height) = image.size
            if width >= height:
                (width, height) = (size, int(size / width * height))
            else:
                (width, height) = (int(size / width * height), size)
            image = image.resize((width, height), Image.LANCZOS)

            # convert pygame image
            image = pygame.image.fromstring(image.tobytes(), image.size,
                                            image.mode)

            logging.debug("weather icon %s %s loaded", name, size)
            return image

        except Exception as e:
            logging.error(e, exc_info=True)
            return None

    @staticmethod
    @lru_cache()
    def moon_icon(age, size):
        """Create a moon phase image
        """
        _size = 200
        radius = int(_size / 2)

        image = Image.new("RGB", (_size + 2, _size + 2))
        draw = ImageDraw.Draw(image)

        # draw full moon
        draw.ellipse([(1, 1), (_size, _size)], fill="white")

        # draw shadow
        theta = age / 14.765 * math.pi
        sum_x = sum_length = 0
        for y in range(-radius, radius, 1):
            alpha = math.acos(y / radius)
            x = radius * math.sin(alpha)
            length = radius * math.cos(theta) * math.sin(alpha)
            if age < 15:
                start = (radius - x + 1, radius + y + 1)
                end = (radius + length + 1, radius + y + 1)
            else:
                start = (radius - length + 1, radius + y + 1)
                end = (radius + x + 1, radius + y + 1)
            draw.line((start, end), fill="dimgray")
            sum_x += 2 * x
            sum_length += end[0] - start[0]

        # resize
        image = image.resize((size, size), Image.LANCZOS)

        # convert pygame image
        image = pygame.image.fromstring(image.tobytes(), image.size,
                                        image.mode)
        logging.info("moon phase age: %s parcentage: %s", age,
                     round(100 - (sum_length / sum_x) * 100, 1))
        return image

    @staticmethod
    @lru_cache()
    def wind_arrow_icon(wind_deg, size):
        """Create a wind direction allow image
        """
        _size = 200
        color = pygame.Color("White")
        width = 0.15 * _size  # arrowhead width
        height = 0.25 * _size  # arrowhead height

        radius = _size / 2
        angle = 90 - wind_deg
        theta = angle / 360 * math.pi * 2

        tail = (radius + radius * math.cos(theta),
                radius - radius * math.sin(theta))
        head = (radius + radius * math.cos(theta + math.pi),
                radius - radius * math.sin(theta + math.pi))

        base_vector = (head[0] - tail[0], head[1] - tail[1])
        length = math.sqrt(base_vector[0]**2 + base_vector[1]**2)
        unit_vector = (base_vector[0] / length, base_vector[1] / length)

        left = (head[0] - unit_vector[1] * width - unit_vector[0] * height,
                head[1] + unit_vector[0] * width - unit_vector[1] * height)
        right = (head[0] + unit_vector[1] * width - unit_vector[0] * height,
                 head[1] - unit_vector[0] * width - unit_vector[1] * height)

        image = Image.new("RGB", (_size, _size))
        draw = ImageDraw.Draw(image)
        draw.line([head, tail], fill="white", width=4)
        draw.polygon([head, left, right], fill="white")

        # resize
        image = image.resize((size, size), Image.LANCZOS)

        # convert pygame image
        image = pygame.image.fromstring(image.tobytes(), image.size,
                                        image.mode)
        return image

    @staticmethod
    def display_sleep():
        """Send display sleep event
        """
        DISPLAY_SLEEP = pygame.USEREVENT + 1
        pygame.event.post(pygame.event.Event(DISPLAY_SLEEP))

    @staticmethod
    def display_wakeup():
        """Send display wakeup event
        """
        DISPLAY_WAKEUP = pygame.USEREVENT + 2
        pygame.event.post(pygame.event.Event(DISPLAY_WAKEUP))

    @staticmethod
    def restart():
        """
        send system restart event
        """
        RESTART = pygame.USEREVENT + 3
        pygame.event.post(pygame.event.Event(RESTART))


class WeatherModule:
    """Weather Module
    """

    def __init__(self, fonts, location, language, units, config):
        """Initialize
        """
        self.fonts = fonts
        self.location = location
        self.language = language
        self.units = units
        self.config = config
        self.rect = pygame.Rect(config["rect"])
        self.surface = pygame.Surface((self.rect.width, self.rect.height))

    def quit(self):
        """Destractor
        """

    def draw(self, screen, weather, updated):
        """Draw surface
        """

    def clear_surface(self):
        """Clear Surface
        """
        self.surface.fill(pygame.Color("black"))

    def update_screen(self, screen):
        """Draw surface on screen
        """
        screen.blit(self.surface, (self.rect.left, self.rect.top))

    def text_size(self, text, size, *, bold=False):
        """
        determine the amount of space needed to render text
        """
        if not text:
            return (0, 0)
        return self.font(size, bold).size(text)

    def text_warp(self, text, line_width, size, *, bold=False, max_lines=0):
        """
        Text wrapping
        """
        font = self.font(size, bold)
        lines = []
        cur_line = ""
        cur_width = 0
        for char in text:
            (width, _height) = font.size(char)
            if cur_width + width > line_width:
                lines.append(cur_line)
                cur_line = ""
                cur_width = 0
            cur_line += char
            cur_width += width
        if cur_line:
            lines.append(cur_line)
        if 0 < max_lines < len(lines):
            # Put a placeholder if the text is truncated
            lines = lines[:max_lines]
            lines[max_lines - 1] = lines[max_lines - 1][:-2] + ".."
        return lines

    def font(self, size, bold):
        """
        create a new Font object
        """
        name = self.fonts["name"]
        if isinstance(size, str):
            size = self.fonts["size"][size]
        return Utils.font(name, size, bold)

    def draw_text(self,
                  text,
                  position,
                  size,
                  color,
                  *,
                  bold=False,
                  align="left",
                  background="black"):
        """
        Draw text.

        Parameters
        ----------
        text:
            text to draw
        position:
            render relative position (x, y)
        size:
            font size. ["small", "medium", "large"]
        color:
            color name or RGB color tuple
        bold:
            bold flag.
        align:
            text align. ["left", "center", "right"]
        background:
            background color
        """
        if not text:
            return position

        (x, y) = position
        font = self.font(size, bold)
        (width, height) = font.size(text)
        color = Utils.color(color) if isinstance(color, str) else color
        if align == "center":
            x = (self.rect.width - width) / 2
        elif align == "right":
            x = self.rect.width - width
        self.surface.blit(font.render(text, True, color, background), (x, y))
        (right, bottom) = (x + width, height)
        return right, bottom

    def draw_image(self, image, position, angle=0):
        """
        Draw an image.

        Parameters
        ----------
        image:
            image to draw
        position:
            render relative position (x, y)
        angle:
            counterclockwise  degrees angle
        """
        if not image:
            return position

        (x, y) = position
        (width, height) = image.get_size()
        if angle:
            image = pygame.transform.rotate(image, angle)
            x = x + (width - image.get_width()) / 2
            y = height + (height - image.get_height()) / 2
        self.surface.blit(image, (x, y))
        (right, bottom) = (x + width, y + height)
        return right, bottom
