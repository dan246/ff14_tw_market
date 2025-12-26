"""工具函數."""

from datetime import datetime

import pandas as pd

from .config import WORLDS


def format_price(price: int) -> str:
    """格式化價格顯示.

    Args:
        price: 價格數值

    Returns:
        格式化後的價格字串
    """
    if price >= 1_000_000:
        return f"{price / 1_000_000:.2f}M"
    if price >= 1_000:
        return f"{price / 1_000:.1f}K"
    return str(price)


def format_timestamp(timestamp: int) -> str:
    """格式化時間戳.

    Args:
        timestamp: Unix 時間戳（秒或毫秒）

    Returns:
        格式化後的時間字串
    """
    if not timestamp:
        return "N/A"

    # 如果 timestamp 超過合理範圍，可能是毫秒，需要轉換為秒
    if timestamp > 9999999999:
        timestamp = timestamp // 1000

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M")


def format_relative_time(timestamp: int) -> str:
    """格式化相對時間.

    Args:
        timestamp: Unix 時間戳（秒或毫秒）

    Returns:
        相對時間字串（如「3 小時前」）
    """
    if not timestamp:
        return "N/A"

    # 如果 timestamp 超過合理範圍，可能是毫秒，需要轉換為秒
    if timestamp > 9999999999:
        timestamp = timestamp // 1000

    now = datetime.now()
    dt = datetime.fromtimestamp(timestamp)
    diff = now - dt

    if diff.days > 0:
        return f"{diff.days} 天前"
    if diff.seconds >= 3600:
        return f"{diff.seconds // 3600} 小時前"
    if diff.seconds >= 60:
        return f"{diff.seconds // 60} 分鐘前"
    return "剛剛"


def process_listings(listings: list, quality: str = "all") -> pd.DataFrame:
    """處理上架列表.

    Args:
        listings: 上架資料列表
        quality: 品質篩選（"all", "nq", "hq"）

    Returns:
        處理後的 DataFrame
    """
    if not listings:
        return pd.DataFrame()

    data = []
    for listing in listings:
        if quality == "hq" and not listing.get("hq"):
            continue
        if quality == "nq" and listing.get("hq"):
            continue

        world_id = listing.get("worldID")
        world_name = WORLDS.get(world_id, str(world_id))

        data.append({
            "品質": "HQ" if listing.get("hq") else "NQ",
            "單價": listing.get("pricePerUnit", 0),
            "數量": listing.get("quantity", 0),
            "總價": listing.get("total", 0),
            "雇員": listing.get("retainerName", ""),
            "伺服器": world_name,
            "更新時間": format_relative_time(listing.get("lastReviewTime", 0)),
        })

    return pd.DataFrame(data)


def process_history(entries: list, quality: str = "all") -> pd.DataFrame:
    """處理交易歷史.

    Args:
        entries: 交易記錄列表
        quality: 品質篩選（"all", "nq", "hq"）

    Returns:
        處理後的 DataFrame
    """
    if not entries:
        return pd.DataFrame()

    data = []
    for entry in entries:
        if quality == "hq" and not entry.get("hq"):
            continue
        if quality == "nq" and entry.get("hq"):
            continue

        world_id = entry.get("worldID")
        world_name = WORLDS.get(world_id, str(world_id))

        data.append({
            "品質": "HQ" if entry.get("hq") else "NQ",
            "單價": entry.get("pricePerUnit", 0),
            "數量": entry.get("quantity", 0),
            "總價": entry.get("total", 0),
            "買家": entry.get("buyerName", ""),
            "伺服器": world_name,
            "成交時間": format_timestamp(entry.get("timestamp", 0)),
        })

    return pd.DataFrame(data)
