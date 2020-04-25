# pylint: disable=invalid-name
"""Covid-19 module
"""

import datetime
import pandas as pd
from modules.WeatherModule import WeatherModule
from modules.GraphUtils import GraphUtils


class Covid19Tokyo(WeatherModule):
    """
    東京都オープンデータカタログサイトで東京都福祉保健局が提供している「都内 新型コロナウイルス
    陽性患者の詳細データ」を取得し、感染者数をグラフ表示します。

    example config:
    {
      "module": "Covid19Tokyo",
      "config": {
        "rect": [x, y, width, height],
        "days_ago": 28
      }
     }
    """

    def __init__(self, fonts, location, language, units, config):
        super().__init__(fonts, location, language, units, config)
        self.days_ago = config["days_ago"] if "days_ago" in config else 0

    def draw(self, screen, weather, updated):
        if weather is None or not updated:
            return

        # Retrieve the data
        df = pd.read_csv(("https://stopcovid19.metro.tokyo.lg.jp"
                          "/data/130001_tokyo_covid19_patients.csv"))
        df["公表_年月日"] = pd.to_datetime(df["公表_年月日"])
        df["人数"] = 1
        new_cases = pd.DataFrame(df.groupby("公表_年月日").sum()["人数"])
        total_cases = new_cases.cumsum()

        # Filter the data
        if self.days_ago > 0 and self.days_ago < len(new_cases):
            start = new_cases.tail(1).index[0] - datetime.timedelta(
                days=self.days_ago)
            new_cases = new_cases[new_cases.index >= start]
            total_cases = total_cases[total_cases.index >= start]

        # Total cases and doubling time of new cases
        total = total_cases.tail(1)["人数"][0]
        dt = 70 / (new_cases.tail(5)["人数"].mean() /
                   total_cases.tail(2)["人数"][0] * 100)

        # Plot
        self.clear_surface()
        GraphUtils.set_font(self.fonts["name"])
        GraphUtils.draw_2axis_graph(
            screen,
            self.surface,
            self.rect,
            list(new_cases.index.date),
            new_cases.values,
            "New Cases",
            total_cases.values,
            "Total Cases (log)",
            title="COVID-19: Tokyo  Total: {:,}  DT: {:.2f}".format(total, dt),
            yscale2="log")
