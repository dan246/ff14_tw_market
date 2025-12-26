"""常數和配置設定."""

# 繁中服資料中心和伺服器
DATA_CENTER = "陸行鳥"

WORLDS = {
    4028: "伊弗利特",
    4029: "迦樓羅",
    4030: "利維坦",
    4031: "鳳凰",
    4032: "奧汀",
    4033: "巴哈姆特",
    4034: "拉姆",
    4035: "泰坦",
}

WORLD_NAMES = list(WORLDS.values())
WORLD_IDS = {v: k for k, v in WORLDS.items()}

# API 端點
UNIVERSALIS_BASE = "https://universalis.app/api/v2"
XIVAPI_BASE = "https://xivapi.com"
CAFEMAKER_BASE = "https://cafemaker.wakingsands.com"

# 常用物品快速選擇（繁中名稱對應物品ID）
POPULAR_ITEMS = {
    # 戰鬥素材
    "暗物質 G8 / Grade 8 Dark Matter": 33916,
    "暗物質 G7 / Grade 7 Dark Matter": 21080,
    # 食物
    "炒蛋 / Fried Egg": 4653,
    "橙汁 / Orange Juice": 4654,
    # 基礎合成素材
    "黑膠 / Glue": 5506,
    "鐵礦 / Iron Ore": 5111,
    "棉花 / Cotton Boll": 5343,
    "原木 / Maple Log": 5380,
    "獸脂 / Animal Fat": 5507,
    "蜂蠟 / Beeswax": 5504,
    # 魔晶石
    "戰技魔晶石捌型": 33917,
    "咏唱魔晶石捌型": 33920,
    # 結晶
    "火之碎晶 / Fire Shard": 2,
    "冰之碎晶 / Ice Shard": 3,
    "風之碎晶 / Wind Shard": 4,
    "土之碎晶 / Earth Shard": 5,
    "雷之碎晶 / Lightning Shard": 6,
    "水之碎晶 / Water Shard": 7,
    "火之水晶 / Fire Crystal": 8,
    "冰之水晶 / Ice Crystal": 9,
    "風之水晶 / Wind Crystal": 10,
    "土之水晶 / Earth Crystal": 11,
    "雷之水晶 / Lightning Crystal": 12,
    "水之水晶 / Water Crystal": 13,
}

# 監看清單儲存檔案
WATCHLIST_FILE = "watchlist.json"

# API 請求超時時間（秒）
API_TIMEOUT = 10
MARKET_API_TIMEOUT = 15
