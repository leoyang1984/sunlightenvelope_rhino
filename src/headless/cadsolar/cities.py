"""
City coordinates and analysis-day presets.

Convenience only. The coordinates are city-centre approximations; a real
project uses its own surveyed position. Shanghai is the exception: those
numbers come from the official technical rule cited in
docs/SHANGHAI_DESIGN_PROFILE.md.

The analysis days are the ones Chinese practice uses for design-stage
comparison. They are NOT a compliance test — this engine samples 3D points,
not regulation window measuring points, and produces no report that can be
submitted for approval. See docs/SHANGHAI_DESIGN_PROFILE.md.
"""

CITIES = {
    "上海": (31.233333, 121.466667, 8.0),
    "shanghai": (31.233333, 121.466667, 8.0),
    "北京": (39.9042, 116.4074, 8.0),
    "beijing": (39.9042, 116.4074, 8.0),
    "广州": (23.1291, 113.2644, 8.0),
    "guangzhou": (23.1291, 113.2644, 8.0),
    "深圳": (22.5431, 114.0579, 8.0),
    "shenzhen": (22.5431, 114.0579, 8.0),
    "杭州": (30.2741, 120.1551, 8.0),
    "hangzhou": (30.2741, 120.1551, 8.0),
    "南京": (32.0603, 118.7969, 8.0),
    "nanjing": (32.0603, 118.7969, 8.0),
    "成都": (30.5728, 104.0668, 8.0),
    "chengdu": (30.5728, 104.0668, 8.0),
    "武汉": (30.5928, 114.3055, 8.0),
    "wuhan": (30.5928, 114.3055, 8.0),
    "西安": (34.3416, 108.9398, 8.0),
    "xian": (34.3416, 108.9398, 8.0),
    "天津": (39.3434, 117.3616, 8.0),
    "tianjin": (39.3434, 117.3616, 8.0),
    "重庆": (29.5630, 106.5516, 8.0),
    "chongqing": (29.5630, 106.5516, 8.0),
    "沈阳": (41.8057, 123.4315, 8.0),
    "shenyang": (41.8057, 123.4315, 8.0),
    "哈尔滨": (45.8038, 126.5349, 8.0),
    "harbin": (45.8038, 126.5349, 8.0),
    "青岛": (36.0671, 120.3826, 8.0),
    "qingdao": (36.0671, 120.3826, 8.0),
    "郑州": (34.7466, 113.6254, 8.0),
    "zhengzhou": (34.7466, 113.6254, 8.0),
    "长沙": (28.2282, 112.9388, 8.0),
    "changsha": (28.2282, 112.9388, 8.0),
    "昆明": (25.0389, 102.7183, 8.0),
    "kunming": (25.0389, 102.7183, 8.0),
    "乌鲁木齐": (43.8256, 87.6168, 8.0),
    "urumqi": (43.8256, 87.6168, 8.0),
}

# Analysis-day presets: (month, day, start_hour, end_hour, label)
DAYS = {
    "大寒": (1, 20, 8.0, 16.0, "大寒日 08:00–16:00"),
    "dahan": (1, 20, 8.0, 16.0, "大寒日 08:00–16:00"),
    "冬至": (12, 22, 9.0, 15.0, "冬至日 09:00–15:00"),
    "dongzhi": (12, 22, 9.0, 15.0, "冬至日 09:00–15:00"),
    "winter": (12, 22, 9.0, 15.0, "冬至日 09:00–15:00"),
    "夏至": (6, 21, 6.0, 18.0, "夏至日 06:00–18:00"),
    "summer": (6, 21, 6.0, 18.0, "夏至日 06:00–18:00"),
    "春分": (3, 21, 8.0, 16.0, "春分日 08:00–16:00"),
    "equinox": (3, 21, 8.0, 16.0, "春分日 08:00–16:00"),
}


def lookup_city(name):
    """Return (lat, lon, timezone) or None."""
    if not name:
        return None

    return CITIES.get(str(name).strip().lower()) or CITIES.get(str(name).strip())


def lookup_day(name):
    """Return (month, day, start_hour, end_hour, label) or None."""
    if not name:
        return None

    key = str(name).strip().lower()
    return DAYS.get(key) or DAYS.get(str(name).strip())


def known_cities():
    seen = []

    for key in CITIES:
        if not key.isascii():
            seen.append(key)

    return seen
