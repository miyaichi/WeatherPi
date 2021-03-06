# pylint: disable=invalid-name, broad-except
"""Japan Meteorological Agency alerts module
"""

import logging
from xml.etree import ElementTree as et
import requests
from modules.WeatherModule import WeatherModule
from modules.RepeatedTimer import RepeatedTimer


def weather_alerts(prefectures, city):
    """Get weather alerts
    """

    try:
        response = requests.get(
            "https://www.data.jma.go.jp/developer/xml/feed/extra.xml")
        response.raise_for_status()

        data = et.fromstring(response.content)
        ns = {"ns": "http://www.w3.org/2005/Atom"}
        url = None
        for element in data.findall("./ns:entry", ns):
            if element.find("ns:content", ns).text.find(prefectures) > -1:
                if element.find("ns:title", ns).text == "気象特別警報・警報・注意報":
                    url = element.find("ns:link", ns).attrib["href"]
                    break
        if not url:
            return None

        response = requests.get(url)
        response.raise_for_status()

        data = et.fromstring(response.content)
        ns = {"ns": "http://xml.kishou.go.jp/jmaxml1/body/meteorology1/"}
        return list(
            map(
                lambda x: x.text,
                data.findall(
                    "ns:Body/ns:Warning//*[ns:Name='{}']../ns:Kind/ns:Name".
                    format(city), ns)))

    except Exception as e:
        logging.error(e, exc_info=True)
        return None


class JMAAlerts(WeatherModule):
    """
    気象庁 (Japan Meteorological Agency) alerts module

    example config:
    {
      "module": "JMAAlerts",
      "config": {
        "rect": [x, y, width, height],
        "prefectures": "東京都",
        "city": "中央区"
       }
    }

    気象庁防災情報XMLフォーマット形式電文の公開（PULL型）で公開されているAtomフィードのうち、
    "高頻度フィード/随時"のフィードに掲載された都道府県のデータフィードから、指定した市区町村の
    注意報、警報、特別警報を取得し、表示する。

    参考：http://xml.kishou.go.jp/xmlpull.html
    """

    def __init__(self, fonts, location, language, units, config):
        super().__init__(fonts, location, language, units, config)
        if "prefectures" in config and "city" in config:
            self.prefectures = config["prefectures"]
            self.city = config["city"]
        elif self.location["address"]:
            self.city, self.prefectures = self.location["address"].split(",")
        if not self.prefectures or not self.city:
            raise ValueError(__class__.__name__)

        # start weather alerts thread
        self.timer_thread = RepeatedTimer(600, weather_alerts,
                                          [self.prefectures, self.city])
        self.timer_thread.start()

    def quit(self):
        if self.timer_thread:
            self.timer_thread.quit()

    def draw(self, screen, weather, updated):
        if weather is None:
            message = "Waiting data..."
        else:
            result = self.timer_thread.get_result()
            if result:
                message = ",".join(list(map(_, result)))
            else:
                message = ""

        self.clear_surface()
        if message:
            logging.info("%s: %s", __class__.__name__, message)
            if "特別警報" in message:
                color = "violet"
            elif "警報" in message:
                color = "red"
            elif "注意報" in message:
                color = "yellow"
            else:
                color = "white"
            for size in ("large", "medium", "small"):
                w, h = self.text_size(message, size, bold=True)
                if w <= self.rect.width and h <= self.rect.height:
                    break
            self.draw_text(message, (0, 0),
                           size,
                           color,
                           bold=True,
                           align="center")
        self.update_screen(screen)
