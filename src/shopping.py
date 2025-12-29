"""購物清單與雇員銷售建議模組."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .api import get_item_info, get_market_data, search_items
from .config import DATA_CENTER, WORLDS, WORLD_NAMES


def parse_shopping_list(text: str) -> list[dict]:
    """解析購物清單文字.

    支援格式:
    - 每行一個物品（可帶數量）
    - "物品名稱 x數量" 或 "物品名稱 數量"
    - "物品名稱*數量"

    Args:
        text: 購物清單文字

    Returns:
        物品列表 [{"name": str, "quantity": int, "id": int or None}, ...]
    """
    if not text:
        return []

    items = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 解析數量
        quantity = 1
        name = line

        # 格式: "物品名 x10" 或 "物品名 *10" 或 "物品名 10"
        import re
        match = re.match(r"(.+?)\s*[x\*×]?\s*(\d+)\s*$", line, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            quantity = int(match.group(2))

        if name:
            items.append({
                "name": name,
                "quantity": quantity,
                "id": None,
            })

    return items


def resolve_item_ids(items: list[dict]) -> list[dict]:
    """為購物清單中的物品解析 ID.

    Args:
        items: 購物清單物品列表

    Returns:
        包含 ID 的物品列表
    """
    resolved = []

    for item in items:
        name = item["name"]
        quantity = item["quantity"]

        # 如果已經是 ID
        if name.isdigit():
            item_id = int(name)
            item_info = get_item_info(item_id)
            resolved.append({
                "name": item_info.get("Name", name),
                "quantity": quantity,
                "id": item_id,
            })
            continue

        # 搜尋物品
        results = search_items(name, limit=1)
        if results:
            resolved.append({
                "name": results[0]["name"],
                "quantity": quantity,
                "id": results[0]["id"],
            })
        else:
            resolved.append({
                "name": name,
                "quantity": quantity,
                "id": None,
                "error": "找不到此物品",
            })

    return resolved


def calculate_shopping_cost(items: list[dict], world_or_dc: str = None) -> dict:
    """計算購物清單的總成本.

    Args:
        items: 購物清單物品列表（需已解析 ID）
        world_or_dc: 伺服器或資料中心

    Returns:
        {
            "items": [
                {
                    "name": str,
                    "quantity": int,
                    "id": int,
                    "prices": {world: price, ...},
                    "best_world": str,
                    "best_price": int,
                },
                ...
            ],
            "world_totals": {world: total, ...},
            "best_world": str,
            "best_total": int,
            "all_on_best": bool,  # 是否所有物品都在最佳伺服器有貨
        }
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    result_items = []
    world_totals = {name: 0 for name in WORLD_NAMES}
    world_availability = {name: 0 for name in WORLD_NAMES}  # 有貨的物品數

    def fetch_item_prices(item: dict) -> dict:
        """取得單一物品在各伺服器的價格."""
        if not item.get("id"):
            return {
                **item,
                "prices": {},
                "best_world": None,
                "best_price": 0,
                "error": item.get("error", "無法取得價格"),
            }

        item_id = item["id"]
        quantity = item["quantity"]
        prices = {}

        # 取得各伺服器價格
        for world_name in WORLD_NAMES:
            try:
                market_data = get_market_data(item_id, world_name)
                listings = market_data.get("listings", [])

                if listings:
                    # 計算能滿足需求數量的最低成本
                    total_cost = 0
                    remaining = quantity
                    # 按價格排序
                    sorted_listings = sorted(listings, key=lambda x: x["pricePerUnit"])

                    for listing in sorted_listings:
                        if remaining <= 0:
                            break
                        buy_qty = min(remaining, listing["quantity"])
                        total_cost += buy_qty * listing["pricePerUnit"]
                        remaining -= buy_qty

                    if remaining <= 0:
                        prices[world_name] = total_cost
                    else:
                        # 數量不足，標記為無貨
                        prices[world_name] = None
                else:
                    prices[world_name] = None
            except Exception:
                prices[world_name] = None

        # 找最佳伺服器
        valid_prices = {w: p for w, p in prices.items() if p is not None}
        if valid_prices:
            best_world = min(valid_prices, key=valid_prices.get)
            best_price = valid_prices[best_world]
        else:
            best_world = None
            best_price = 0

        return {
            **item,
            "prices": prices,
            "best_world": best_world,
            "best_price": best_price,
        }

    # 並行取得價格
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_item_prices, item) for item in items]
        for future in as_completed(futures):
            result_items.append(future.result())

    # 計算各伺服器總價
    for item in result_items:
        for world_name in WORLD_NAMES:
            price = item.get("prices", {}).get(world_name)
            if price is not None:
                world_totals[world_name] += price
                world_availability[world_name] += 1
            else:
                # 無貨的伺服器設為無限大（不考慮）
                world_totals[world_name] = float("inf")

    # 找整體最佳伺服器
    valid_totals = {w: t for w, t in world_totals.items() if t != float("inf")}
    if valid_totals:
        best_world = min(valid_totals, key=valid_totals.get)
        best_total = valid_totals[best_world]
        all_on_best = world_availability[best_world] == len(items)
    else:
        best_world = None
        best_total = 0
        all_on_best = False

    return {
        "items": result_items,
        "world_totals": {w: t if t != float("inf") else None for w, t in world_totals.items()},
        "best_world": best_world,
        "best_total": best_total,
        "all_on_best": all_on_best,
        "item_count": len(items),
    }


def format_shopping_result(result: dict) -> str:
    """格式化購物清單結果為 Markdown.

    Args:
        result: calculate_shopping_cost 的結果

    Returns:
        Markdown 格式字串
    """
    if not result.get("items"):
        return "請輸入購物清單"

    output = "## 購物清單分析\n\n"

    # 最佳購買建議
    if result.get("best_world"):
        output += f"### 最佳購買伺服器: **{result['best_world']}**\n"
        output += f"總成本: **{result['best_total']:,} Gil**\n\n"

        if not result.get("all_on_best"):
            output += "> 部分物品在此伺服器缺貨，可能需要跨服購買\n\n"
    else:
        output += "### 無法找到完整購買方案\n"
        output += "> 部分物品在所有伺服器都缺貨\n\n"

    # 各物品明細
    output += "### 物品明細\n\n"
    output += "| 物品 | 數量 | 最佳伺服器 | 最低價 |\n"
    output += "|------|------|------------|--------|\n"

    for item in result.get("items", []):
        name = item.get("name", "???")
        qty = item.get("quantity", 1)

        if item.get("error"):
            output += f"| {name} | {qty} | - | {item['error']} |\n"
        elif item.get("best_world"):
            output += f"| {name} | {qty} | {item['best_world']} | {item['best_price']:,} Gil |\n"
        else:
            output += f"| {name} | {qty} | - | 缺貨 |\n"

    # 各伺服器總價比較
    output += "\n### 各伺服器總價比較\n\n"
    output += "| 伺服器 | 總價 | 差價 |\n"
    output += "|--------|------|------|\n"

    world_totals = result.get("world_totals", {})
    best_total = result.get("best_total", 0)

    # 按價格排序
    sorted_worlds = sorted(
        [(w, t) for w, t in world_totals.items() if t is not None],
        key=lambda x: x[1]
    )

    for world, total in sorted_worlds:
        diff = total - best_total if best_total > 0 else 0
        marker = " (最低)" if diff == 0 else ""
        diff_str = f"+{diff:,}" if diff > 0 else "-"
        output += f"| {world}{marker} | {total:,} Gil | {diff_str} |\n"

    # 缺貨的伺服器
    missing_worlds = [w for w, t in world_totals.items() if t is None]
    if missing_worlds:
        output += f"\n> 以下伺服器有物品缺貨: {', '.join(missing_worlds)}\n"

    return output


# ============================================================
# 雇員銷售建議
# ============================================================

def analyze_sale_velocity(item_id: int, world_or_dc: str = None) -> dict:
    """分析物品的銷售速度.

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心

    Returns:
        {
            "sales_per_day": float,  # 平均每日銷量
            "avg_price": int,        # 平均成交價
            "total_sales": int,      # 總銷售數量
            "days_analyzed": int,    # 分析天數
        }
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    market_data = get_market_data(item_id, world_or_dc)
    history = market_data.get("recentHistory", [])

    if not history:
        return {
            "sales_per_day": 0,
            "avg_price": 0,
            "total_sales": 0,
            "days_analyzed": 0,
        }

    # 計算時間範圍
    import time
    now = time.time()
    timestamps = [h.get("timestamp", 0) for h in history]

    if not timestamps:
        return {
            "sales_per_day": 0,
            "avg_price": 0,
            "total_sales": 0,
            "days_analyzed": 0,
        }

    oldest = min(timestamps)
    days = max((now - oldest) / 86400, 1)  # 至少算1天

    total_qty = sum(h.get("quantity", 0) for h in history)
    total_value = sum(h.get("pricePerUnit", 0) * h.get("quantity", 1) for h in history)
    avg_price = total_value // total_qty if total_qty > 0 else 0

    return {
        "sales_per_day": round(total_qty / days, 1),
        "avg_price": avg_price,
        "total_sales": total_qty,
        "days_analyzed": round(days, 1),
    }


def get_retainer_suggestions(world_or_dc: str = None, limit: int = 20) -> list:
    """取得雇員銷售建議.

    分析最近市場活動，找出賣得快且利潤高的物品。

    Args:
        world_or_dc: 伺服器或資料中心
        limit: 結果數量限制

    Returns:
        推薦物品列表
    """
    from .api import get_recent_activity

    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    # 取得最近活躍的物品
    recent_items = get_recent_activity(world_or_dc, limit=50)

    results = []

    def analyze_item(item: dict) -> Optional[dict]:
        """分析單一物品的銷售潛力."""
        item_id = item.get("id")
        if not item_id:
            return None

        # 分析銷售速度
        velocity = analyze_sale_velocity(item_id, world_or_dc)

        # 過濾掉銷量太低的物品
        if velocity["sales_per_day"] < 0.5:  # 每天至少賣0.5個
            return None

        # 取得當前價格
        nq_min = item.get("nq_min") or 0
        hq_min = item.get("hq_min") or 0
        best_price = hq_min if hq_min > 0 else nq_min

        if best_price <= 0:
            return None

        # 計算推薦分數（銷量 × 價格）
        score = velocity["sales_per_day"] * best_price

        return {
            "id": item_id,
            "name": item.get("name", f"物品 {item_id}"),
            "nq_price": nq_min,
            "hq_price": hq_min,
            "sales_per_day": velocity["sales_per_day"],
            "avg_price": velocity["avg_price"],
            "listing_count": item.get("listing_count", 0),
            "score": score,
            "recommendation": _get_recommendation(velocity, best_price),
        }

    # 並行分析
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(analyze_item, item) for item in recent_items]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    # 按推薦分數排序
    results.sort(key=lambda x: x["score"], reverse=True)

    return results[:limit]


def _get_recommendation(velocity: dict, price: int) -> str:
    """根據銷售數據生成推薦等級.

    Args:
        velocity: 銷售速度資料
        price: 物品價格

    Returns:
        推薦等級文字
    """
    sales_per_day = velocity.get("sales_per_day", 0)

    # 高銷量高價格 = 極力推薦
    if sales_per_day >= 5 and price >= 10000:
        return "極力推薦"
    elif sales_per_day >= 3 and price >= 5000:
        return "強力推薦"
    elif sales_per_day >= 2 and price >= 1000:
        return "推薦"
    elif sales_per_day >= 1:
        return "可考慮"
    else:
        return "銷量較低"


def format_retainer_suggestions(suggestions: list) -> str:
    """格式化雇員銷售建議為 Markdown.

    Args:
        suggestions: 推薦物品列表

    Returns:
        Markdown 格式字串
    """
    if not suggestions:
        return "目前沒有找到推薦的銷售物品"

    output = "## 雇員銷售建議\n\n"
    output += "> 根據銷售速度與價格綜合評估，以下物品值得上架販售\n\n"

    output += "| 物品 | NQ 價格 | HQ 價格 | 日銷量 | 上架數 | 推薦度 |\n"
    output += "|------|---------|---------|--------|--------|--------|\n"

    for item in suggestions:
        name = item.get("name", "???")
        nq = f"{item['nq_price']:,}" if item.get("nq_price") else "-"
        hq = f"{item['hq_price']:,}" if item.get("hq_price") else "-"
        sales = f"{item['sales_per_day']:.1f}"
        listings = item.get("listing_count", 0)
        rec = item.get("recommendation", "")

        output += f"| {name} | {nq} | {hq} | {sales} | {listings} | {rec} |\n"

    output += "\n### 說明\n"
    output += "- **日銷量**: 平均每天賣出的數量\n"
    output += "- **上架數**: 目前市場上的上架數量（競爭程度）\n"
    output += "- **推薦度**: 綜合銷量與價格的評估\n"

    return output
