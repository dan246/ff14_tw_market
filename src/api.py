"""Universalis 和 XIVAPI 的 API 呼叫函數."""

import re

import requests
from opencc import OpenCC

# 繁體轉簡體轉換器（用於搜尋）
_t2s_converter = OpenCC('t2s')
# 簡體轉繁體轉換器（用於顯示結果）
_s2t_converter = OpenCC('s2t')

from .config import (
    API_TIMEOUT,
    CAFEMAKER_BASE,
    DATA_CENTER,
    MARKET_API_TIMEOUT,
    POPULAR_ITEMS,
    UNIVERSALIS_BASE,
    WORLD_IDS,
    XIVAPI_BASE,
)


def _extract_item_id(query: str) -> int:
    """從查詢字串中提取物品 ID.

    支援格式：
    - 純數字: "5506"
    - Universalis 網址: "https://universalis.app/market/5506"
    """
    # 檢查是否為純數字
    if query.isdigit():
        return int(query)

    # 檢查是否為 Universalis 網址
    match = re.search(r"universalis\.app/market/(\d+)", query)
    if match:
        return int(match.group(1))

    return 0


def search_items(query: str, limit: int = 20) -> list:
    """搜尋物品 - 支援繁體中文、簡體中文、英文.

    Args:
        query: 搜尋關鍵字、物品 ID 或 Universalis 網址
        limit: 結果數量限制

    Returns:
        物品列表，每個物品包含 id, name, icon, level
    """
    if not query:
        return []

    query = query.strip()
    results = []

    # 1. 檢查是否為物品 ID 或 Universalis 網址
    item_id = _extract_item_id(query)
    if item_id > 0:
        item_info = get_item_info(item_id)
        if item_info and item_info.get("Name"):
            results.append({
                "id": item_id,
                "name": item_info.get("Name", f"物品 {item_id}"),
                "icon": "",
                "level": item_info.get("LevelItem", 0),
            })
            return results

    # 2. 將繁體中文轉換為簡體中文（Cafemaker 使用簡體）
    query_simplified = _t2s_converter.convert(query)

    # 3. 使用 Cafemaker 搜尋（支援中文）
    try:
        url = f"{CAFEMAKER_BASE}/search"
        params = {
            "string": query_simplified,
            "indexes": "Item",
            "limit": limit,
        }
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            for item in data.get("Results", []):
                if not any(r["id"] == item.get("ID") for r in results):
                    # 將簡體中文名稱轉換為繁體中文
                    name_traditional = _s2t_converter.convert(item.get("Name", ""))
                    results.append({
                        "id": item.get("ID"),
                        "name": name_traditional,
                        "icon": "",
                        "level": item.get("LevelItem", 0),
                    })
    except requests.RequestException as e:
        print(f"Cafemaker 搜尋錯誤: {e}")

    return results[:limit]


def get_item_info(item_id: int) -> dict:
    """取得物品詳細資訊 - 嘗試多個來源.

    Args:
        item_id: 物品 ID

    Returns:
        物品資訊字典
    """
    # 嘗試 XIVAPI
    try:
        url = f"{XIVAPI_BASE}/item/{item_id}"
        params = {"language": "en"}
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print(f"XIVAPI 取得物品資訊錯誤: {e}")

    # 備用：嘗試 Cafemaker
    try:
        url = f"{CAFEMAKER_BASE}/item/{item_id}"
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print(f"Cafemaker 取得物品資訊錯誤: {e}")

    # 如果都失敗，返回基本資訊
    return {"ID": item_id, "Name": f"Item {item_id}", "LevelItem": 0}


def get_market_data(item_id: int, world_or_dc: str = None) -> dict:
    """取得市場板數據.

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心名稱

    Returns:
        市場數據字典
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    try:
        url = f"{UNIVERSALIS_BASE}/{world_or_dc}/{item_id}"
        params = {
            "listings": 50,
            "entries": 50,
        }
        response = requests.get(url, params=params, timeout=MARKET_API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"取得市場數據錯誤: {e}")
        return {}


def get_tax_rates(world: str) -> dict:
    """取得稅率資訊.

    Args:
        world: 伺服器名稱

    Returns:
        稅率字典
    """
    try:
        world_id = WORLD_IDS.get(world)
        if not world_id:
            return {}
        url = f"{UNIVERSALIS_BASE}/tax-rates"
        params = {"world": world_id}
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"取得稅率錯誤: {e}")
        return {}


def get_upload_stats() -> dict:
    """取得上傳統計.

    Returns:
        上傳統計字典
    """
    try:
        url = f"{UNIVERSALIS_BASE}/extra/stats/world-upload-counts"
        response = requests.get(url, timeout=API_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"取得上傳統計錯誤: {e}")
        return {}
