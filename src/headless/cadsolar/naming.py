"""
Block-name convention parser.

The convention encodes the analysis role and the vertical dimension in the
block name, so an ordinary CAD drawing carries everything the pipeline needs
without a side-car file:

    方案a-100m       design volume, 100 m tall
    周边建筑a-50m    context building, 50 m tall
    建筑a-10m        context building, 10 m tall
    保护点1-1.5m     protected point, 1.5 m above ground
    地块-0m          site boundary (height ignored)

Grammar:

    <role><label> <separator> <number><unit>

    role       Chinese or ASCII keyword, longest match wins
    label      free text, may be empty
    separator  - _ － ＿ or whitespace
    number     decimal, optional sign stripped
    unit       m 米 mm 毫米 M, default m

Parsing is deliberately strict about the role keyword and forgiving about
everything else. Unparseable names are reported, never silently skipped —
a silent skip is what turns a naming typo into a confidently wrong answer.
"""

import re
import unicodedata

ROLE_DESIGN = "design"
ROLE_CONTEXT = "context"
ROLE_POINT = "point"
ROLE_SITE = "site"

# Longest keyword first so 周边建筑 wins over 建筑.
ROLE_KEYWORDS = [
    ("周边建筑", ROLE_CONTEXT),
    ("既有建筑", ROLE_CONTEXT),
    ("保护点", ROLE_POINT),
    ("日照点", ROLE_POINT),
    ("测点", ROLE_POINT),
    ("方案", ROLE_DESIGN),
    ("设计", ROLE_DESIGN),
    ("周边", ROLE_CONTEXT),
    ("建筑", ROLE_CONTEXT),
    ("地块", ROLE_SITE),
    ("场地", ROLE_SITE),
    ("scheme", ROLE_DESIGN),
    ("design", ROLE_DESIGN),
    ("context", ROLE_CONTEXT),
    ("existing", ROLE_CONTEXT),
    ("building", ROLE_CONTEXT),
    ("point", ROLE_POINT),
    ("site", ROLE_SITE),
    ("pt", ROLE_POINT),
]

UNIT_TO_METERS = {
    "m": 1.0,
    "米": 1.0,
    "mm": 0.001,
    "毫米": 0.001,
}

VALUE_PATTERN = re.compile(
    r"[-_－＿\s]\s*([0-9]+(?:[.．][0-9]+)?)\s*"
    r"(mm|m|毫米|米)?\s*$",
    re.IGNORECASE
)


class NameError_(ValueError):
    """Raised when a block name does not follow the convention."""


class ParsedName(object):
    """One decoded block name."""

    __slots__ = ("raw", "role", "label", "meters")

    def __init__(self, raw, role, label, meters):
        self.raw = raw
        self.role = role
        self.label = label
        self.meters = meters

    def __repr__(self):
        return "ParsedName({0!r}, {1}, {2!r}, {3})".format(
            self.raw, self.role, self.label, self.meters
        )


def normalize(name):
    """Fold full-width forms and trim, without touching the role keywords."""
    text = unicodedata.normalize("NFKC", str(name)).strip()
    return text


def parse_block_name(name):
    """
    Decode one block name.

    Returns a ParsedName, or raises NameError_ with a message that names the
    actual problem rather than 'invalid input'.
    """
    text = normalize(name)

    if not text:
        raise NameError_("块名为空。")

    lowered = text.lower()
    role = None
    keyword = None

    for candidate, candidate_role in ROLE_KEYWORDS:
        if lowered.startswith(candidate.lower()):
            role = candidate_role
            keyword = candidate
            break

    if role is None:
        raise NameError_(
            "块名 {0!r} 没有可识别的角色前缀。"
            "可用前缀：方案 / 建筑 / 周边建筑 / 保护点 / 地块"
            "（或 scheme / context / point / site）。".format(text)
        )

    remainder = text[len(keyword):]
    match = VALUE_PATTERN.search(remainder)

    if match is None:
        if role == ROLE_SITE:
            return ParsedName(text, role, remainder.strip(" -_"), 0.0)

        raise NameError_(
            "块名 {0!r} 缺少高度段。应写成 {1}a-50m 这样的形式，"
            "数字后面可以跟 m / 米 / mm / 毫米，默认按米。".format(
                text, keyword
            )
        )

    raw_value = match.group(1).replace("．", ".")
    unit = (match.group(2) or "m").lower()
    label = remainder[:match.start()].strip(" -_－＿")

    try:
        value = float(raw_value)
    except ValueError:
        raise NameError_(
            "块名 {0!r} 的数值 {1!r} 无法解析。".format(text, raw_value)
        )

    if role != ROLE_SITE and value <= 0.0:
        raise NameError_(
            "块名 {0!r} 的高度必须大于 0，读到 {1}。".format(text, value)
        )

    factor = UNIT_TO_METERS.get(unit)

    if factor is None:
        raise NameError_(
            "块名 {0!r} 的单位 {1!r} 不认识。".format(text, unit)
        )

    return ParsedName(text, role, label, value * factor)
