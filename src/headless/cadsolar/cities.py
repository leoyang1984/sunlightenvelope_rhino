"""
City coordinates and analysis-day presets.

Convenience only. These are city-centre approximations; a real project uses
its own surveyed position. The error is not large for this purpose - 0.01° of
latitude is about 1.1 km, which moves the sun by well under a tenth of a
degree - but it is an approximation, and a project on the edge of a large
municipality should give explicit --lat/--lon.

Shanghai is the exception: those numbers come from the official technical
rule cited in docs/SHANGHAI_DESIGN_PROFILE.md.

The analysis days are the ones Chinese practice uses for design-stage
comparison. They are NOT a compliance test - this engine samples 3D points,
not regulation window measuring points, and produces no report that can be
submitted for approval.
"""

# (中文名, pinyin, latitude, longitude)
_CITY_TABLE = [
    # 直辖市与主要省会
    ("上海", "shanghai", 31.233333, 121.466667),
    ("北京", "beijing", 39.9042, 116.4074),
    ("天津", "tianjin", 39.3434, 117.3616),
    ("重庆", "chongqing", 29.5630, 106.5516),
    ("广州", "guangzhou", 23.1291, 113.2644),
    ("深圳", "shenzhen", 22.5431, 114.0579),
    ("杭州", "hangzhou", 30.2741, 120.1551),
    ("南京", "nanjing", 32.0603, 118.7969),
    ("成都", "chengdu", 30.5728, 104.0668),
    ("武汉", "wuhan", 30.5928, 114.3055),
    ("西安", "xian", 34.3416, 108.9398),
    ("沈阳", "shenyang", 41.8057, 123.4315),
    ("哈尔滨", "harbin", 45.8038, 126.5349),
    ("长春", "changchun", 43.8171, 125.3235),
    ("济南", "jinan", 36.6512, 117.1201),
    ("郑州", "zhengzhou", 34.7466, 113.6254),
    ("长沙", "changsha", 28.2282, 112.9388),
    ("合肥", "hefei", 31.8206, 117.2272),
    ("福州", "fuzhou", 26.0745, 119.2965),
    ("南昌", "nanchang", 28.6820, 115.8579),
    ("昆明", "kunming", 25.0389, 102.7183),
    ("贵阳", "guiyang", 26.6470, 106.6302),
    ("南宁", "nanning", 22.8170, 108.3665),
    ("海口", "haikou", 20.0444, 110.1999),
    ("兰州", "lanzhou", 36.0611, 103.8343),
    ("银川", "yinchuan", 38.4872, 106.2309),
    ("西宁", "xining", 36.6171, 101.7782),
    ("呼和浩特", "huhehaote", 40.8414, 111.7519),
    ("乌鲁木齐", "urumqi", 43.8256, 87.6168),
    ("拉萨", "lhasa", 29.6520, 91.1721),
    ("石家庄", "shijiazhuang", 38.0428, 114.5149),
    ("太原", "taiyuan", 37.8706, 112.5489),
    # 其它常见地级市
    ("苏州", "suzhou", 31.2989, 120.5853),
    ("无锡", "wuxi", 31.4900, 120.3119),
    ("常州", "changzhou", 31.8107, 119.9740),
    ("南通", "nantong", 31.9802, 120.8943),
    ("徐州", "xuzhou", 34.2058, 117.2848),
    ("宁波", "ningbo", 29.8683, 121.5440),
    ("温州", "wenzhou", 27.9938, 120.6994),
    ("嘉兴", "jiaxing", 30.7522, 120.7500),
    ("绍兴", "shaoxing", 30.0301, 120.5804),
    ("金华", "jinhua", 29.1028, 119.6474),
    ("台州", "taizhou", 28.6560, 121.4207),
    ("厦门", "xiamen", 24.4798, 118.0894),
    ("泉州", "quanzhou", 24.8741, 118.6757),
    ("佛山", "foshan", 23.0219, 113.1214),
    ("东莞", "dongguan", 23.0207, 113.7518),
    ("珠海", "zhuhai", 22.2707, 113.5767),
    ("中山", "zhongshan", 22.5170, 113.3928),
    ("惠州", "huizhou", 23.1115, 114.4162),
    ("汕头", "shantou", 23.3535, 116.6820),
    ("青岛", "qingdao", 36.0671, 120.3826),
    ("烟台", "yantai", 37.4638, 121.4479),
    ("潍坊", "weifang", 36.7069, 119.1618),
    ("淄博", "zibo", 36.8131, 118.0548),
    ("临沂", "linyi", 35.1045, 118.3564),
    ("大连", "dalian", 38.9140, 121.6147),
    ("鞍山", "anshan", 41.1105, 122.9900),
    ("唐山", "tangshan", 39.6303, 118.1804),
    ("保定", "baoding", 38.8739, 115.4646),
    ("洛阳", "luoyang", 34.6197, 112.4540),
    ("襄阳", "xiangyang", 32.0090, 112.1220),
    ("大庆", "daqing", 46.5891, 125.1030),
    ("齐齐哈尔", "qiqihaer", 47.3543, 123.9180),
]

DEFAULT_TIMEZONE = 8.0

CITIES = {}

for _chinese, _pinyin, _lat, _lon in _CITY_TABLE:
    CITIES[_chinese] = (_lat, _lon, DEFAULT_TIMEZONE)
    CITIES[_pinyin] = (_lat, _lon, DEFAULT_TIMEZONE)

# A few spellings people actually type.
for _alias, _target in [
    ("xi'an", "西安"),
    ("hohhot", "呼和浩特"),
    ("wulumuqi", "乌鲁木齐"),
    ("lasa", "拉萨"),
]:
    CITIES[_alias] = CITIES[_target]


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

    text = str(name).strip()
    return CITIES.get(text.lower()) or CITIES.get(text)


def lookup_day(name):
    """Return (month, day, start_hour, end_hour, label) or None."""
    if not name:
        return None

    text = str(name).strip()
    return DAYS.get(text.lower()) or DAYS.get(text)


def known_cities():
    """Chinese city names, in table order."""
    return [chinese for chinese, _, _, _ in _CITY_TABLE]
