"""監看清單管理."""

import json
from datetime import datetime

import pandas as pd

from .api import get_item_info, get_market_data
from .config import DATA_CENTER, WATCHLIST_FILE


def load_watchlist() -> list:
    """載入監看清單.

    Returns:
        監看清單列表
    """
    try:
        with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_watchlist(watchlist: list) -> None:
    """儲存監看清單.

    Args:
        watchlist: 監看清單列表
    """
    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)


def add_to_watchlist(
    item_id: int,
    item_name: str,
    target_price: int = 0,
) -> str:
    """新增物品到監看清單.

    Args:
        item_id: 物品 ID
        item_name: 物品名稱
        target_price: 目標價格

    Returns:
        操作結果訊息
    """
    watchlist = load_watchlist()

    # 檢查是否已存在
    if any(item["id"] == item_id for item in watchlist):
        return "物品已在清單中"

    watchlist.append({
        "id": item_id,
        "name": item_name,
        "target_price": target_price,
        "added_time": datetime.now().isoformat(),
    })
    save_watchlist(watchlist)
    return f"已新增 {item_name} 到監看清單"


def remove_from_watchlist(item_id: int) -> str:
    """從監看清單移除物品.

    Args:
        item_id: 物品 ID

    Returns:
        操作結果訊息
    """
    watchlist = load_watchlist()
    watchlist = [item for item in watchlist if item["id"] != item_id]
    save_watchlist(watchlist)
    return "已從清單移除"


def get_watchlist_with_alerts() -> tuple:
    """取得監看清單及當前價格，並回傳達標提示.

    Returns:
        (監看清單 DataFrame, 達標物品列表)
    """
    watchlist = load_watchlist()
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


def get_watchlist_dataframe() -> pd.DataFrame:
    """取得監看清單及當前價格.

    Returns:
        監看清單 DataFrame
    """
    df, _ = get_watchlist_with_alerts()
    return df


def add_item_to_list(
    item_selection: int,
    target_price: float,
) -> tuple[str, pd.DataFrame]:
    """新增物品到清單（Gradio 回調函數）.

    Args:
        item_selection: 選擇的物品 ID
        target_price: 目標價格

    Returns:
        (訊息, 更新後的清單 DataFrame)
    """
    if not item_selection:
        return "請先選擇物品", get_watchlist_dataframe()

    item_id = item_selection
    item_info = get_item_info(item_id)
    item_name = item_info.get("Name", f"物品 {item_id}")

    msg = add_to_watchlist(
        item_id,
        item_name,
        int(target_price) if target_price else 0,
    )
    return msg, get_watchlist_dataframe()


def remove_item_from_list(item_id: float) -> tuple[str, pd.DataFrame]:
    """從清單移除物品（Gradio 回調函數）.

    Args:
        item_id: 物品 ID

    Returns:
        (訊息, 更新後的清單 DataFrame)
    """
    if not item_id:
        return "請輸入物品 ID", get_watchlist_dataframe()

    remove_from_watchlist(int(item_id))
    return "已移除", get_watchlist_dataframe()
