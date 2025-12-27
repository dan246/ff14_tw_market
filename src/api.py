"""Universalis 和 XIVAPI 的 API 呼叫函數."""

import asyncio
import re
from typing import Optional

import aiohttp
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
    """取得物品詳細資訊 - 優先使用 Cafemaker（支援中文）.

    Args:
        item_id: 物品 ID

    Returns:
        物品資訊字典（名稱已轉換為繁體中文）
    """
    # 優先使用 Cafemaker（支援中文）
    try:
        url = f"{CAFEMAKER_BASE}/item/{item_id}"
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            # 將簡體名稱轉換為繁體
            if data.get("Name"):
                data["Name"] = _s2t_converter.convert(data["Name"])
            return data
    except requests.RequestException as e:
        print(f"Cafemaker 取得物品資訊錯誤: {e}")

    # 備用：嘗試 XIVAPI
    try:
        url = f"{XIVAPI_BASE}/item/{item_id}"
        params = {"language": "en"}
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print(f"XIVAPI 取得物品資訊錯誤: {e}")

    # 如果都失敗，返回基本資訊
    return {"ID": item_id, "Name": f"物品 {item_id}", "LevelItem": 0}


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


def get_recently_updated(world_or_dc: str = None, limit: int = 20) -> list:
    """取得最近更新的物品列表.

    Args:
        world_or_dc: 伺服器或資料中心名稱
        limit: 結果數量限制

    Returns:
        最近更新的物品 ID 列表
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    # 如果是伺服器名稱，轉換為 world ID
    world_id = WORLD_IDS.get(world_or_dc, world_or_dc)

    try:
        url = f"{UNIVERSALIS_BASE}/extra/stats/recently-updated"
        params = {"world": world_id} if isinstance(world_id, int) else {"dcName": world_or_dc}
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])[:limit]
    except requests.RequestException as e:
        print(f"取得最近更新錯誤: {e}")
        return []


def get_recent_activity(world_or_dc: str = None, limit: int = 15) -> list:
    """取得市場動態（最近更新的物品及其價格資訊）.

    Args:
        world_or_dc: 伺服器或資料中心名稱
        limit: 結果數量限制

    Returns:
        市場動態列表，包含物品名稱、最低價等資訊
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    item_ids = get_recently_updated(world_or_dc, limit)
    if not item_ids:
        return []

    activity_list = []

    def fetch_item_data(item_id: int) -> dict:
        """取得單一物品的市場資料."""
        item_info = get_item_info(item_id)
        market_data = get_market_data(item_id, world_or_dc)

        if not market_data:
            return None

        listings = market_data.get("listings", [])
        nq_prices = [l["pricePerUnit"] for l in listings if not l.get("hq")]
        hq_prices = [l["pricePerUnit"] for l in listings if l.get("hq")]

        # 取得物品名稱並轉換為繁體
        name = item_info.get("Name", f"物品 {item_id}")
        name_traditional = _s2t_converter.convert(name)

        return {
            "id": item_id,
            "name": name_traditional,
            "nq_min": min(nq_prices) if nq_prices else None,
            "hq_min": min(hq_prices) if hq_prices else None,
            "listing_count": len(listings),
            "last_update": market_data.get("lastUploadTime", 0),
        }

    # 並行請求物品資料
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_item_data, item_id): item_id for item_id in item_ids}
        for future in as_completed(futures):
            result = future.result()
            if result:
                activity_list.append(result)

    # 按更新時間排序（最新的在前）
    activity_list.sort(key=lambda x: x["last_update"], reverse=True)

    return activity_list


# ============================================================
# 異步 API 函數 (使用 aiohttp，速度更快)
# ============================================================

async def get_market_data_async(
    item_id: int,
    world_or_dc: str = None,
    session: aiohttp.ClientSession = None,
) -> dict:
    """異步取得市場板數據.

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心名稱
        session: 可選的 aiohttp session

    Returns:
        市場數據字典
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    url = f"{UNIVERSALIS_BASE}/{world_or_dc}/{item_id}"
    params = {"listings": 50, "entries": 50}

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=MARKET_API_TIMEOUT)
        ) as response:
            if response.status == 200:
                return await response.json()
            return {}
    except Exception as e:
        print(f"異步取得市場數據錯誤: {e}")
        return {}
    finally:
        if close_session:
            await session.close()


async def get_item_info_async(
    item_id: int,
    session: aiohttp.ClientSession = None,
) -> dict:
    """異步取得物品詳細資訊.

    Args:
        item_id: 物品 ID
        session: 可選的 aiohttp session

    Returns:
        物品資訊字典
    """
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        url = f"{CAFEMAKER_BASE}/item/{item_id}"
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("Name"):
                    data["Name"] = _s2t_converter.convert(data["Name"])
                return data
    except Exception as e:
        print(f"異步取得物品資訊錯誤: {e}")

    # 備用：嘗試 XIVAPI
    try:
        url = f"{XIVAPI_BASE}/item/{item_id}"
        params = {"language": "en"}
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
        ) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        print(f"XIVAPI 異步取得物品資訊錯誤: {e}")
    finally:
        if close_session:
            await session.close()

    return {"ID": item_id, "Name": f"物品 {item_id}", "LevelItem": 0}


async def get_multi_item_market_data_async(
    item_ids: list[int],
    world_or_dc: str = None,
) -> dict:
    """異步批量取得多個物品的市場數據.

    Args:
        item_ids: 物品 ID 列表
        world_or_dc: 伺服器或資料中心名稱

    Returns:
        以物品 ID 為 key 的市場數據字典
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    if not item_ids:
        return {}

    # Universalis 支援批量查詢，最多 100 個物品
    ids_str = ",".join(str(i) for i in item_ids[:100])
    url = f"{UNIVERSALIS_BASE}/{world_or_dc}/{ids_str}"
    params = {"listings": 20, "entries": 20}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=MARKET_API_TIMEOUT)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # 如果是單個物品，包裝成 items 格式
                    if "items" not in data and "itemID" in data:
                        return {data["itemID"]: data}
                    return data.get("items", {})
    except Exception as e:
        print(f"批量取得市場數據錯誤: {e}")

    return {}


async def get_full_item_data_async(
    item_id: int,
    world_or_dc: str = None,
) -> dict:
    """異步取得物品的完整資料（物品資訊 + 市場數據）.

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心名稱

    Returns:
        包含 item_info 和 market_data 的字典
    """
    async with aiohttp.ClientSession() as session:
        # 並行請求物品資訊和市場數據
        item_info_task = get_item_info_async(item_id, session)
        market_data_task = get_market_data_async(item_id, world_or_dc, session)

        item_info, market_data = await asyncio.gather(
            item_info_task, market_data_task
        )

        return {
            "item_info": item_info,
            "market_data": market_data,
        }


def get_market_data_fast(item_id: int, world_or_dc: str = None) -> dict:
    """快速取得市場板數據（使用異步）.

    這是 get_market_data 的快速版本，適合在 Gradio 中使用。

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心名稱

    Returns:
        市場數據字典
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_market_data_async(item_id, world_or_dc))
        loop.close()
        return result
    except Exception as e:
        print(f"快速取得市場數據錯誤: {e}")
        # 回退到同步版本
        return get_market_data(item_id, world_or_dc)


def get_full_item_data_fast(item_id: int, world_or_dc: str = None) -> dict:
    """快速取得物品完整資料（使用異步並行請求）.

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心名稱

    Returns:
        包含 item_info 和 market_data 的字典
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(get_full_item_data_async(item_id, world_or_dc))
        loop.close()
        return result
    except Exception as e:
        print(f"快速取得完整資料錯誤: {e}")
        # 回退到同步版本
        return {
            "item_info": get_item_info(item_id),
            "market_data": get_market_data(item_id, world_or_dc),
        }
