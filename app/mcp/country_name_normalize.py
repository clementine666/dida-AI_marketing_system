"""MCP 英文国家名 → 业务映射表中文国名。"""

from __future__ import annotations

# 伽利略 dida_hotel_country_name 常见英文 → continent_l2_mapping 中文
EN_TO_CN: dict[str, str] = {
    "china": "中国",
    "japan": "日本",
    "korea": "韩国",
    "south korea": "韩国",
    "north korea": "韩国",
    "thailand": "泰国",
    "singapore": "新加坡",
    "malaysia": "马来西亚",
    "vietnam": "越南",
    "indonesia": "印度尼西亚",
    "philippines": "菲律宾",
    "australia": "澳大利亚",
    "new zealand": "新西兰",
    "fiji": "斐济",
    "usa": "美国",
    "us": "美国",
    "united states": "美国",
    "united states of america": "美国",
    "canada": "加拿大",
    "mexico": "墨西哥",
    "brazil": "巴西",
    "united kingdom": "英国",
    "great britain": "英国",
    "uk": "英国",
    "england": "英国",
    "france": "法国",
    "germany": "德国",
    "switzerland": "瑞士",
    "austria": "奥地利",
    "belgium": "比利时",
    "netherlands": "荷兰",
    "ireland": "爱尔兰",
    "luxembourg": "卢森堡",
    "spain": "西班牙",
    "portugal": "葡萄牙",
    "italy": "意大利",
    "greece": "希腊",
    "croatia": "克罗地亚",
    "serbia": "塞尔维亚",
    "slovenia": "斯洛文尼亚",
    "albania": "阿尔巴尼亚",
    "macedonia": "马其顿",
    "malta": "马耳他",
    "sweden": "瑞典",
    "finland": "芬兰",
    "norway": "挪威",
    "denmark": "丹麦",
    "iceland": "冰岛",
    "estonia": "爱沙尼亚",
    "latvia": "拉脱维亚",
    "poland": "波兰",
    "czech republic": "捷克",
    "czechia": "捷克",
    "hungary": "匈牙利",
    "romania": "罗马尼亚",
    "bulgaria": "保加利亚",
    "slovakia": "斯洛伐克",
    "lithuania": "立陶宛",
    "belarus": "白俄罗斯",
    "moldova": "摩尔多瓦",
    "russia": "俄罗斯",
    "turkey": "土耳其",
    "uae": "阿拉伯联合酋长国",
    "united arab emirates": "阿拉伯联合酋长国",
    "hong kong": "中国香港",
    "macau": "中国澳门",
    "macao": "中国澳门",
    "taiwan": "中国台湾",
    "taiwan, province of china": "中国台湾",
}


def normalize_country_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return raw
    if any("\u4e00" <= ch <= "\u9fff" for ch in raw):
        return raw
    key = raw.lower().replace("_", " ").strip()
    if key in EN_TO_CN:
        return EN_TO_CN[key]
    # Title case fallback: Thailand already handled
    return EN_TO_CN.get(key.title().lower(), raw)
