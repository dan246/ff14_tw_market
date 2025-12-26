"""監看清單管理（使用瀏覽器 LocalStorage）."""

from datetime import datetime
from typing import Tuple

import pandas as pd

from .api import get_item_info, get_market_data
from .config import DATA_CENTER


def get_watchlist_with_alerts(watchlist: list) -> Tuple[pd.DataFrame, list]:
    """取得監看清單及當前價格，並回傳達標提示.

    Args:
        watchlist: 監看清單列表（從 BrowserState 傳入）

    Returns:
        (監看清單 DataFrame, 達標物品列表)
    """
    if not watchlist:
        return pd.DataFrame({"訊息": ["清單為空，請先新增物品"]}), []

    data = []
    alerts = []

    for item in watchlist:
        market_data = get_market_data(item["id"], DATA_CENTER)
        min_price = market_data.get("minPrice", 0) if market_data else 0
        target = item.get("target_price", 0)

        status = ""
        if target > 0 and min_price > 0:
            if min_price <= target:
                status = "✓ 達標"
                alerts.append(f"{item['name']} 已達標！目前 {min_price:,} Gil")
            else:
                status = f"還差 {min_price - target:,}"

        data.append({
            "物品 ID": item["id"],
            "物品名稱": item["name"],
            "目標價格": f"{target:,}" if target > 0 else "-",
            "當前最低價": f"{min_price:,}" if min_price > 0 else "無資料",
            "狀態": status,
        })

    return pd.DataFrame(data), alerts


def add_item_to_list(
    item_selection: int,
    target_price: float,
    watchlist: list,
) -> Tuple[str, pd.DataFrame, list]:
    """新增物品到清單.

    Args:
        item_selection: 選擇的物品 ID
        target_price: 目標價格
        watchlist: 目前的監看清單

    Returns:
        (訊息, 更新後的清單 DataFrame, 更新後的 watchlist)
    """
    if watchlist is None:
        watchlist = []

    if not item_selection:
        df, _ = get_watchlist_with_alerts(watchlist)
        return "請先選擇物品", df, watchlist

    item_id = item_selection

    # 檢查是否已存在
    if any(item["id"] == item_id for item in watchlist):
        df, _ = get_watchlist_with_alerts(watchlist)
        return "物品已在清單中", df, watchlist

    item_info = get_item_info(item_id)
    item_name = item_info.get("Name", f"物品 {item_id}")

    watchlist.append({
        "id": item_id,
        "name": item_name,
        "target_price": int(target_price) if target_price else 0,
        "added_time": datetime.now().isoformat(),
    })

    df, _ = get_watchlist_with_alerts(watchlist)
    return f"已新增 {item_name}", df, watchlist


def remove_item_from_list(
    item_id: float,
    watchlist: list,
) -> Tuple[str, pd.DataFrame, list]:
    """從清單移除物品.

    Args:
        item_id: 物品 ID
        watchlist: 目前的監看清單

    Returns:
        (訊息, 更新後的清單 DataFrame, 更新後的 watchlist)
    """
    if watchlist is None:
        watchlist = []

    if not item_id:
        df, _ = get_watchlist_with_alerts(watchlist)
        return "請輸入物品 ID", df, watchlist

    watchlist = [item for item in watchlist if item["id"] != int(item_id)]

    df, _ = get_watchlist_with_alerts(watchlist)
    return "已移除", df, watchlist
