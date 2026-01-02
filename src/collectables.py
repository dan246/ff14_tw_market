"""收藏品採集時間表模組.

顯示大地使者（採礦工、園藝工、捕魚人）收藏品的採集時間表。
資料來源：FFXIV Teamcraft (https://github.com/ffxiv-teamcraft/ffxiv-teamcraft)
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

import requests
from opencc import OpenCC

# 繁簡轉換器
_s2t_converter = OpenCC('s2t')

# 資料快取目錄
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_EXPIRY = 86400 * 7  # 7 天過期

# Teamcraft GitHub 原始資料 URL
TEAMCRAFT_BASE = "https://raw.githubusercontent.com/ffxiv-teamcraft/ffxiv-teamcraft/master/libs/data/src/lib/json"

# ET 時間計算常數
# 現實 1 秒 = ET 20.571... 秒
# 現實 70 分鐘 = ET 24 小時（1 天）
EORZEA_MULTIPLIER = 3600 / 175  # ≈ 20.571

# 採集職業類型
GATHERING_JOBS = {
    0: "採礦工",  # MIN
    1: "園藝工",  # BTN
    2: "捕魚人",  # FSH - 釣魚節點類型不同
}

# 節點類型對應職業
NODE_TYPE_TO_JOB = {
    0: "採礦工",  # 礦脈
    1: "採礦工",  # 岩場
    2: "園藝工",  # 良材
    3: "園藝工",  # 草場
    4: "捕魚人",  # 釣場（可能不在 nodes.json）
    5: "捕魚人",
}

# 快取的資料
_nodes_cache: dict = {}
_collectables_cache: dict = {}
_items_zh_cache: dict = {}
_places_zh_cache: dict = {}
_gathering_items_cache: dict = {}
_fishing_sources_cache: dict = {}
_fishing_spots_cache: dict = {}
_npcs_cache: dict = {}
_npcs_zh_cache: dict = {}

# 老主顧 NPC 資料 (Custom Delivery NPCs)
# 每週可交納收藏品獲得額外獎勵
# 資料來源：Teamcraft + FFXIV Wiki
CUSTOM_DELIVERY_NPCS = [
    {
        "level_min": 50,
        "level_max": 60,
        "npc_id": 1019615,
        "npc_name_zh": "熙洛·阿里亞珀",
        "npc_name_en": "Zhloe Aliapoh",
        "location_zh": "田園郡",
        "zone_id": 2082,
        "x": 4.6,
        "y": 6.7,
    },
    {
        "level_min": 60,
        "level_max": 70,
        "npc_id": 1018393,
        "npc_name_zh": "亞德基拉",
        "npc_name_en": "Adkiragh",
        "location_zh": "田園郡",
        "zone_id": 2082,
        "x": 4.9,
        "y": 6.6,
    },
    {
        "level_min": 60,
        "level_max": 70,
        "npc_id": 1020395,
        "npc_name_zh": "梅·娜格",
        "npc_name_en": "M'naago",
        "location_zh": "神拳痕",
        "zone_id": 2403,
        "x": 14.6,
        "y": 9.4,
    },
    {
        "level_min": 62,
        "level_max": 70,
        "npc_id": 1025878,
        "npc_name_zh": "紅",
        "npc_name_en": "Kurenai",
        "location_zh": "碧玉水",  # Tamamizu
        "zone_id": 2409,
        "x": 28.5,
        "y": 15.2,
    },
    {
        "level_min": 70,
        "level_max": 80,
        "npc_id": 1029840,
        "npc_name_zh": "凱·希爾",
        "npc_name_en": "Kai-Shirr",
        "location_zh": "遊末邦",
        "zone_id": 2952,
        "x": 12.3,
        "y": 9.9,
    },
    {
        "level_min": 80,
        "level_max": 80,
        "npc_id": 1032001,
        "npc_name_zh": "艾爾·圖",
        "npc_name_en": "Ehll Tou",
        "location_zh": "天穹街",
        "zone_id": 3435,
        "x": 14.4,
        "y": 12.6,
    },
    {
        "level_min": 80,
        "level_max": 90,
        "npc_id": 1035211,
        "npc_name_zh": "狄蘭達爾伯爵",
        "npc_name_en": "Charlemend",
        "location_zh": "天穹街",
        "zone_id": 3435,
        "x": 9.4,
        "y": 8.7,
    },
    {
        "level_min": 80,
        "level_max": 90,
        "npc_id": 1040284,
        "npc_name_zh": "阿梅莉安絲",
        "npc_name_en": "Ameliance",
        "location_zh": "舊薩雷安",
        "zone_id": 3706,
        "x": 12.6,
        "y": 9.7,
    },
    {
        "level_min": 80,
        "level_max": 90,
        "npc_id": 1045407,
        "npc_name_zh": "瑪格拉特",
        "npc_name_en": "Margrat",
        "location_zh": "迷津",  # Labyrinthos
        "zone_id": 3709,
        "x": 20.4,
        "y": 20.1,
    },
    {
        "level_min": 90,
        "level_max": 100,
        "npc_id": 1044547,
        "npc_name_zh": "安登",
        "npc_name_en": "Anden",
        "location_zh": "伊爾美格",
        "zone_id": 2956,
        "x": 17.0,
        "y": 34.0,
    },
    {
        "level_min": 90,
        "level_max": 100,
        "npc_id": 1046985,
        "npc_name_zh": "尼托維凱",
        "npc_name_en": "Nitowikwe",
        "location_zh": "夏勞尼荒野",
        "zone_id": 4508,
        "x": 14.3,
        "y": 19.3,
    },
]

# 收藏品交易員 (Collectable Appraiser) 位置
# 可隨時交納收藏品換取工票
# 資料來源：Teamcraft + FFXIV Wiki
# 注意：順序很重要，特定等級的放前面，通用的放後面
COLLECTABLE_APPRAISERS = [
    # === Lv 50-60 ===
    {
        "level_min": 50,
        "level_max": 60,
        "npc_id": 1012300,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "田園郡",
        "zone_id": 2082,
        "x": 5.8,
        "y": 7.0,
    },
    {
        "level_min": 50,
        "level_max": 60,
        "npc_id": 1013396,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "摩杜納",
        "zone_id": 67,
        "x": 22.5,
        "y": 6.7,
    },
    # === Lv 61-70 ===
    {
        "level_min": 61,
        "level_max": 70,
        "npc_id": 1019457,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "神拳痕",
        "zone_id": 2403,
        "x": 9.9,
        "y": 12.6,
    },
    {
        "level_min": 61,
        "level_max": 70,
        "npc_id": 1025971,
        "npc_name_zh": "薩娜娜",
        "npc_name_en": "Sanana",
        "location_zh": "黃金港",
        "zone_id": 2404,
        "x": 12.0,
        "y": 8.4,
    },
    # === Lv 71-80 ===
    {
        "level_min": 71,
        "level_max": 80,
        "npc_id": 1027542,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "遊末邦",
        "zone_id": 2952,
        "x": 11.7,
        "y": 10.8,
    },
    {
        "level_min": 71,
        "level_max": 80,
        "npc_id": 1031501,
        "npc_name_zh": "工票交易員",
        "npc_name_en": "Scrip Exchange",
        "location_zh": "水晶都",
        "zone_id": 2951,
        "x": 9.8,
        "y": 8.5,
    },
    # === Lv 81-90 ===
    {
        "level_min": 81,
        "level_max": 90,
        "npc_id": 1037262,
        "npc_name_zh": "工票交易員",
        "npc_name_en": "Scrip Exchange",
        "location_zh": "舊薩雷安",
        "zone_id": 3706,
        "x": 5.0,
        "y": 9.4,
    },
    {
        "level_min": 81,
        "level_max": 90,
        "npc_id": 1037306,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "拉札罕",
        "zone_id": 3707,
        "x": 11.7,
        "y": 9.9,
    },
    # === Lv 91-100 ===
    {
        "level_min": 91,
        "level_max": 100,
        "npc_id": 1048386,
        "npc_name_zh": "工票交易員",
        "npc_name_en": "Scrip Exchange",
        "location_zh": "圖萊尤拉",
        "zone_id": 4504,
        "x": 16.3,
        "y": 11.2,
    },
    {
        "level_min": 91,
        "level_max": 100,
        "npc_id": 1049084,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "九號解決方案",
        "zone_id": 4503,
        "x": 9.1,
        "y": 13.5,
    },
    # === 三大主城（全等級通用，放最後作為備用）===
    {
        "level_min": 1,
        "level_max": 100,
        "npc_id": 1003632,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "利姆薩·羅敏薩下層甲板",
        "zone_id": 29,
        "x": 6.1,
        "y": 12.0,
    },
    {
        "level_min": 1,
        "level_max": 100,
        "npc_id": 1001616,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "烏爾達哈來生回廊",
        "zone_id": 41,
        "x": 14.3,
        "y": 10.9,
    },
    {
        "level_min": 1,
        "level_max": 100,
        "npc_id": 1003076,
        "npc_name_zh": "收藏品交易員",
        "npc_name_en": "Collectable Appraiser",
        "location_zh": "格里達尼亞舊街",
        "zone_id": 53,
        "x": 14.2,
        "y": 9.1,
    },
]


def get_eorzea_time() -> tuple[int, int]:
    """取得當前艾歐澤亞時間.

    Returns:
        (hours, minutes) - 當前 ET 的小時和分鐘
    """
    unix_time = time.time()
    eorzea_time = unix_time * EORZEA_MULTIPLIER

    hours = int((eorzea_time / 3600) % 24)
    minutes = int((eorzea_time / 60) % 60)

    return hours, minutes


def get_eorzea_time_str() -> str:
    """取得格式化的 ET 時間字串."""
    hours, minutes = get_eorzea_time()
    return f"{hours:02d}:{minutes:02d}"


def _ensure_data_dir():
    """確保資料目錄存在."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _is_cache_valid(filepath: Path) -> bool:
    """檢查快取是否有效."""
    if not filepath.exists():
        return False
    mtime = filepath.stat().st_mtime
    return (time.time() - mtime) < CACHE_EXPIRY


def _download_json(url: str, cache_name: str) -> dict:
    """下載 JSON 資料並快取.

    Args:
        url: 資料 URL
        cache_name: 快取檔案名稱

    Returns:
        JSON 資料字典
    """
    _ensure_data_dir()
    cache_path = DATA_DIR / cache_name

    # 檢查快取
    if _is_cache_valid(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # 快取損壞，重新下載

    # 下載資料
    try:
        print(f"下載資料: {cache_name}...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 儲存快取
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return data
    except requests.RequestException as e:
        print(f"下載失敗 {cache_name}: {e}")
        # 嘗試使用過期的快取
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}


def load_nodes_data() -> dict:
    """載入採集節點資料."""
    global _nodes_cache
    if not _nodes_cache:
        _nodes_cache = _download_json(
            f"{TEAMCRAFT_BASE}/nodes.json",
            "nodes.json"
        )
    return _nodes_cache


def load_collectables_data() -> dict:
    """載入收藏品資料."""
    global _collectables_cache
    if not _collectables_cache:
        _collectables_cache = _download_json(
            f"{TEAMCRAFT_BASE}/collectables.json",
            "collectables.json"
        )
    return _collectables_cache


def load_items_zh() -> dict:
    """載入中文物品名稱."""
    global _items_zh_cache
    if not _items_zh_cache:
        _items_zh_cache = _download_json(
            f"{TEAMCRAFT_BASE}/zh/zh-items.json",
            "zh-items.json"
        )
    return _items_zh_cache


def load_places_zh() -> dict:
    """載入中文地點名稱."""
    global _places_zh_cache
    if not _places_zh_cache:
        _places_zh_cache = _download_json(
            f"{TEAMCRAFT_BASE}/zh/zh-places.json",
            "zh-places.json"
        )
    return _places_zh_cache


def load_gathering_items() -> dict:
    """載入採集物品資料（建立 itemId -> data 的映射）."""
    global _gathering_items_cache
    if not _gathering_items_cache:
        raw_data = _download_json(
            f"{TEAMCRAFT_BASE}/gathering-items.json",
            "gathering-items.json"
        )
        # 建立 itemId -> data 的映射
        _gathering_items_cache = {}
        for entry in raw_data.values():
            item_id = entry.get("itemId")
            if item_id:
                _gathering_items_cache[item_id] = entry
    return _gathering_items_cache


def load_fishing_sources() -> dict:
    """載入釣魚來源資料."""
    global _fishing_sources_cache
    if not _fishing_sources_cache:
        _fishing_sources_cache = _download_json(
            f"{TEAMCRAFT_BASE}/fishing-sources.json",
            "fishing-sources.json"
        )
    return _fishing_sources_cache


def load_fishing_spots() -> dict:
    """載入釣魚點資料."""
    global _fishing_spots_cache
    if not _fishing_spots_cache:
        _fishing_spots_cache = _download_json(
            f"{TEAMCRAFT_BASE}/fishing-spots.json",
            "fishing-spots.json"
        )
    return _fishing_spots_cache


def get_item_name_zh(item_id: int) -> str:
    """取得物品的繁體中文名稱."""
    items = load_items_zh()
    item_data = items.get(str(item_id))
    if item_data:
        # zh-items.json 的值是 {"zh": "物品名稱"} 格式
        if isinstance(item_data, dict):
            name = item_data.get("zh", f"物品 {item_id}")
        else:
            name = str(item_data)
    else:
        name = f"物品 {item_id}"
    # 轉換為繁體
    return _s2t_converter.convert(name)


def get_place_name_zh(place_id: int) -> str:
    """取得地點的繁體中文名稱."""
    places = load_places_zh()
    place_data = places.get(str(place_id))
    if place_data:
        # zh-places.json 的值是 {"zh": "地點名稱"} 格式
        if isinstance(place_data, dict):
            name = place_data.get("zh", f"地點 {place_id}")
        else:
            name = str(place_data)
    else:
        name = f"地點 {place_id}"
    return _s2t_converter.convert(name)


def get_collectable_scrip_reward(item_id: int) -> dict:
    """取得收藏品的工票獎勵.

    Args:
        item_id: 物品 ID

    Returns:
        {"white": int, "purple": int} 或空字典
    """
    collectables = load_collectables_data()

    # collectables.json 的 key 就是 item ID
    coll_data = collectables.get(str(item_id))
    if not coll_data:
        return {"white": 0, "purple": 0}

    # 取得高品質的工票獎勵
    high_reward = coll_data.get("high", {})
    scrip = high_reward.get("scrip", 0)

    # 根據 reward ID 判斷是白票還是紫票
    reward_id = coll_data.get("reward", 0)

    # 白色工票 reward ID: 25199 (Lv 50-80), 33913 (Lv 81-90)
    # 紫色工票 reward ID: 33914 (Lv 81-90), 41784 (7.0 紫票)
    if reward_id in [25199, 33913]:
        return {"white": scrip, "purple": 0}
    elif reward_id in [33914, 41784]:
        return {"white": 0, "purple": scrip}
    else:
        # 假設是白票
        return {"white": scrip, "purple": 0}


def get_timed_collectables() -> list[dict]:
    """取得所有有時間限制的收藏品節點.

    Returns:
        收藏品列表，每個包含：
        - item_id: 物品 ID
        - item_name: 繁中名稱
        - job: 職業
        - level: 採集等級
        - location: 採集地點
        - x, y: 座標
        - spawn_times: ET 出現時間列表
        - duration: 持續時間（ET 分鐘）
        - scrip_reward: 工票獎勵
    """
    nodes = load_nodes_data()
    collectables = load_collectables_data()
    gathering_items = load_gathering_items()

    # 建立收藏品物品 ID 集合（collectables.json 的 key 就是 item ID）
    collectable_item_ids = set(int(k) for k in collectables.keys())

    results = []

    # === 採礦工和園藝工的收藏品 ===
    for node_id, node_data in nodes.items():
        # 只處理有時間限制的節點
        spawns = node_data.get("spawns")
        if not spawns:
            continue

        # 檢查節點類型
        node_type = node_data.get("type", 0)
        job = NODE_TYPE_TO_JOB.get(node_type, "未知")

        # 取得節點物品
        items = node_data.get("items", [])
        for item_id in items:
            # 只處理收藏品
            if item_id not in collectable_item_ids:
                continue

            # 取得採集等級（gathering_items 已經用 itemId 為 key）
            gathering_item = gathering_items.get(item_id, {})
            level = gathering_item.get("level", 0)

            # 取得地點名稱
            zone_id = node_data.get("zoneid", 0)
            location = get_place_name_zh(zone_id)

            # 取得座標
            x = node_data.get("x", 0)
            y = node_data.get("y", 0)

            # 取得工票獎勵
            scrip_reward = get_collectable_scrip_reward(item_id)

            results.append({
                "item_id": item_id,
                "item_name": get_item_name_zh(item_id),
                "job": job,
                "level": level,
                "location": location,
                "x": x,
                "y": y,
                "spawn_times": spawns,
                "duration": node_data.get("duration", 120),  # 預設 2 ET 小時
                "scrip_reward": scrip_reward,
            })

    # === 捕魚人的收藏品 ===
    fishing_sources = load_fishing_sources()
    fishing_spots = load_fishing_spots()

    # 建立釣魚點 ID -> 資料的映射
    spots_map = {}
    for spot in fishing_spots:
        spots_map[spot.get("id")] = spot

    for fish_id_str, sources in fishing_sources.items():
        fish_id = int(fish_id_str)

        # 只處理收藏品
        if fish_id not in collectable_item_ids:
            continue

        # 找有時間限制的來源
        for src in sources:
            spawn = src.get("spawn")
            duration = src.get("duration")
            if spawn is None:
                continue

            # 取得釣魚點資訊
            spot_id = src.get("spot")
            spot_data = spots_map.get(spot_id, {})

            # 取得地點名稱
            zone_id = spot_data.get("zoneId", 0)
            location = get_place_name_zh(zone_id)

            # 取得座標
            coords = spot_data.get("coords", {})
            x = coords.get("x", 0) if isinstance(coords, dict) else 0
            y = coords.get("y", 0) if isinstance(coords, dict) else 0

            # 取得等級
            level = spot_data.get("level", 0)

            # 取得工票獎勵
            scrip_reward = get_collectable_scrip_reward(fish_id)

            # duration 是 ET 小時，轉換為 ET 分鐘
            duration_minutes = int(duration * 60) if duration else 120

            results.append({
                "item_id": fish_id,
                "item_name": get_item_name_zh(fish_id),
                "job": "捕魚人",
                "level": level,
                "location": location,
                "x": x,
                "y": y,
                "spawn_times": [spawn],  # 釣魚只有一個出現時間
                "duration": duration_minutes,
                "scrip_reward": scrip_reward,
            })

            # 每種魚只加一次（用第一個有時間限制的來源）
            break

    # 按等級排序
    results.sort(key=lambda x: x["level"], reverse=True)

    return results


def calculate_time_until_spawn(spawn_hour: int) -> int:
    """計算距離下次出現還有多少 ET 分鐘.

    Args:
        spawn_hour: 出現的 ET 小時

    Returns:
        距離下次出現的 ET 分鐘數
    """
    current_hour, current_minute = get_eorzea_time()
    current_total_minutes = current_hour * 60 + current_minute
    spawn_total_minutes = spawn_hour * 60

    if spawn_total_minutes > current_total_minutes:
        return spawn_total_minutes - current_total_minutes
    else:
        # 需要等到下一個 ET 週期
        return (24 * 60 - current_total_minutes) + spawn_total_minutes


def calculate_time_remaining(spawn_hour: int, duration: int) -> int:
    """計算還剩多少 ET 分鐘可採集.

    Args:
        spawn_hour: 出現的 ET 小時
        duration: 持續時間（ET 分鐘）

    Returns:
        剩餘的 ET 分鐘數，如果不在採集時間內返回 -1
    """
    current_hour, current_minute = get_eorzea_time()
    current_total_minutes = current_hour * 60 + current_minute
    spawn_total_minutes = spawn_hour * 60
    end_total_minutes = spawn_total_minutes + duration

    # 檢查是否在採集時間內
    if spawn_total_minutes <= current_total_minutes < end_total_minutes:
        return end_total_minutes - current_total_minutes

    # 處理跨日的情況
    if end_total_minutes > 24 * 60:
        end_total_minutes -= 24 * 60
        if current_total_minutes < end_total_minutes:
            return end_total_minutes - current_total_minutes
        elif current_total_minutes >= spawn_total_minutes:
            return (24 * 60 - current_total_minutes) + end_total_minutes

    return -1


def is_currently_available(spawn_times: list[int], duration: int) -> tuple[bool, int]:
    """檢查收藏品是否目前可採集.

    Args:
        spawn_times: 出現時間列表
        duration: 持續時間

    Returns:
        (是否可採集, 剩餘時間或下次出現時間)
    """
    for spawn_hour in spawn_times:
        remaining = calculate_time_remaining(spawn_hour, duration)
        if remaining > 0:
            return True, remaining

    # 計算最近的出現時間
    min_time_until = float('inf')
    for spawn_hour in spawn_times:
        time_until = calculate_time_until_spawn(spawn_hour)
        min_time_until = min(min_time_until, time_until)

    return False, int(min_time_until)


def et_to_real_seconds(et_minutes: int) -> int:
    """將 ET 分鐘轉換為現實秒數.

    1 ET 分鐘 = 現實 175/60 秒 ≈ 2.917 秒
    """
    return int(et_minutes * 175 / 60)


def format_real_duration(et_minutes: int) -> str:
    """將 ET 分鐘格式化為現實時間."""
    real_seconds = et_to_real_seconds(et_minutes)
    real_minutes = real_seconds // 60
    remaining_seconds = real_seconds % 60

    if real_minutes >= 60:
        hours = real_minutes // 60
        mins = real_minutes % 60
        if mins > 0:
            return f"{hours}時{mins}分"
        return f"{hours}時"
    elif real_minutes > 0:
        return f"{real_minutes}分{remaining_seconds}秒"
    else:
        return f"{remaining_seconds}秒"


def get_current_collectables(job_filter: str = None) -> tuple[list, list]:
    """取得目前可採集和即將出現的收藏品.

    Args:
        job_filter: 職業篩選（"採礦工"、"園藝工"、"捕魚人" 或 None）

    Returns:
        (目前可採集列表, 即將出現列表)
    """
    all_collectables = get_timed_collectables()

    available = []
    upcoming = []

    for coll in all_collectables:
        # 職業篩選
        if job_filter and coll["job"] != job_filter:
            continue

        is_available, time_value = is_currently_available(
            coll["spawn_times"],
            coll["duration"]
        )

        # 複製資料並加入時間資訊
        item_data = coll.copy()
        item_data["time_value"] = time_value

        if is_available:
            item_data["remaining_time"] = format_real_duration(time_value)
            available.append(item_data)
        else:
            item_data["spawn_in"] = format_real_duration(time_value)
            upcoming.append(item_data)

    # 排序：可採集的按剩餘時間，即將出現的按等待時間
    available.sort(key=lambda x: x["time_value"])
    upcoming.sort(key=lambda x: x["time_value"])

    return available, upcoming


def format_collectables_table(collectables: list, is_available: bool, show_appraiser: bool = True) -> list:
    """格式化收藏品資料為表格.

    Args:
        collectables: 收藏品列表
        is_available: 是否是目前可採集
        show_appraiser: 是否顯示老主顧欄位

    Returns:
        表格資料列表
    """
    rows = []
    for coll in collectables:
        # 工票顯示
        scrip = coll.get("scrip_reward", {})
        white = scrip.get("white", 0)
        purple = scrip.get("purple", 0)
        if purple > 0:
            scrip_str = f"紫票 {purple}"
        elif white > 0:
            scrip_str = f"白票 {white}"
        else:
            scrip_str = "-"

        # 時間顯示
        if is_available:
            time_str = coll.get("remaining_time", "-")
        else:
            time_str = coll.get("spawn_in", "-")

        # 座標
        x = coll.get("x", 0)
        y = coll.get("y", 0)
        coord_str = f"({x:.1f}, {y:.1f})" if x and y else "-"

        # 出現時間列表
        spawn_times = coll.get("spawn_times", [])
        spawn_str = ", ".join(f"{h:02d}:00" for h in spawn_times)

        # 老主顧資訊
        level = coll.get("level", 0)
        appraiser_str = format_appraiser_info(level) if show_appraiser else ""

        row = [
            coll.get("item_name", ""),
            coll.get("job", ""),
            coll.get("level", 0),
            coll.get("location", ""),
            coord_str,
            spawn_str,
            time_str,
            scrip_str,
        ]

        if show_appraiser:
            row.append(appraiser_str)

        rows.append(row)

    return rows


def refresh_collectables_data():
    """強制刷新收藏品資料（清除快取）."""
    global _nodes_cache, _collectables_cache, _items_zh_cache, _places_zh_cache, _gathering_items_cache, _fishing_sources_cache, _fishing_spots_cache

    # 清除記憶體快取
    _nodes_cache = {}
    _collectables_cache = {}
    _items_zh_cache = {}
    _places_zh_cache = {}
    _gathering_items_cache = {}
    _fishing_sources_cache = {}
    _fishing_spots_cache = {}

    # 刪除檔案快取
    cache_files = ["nodes.json", "collectables.json", "zh-items.json", "zh-places.json", "gathering-items.json", "fishing-sources.json", "fishing-spots.json"]
    for filename in cache_files:
        cache_path = DATA_DIR / filename
        if cache_path.exists():
            cache_path.unlink()

    # 重新載入
    load_nodes_data()
    load_collectables_data()
    load_items_zh()
    load_places_zh()
    load_gathering_items()


def get_custom_delivery_for_level(level: int) -> list[dict]:
    """取得對應等級的老主顧 NPC 資訊.

    Args:
        level: 收藏品等級

    Returns:
        老主顧資訊列表（可能有多個）
    """
    npcs = []
    for npc in CUSTOM_DELIVERY_NPCS:
        if npc["level_min"] <= level <= npc["level_max"]:
            npcs.append(npc)
    return npcs


def format_appraiser_info(level: int) -> str:
    """格式化收藏品交易員資訊為字串.

    Args:
        level: 收藏品等級

    Returns:
        格式化的收藏品交易員資訊
    """
    # 使用收藏品交易員 (Collectable Appraiser) NPC
    appraisers = get_appraiser_for_level(level)
    if not appraisers:
        return "-"

    # 使用繁體中文名稱，取第一個符合等級的
    appraiser = appraisers[0]
    name = _s2t_converter.convert(appraiser["npc_name_zh"])
    location = _s2t_converter.convert(appraiser["location_zh"])

    return f"{name} @ {location}"


def get_appraiser_for_level(level: int) -> list[dict]:
    """取得對應等級的收藏品交易員資訊.

    Args:
        level: 收藏品等級

    Returns:
        收藏品交易員資訊列表
    """
    appraisers = []
    for appraiser in COLLECTABLE_APPRAISERS:
        if appraiser["level_min"] <= level <= appraiser["level_max"]:
            appraisers.append(appraiser)
    return appraisers


def get_all_appraisers() -> list[dict]:
    """取得所有老主顧 NPC 的資訊.

    Returns:
        所有老主顧的資訊列表
    """
    result = []
    for appraiser in COLLECTABLE_APPRAISERS:
        result.append({
            "level_range": f"Lv {appraiser['level_min']}-{appraiser['level_max']}",
            "npc_name": _s2t_converter.convert(appraiser["npc_name_zh"]),
            "location": _s2t_converter.convert(appraiser["location_zh"]),
            "coords": f"({appraiser['x']:.1f}, {appraiser['y']:.1f})",
        })
    return result


def format_appraisers_table() -> list:
    """格式化收藏品交易員資訊為表格.

    Returns:
        表格資料列表
    """
    rows = []
    for appraiser in get_all_appraisers():
        rows.append([
            appraiser["level_range"],
            appraiser["npc_name"],
            appraiser["location"],
            appraiser["coords"],
        ])
    return rows


def get_all_custom_delivery_npcs() -> list[dict]:
    """取得所有老主顧 NPC 的資訊.

    Returns:
        所有老主顧的資訊列表
    """
    result = []
    for npc in CUSTOM_DELIVERY_NPCS:
        result.append({
            "level_range": f"Lv {npc['level_min']}-{npc['level_max']}",
            "npc_name": _s2t_converter.convert(npc["npc_name_zh"]),
            "location": _s2t_converter.convert(npc["location_zh"]),
            "coords": f"({npc['x']:.1f}, {npc['y']:.1f})",
        })
    return result


def format_custom_delivery_table() -> list:
    """格式化老主顧 NPC 資訊為表格.

    Returns:
        表格資料列表
    """
    rows = []
    for npc in get_all_custom_delivery_npcs():
        rows.append([
            npc["level_range"],
            npc["npc_name"],
            npc["location"],
            npc["coords"],
        ])
    return rows
