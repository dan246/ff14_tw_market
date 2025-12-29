"""製作利潤計算模組.

計算公式參考:
- FFXIVMB: https://www.ffxivmb.com/Recipes
- FFXIV Tools: https://ffxiv.itinerare.net/crafting
- FFXIV Tax Calculator: https://mbcalc.shiroastral.com/

材料成本 = min(Vendor Price, 製作成本, Market Board 最低價)
利潤 = 市場價 × (1 - 稅率) - 製作成本
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .api import (
    get_item_info,
    get_market_data,
    get_multi_item_market_data_async,
    get_recent_activity,
    get_recipe,
    get_recipe_by_item_id,
)
from .config import DATA_CENTER

# 職業對照表
CRAFT_TYPES = {
    0: "木工師",
    1: "鍛冶師",
    2: "甲冑師",
    3: "雕金師",
    4: "製革師",
    5: "裁縫師",
    6: "煉金師",
    7: "烹調師",
}

# 市場稅率（根據雇員等級）
# 參考: https://mbcalc.shiroastral.com/
# 預設使用 3%（中等等級雇員）
DEFAULT_TAX_RATE = 0.03

# 配方快取（配方資料不常變動）
_recipe_cache: dict = {}


def get_materials_from_recipe(recipe: dict) -> list:
    """從配方中提取材料清單.

    Args:
        recipe: 配方資訊字典

    Returns:
        材料列表，每個材料包含 id, name, quantity
    """
    materials = []
    for i in range(10):
        ingredient_key = f"ItemIngredient{i}"
        amount_key = f"AmountIngredient{i}"

        ingredient = recipe.get(ingredient_key)
        amount = recipe.get(amount_key, 0)

        if ingredient and amount > 0:
            item_id = ingredient.get("ID") or recipe.get(f"{ingredient_key}TargetID")
            if item_id:
                materials.append({
                    "id": item_id,
                    "name": ingredient.get("Name", f"物品 {item_id}"),
                    "quantity": amount,
                })

    return materials


def get_vendor_price(item_id: int) -> int:
    """取得物品的 NPC 商店價格.

    Args:
        item_id: 物品 ID

    Returns:
        Vendor 價格，如果沒有則返回 0
    """
    item_info = get_item_info(item_id)
    # Cafemaker API 的 PriceMid 是 NPC 售價
    vendor_price = item_info.get("PriceMid", 0)
    return vendor_price if vendor_price and vendor_price > 0 else 0


def get_lowest_price(item_id: int, world_or_dc: str = None) -> tuple[int, int, int]:
    """取得物品的最低價格（包含 Vendor 價格）.

    參考 GilGoblin 的做法：取 min(Vendor, Market Board)

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心

    Returns:
        (NQ 最低價, HQ 最低價, Vendor 價格)
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    # 取得 Vendor 價格
    vendor_price = get_vendor_price(item_id)

    # 取得市場價格
    market_data = get_market_data(item_id, world_or_dc)
    if not market_data:
        return (vendor_price, 0, vendor_price)

    listings = market_data.get("listings", [])
    nq_prices = [l["pricePerUnit"] for l in listings if not l.get("hq")]
    hq_prices = [l["pricePerUnit"] for l in listings if l.get("hq")]

    nq_min = min(nq_prices) if nq_prices else 0
    hq_min = min(hq_prices) if hq_prices else 0

    # 如果有 Vendor 價格且比市場便宜，用 Vendor
    if vendor_price > 0 and nq_min > 0:
        nq_min = min(nq_min, vendor_price)

    return (nq_min, hq_min, vendor_price)


def calculate_crafting_cost(
    item_id: int,
    world_or_dc: str = None,
    recursive: bool = True,
    max_depth: int = 3,
    tax_rate: float = DEFAULT_TAX_RATE,
    _depth: int = 0,
) -> dict:
    """計算製作成本與利潤.

    計算公式參考:
    - GilGoblin: 材料成本 = min(Vendor, 製作成本, Market Board)
    - 利潤 = 市場價 × (1 - 稅率) - 製作成本

    Args:
        item_id: 物品 ID
        world_or_dc: 伺服器或資料中心
        recursive: 是否遞迴計算材料成本
        max_depth: 最大遞迴深度
        tax_rate: 市場稅率（預設 3%）
        _depth: 當前遞迴深度（內部使用）

    Returns:
        {
            "item_id": int,
            "item_name": str,
            "recipe_id": int,
            "craft_type": str,  # 職業名稱
            "materials": [
                {
                    "id": int,
                    "name": str,
                    "quantity": int,
                    "unit_price": int,
                    "total_price": int,
                    "method": "vendor" | "buy" | "craft",
                },
                ...
            ],
            "craft_cost": int,  # 製作總成本
            "market_price_nq": int,
            "market_price_hq": int,
            "tax_rate": float,
            "tax_nq": int,  # NQ 稅金
            "tax_hq": int,  # HQ 稅金
            "revenue_nq": int,  # NQ 實際收入（扣稅後）
            "revenue_hq": int,  # HQ 實際收入（扣稅後）
            "profit_nq": int,
            "profit_hq": int,
            "profit_rate_nq": float,  # 利潤率 %
            "profit_rate_hq": float,
            "recommendation": str,
        }
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    # 取得配方
    recipe = get_recipe_by_item_id(item_id)
    if not recipe:
        return {"error": "此物品沒有製作配方"}

    # 取得物品資訊
    item_info = recipe.get("ItemResult", {})
    item_name = item_info.get("Name", f"物品 {item_id}")

    # 取得職業
    craft_type_id = recipe.get("CraftType", {}).get("ID", -1)
    craft_type = CRAFT_TYPES.get(craft_type_id, "未知")

    # 取得材料
    materials = get_materials_from_recipe(recipe)

    # 計算材料成本
    material_costs = []
    total_craft_cost = 0

    for material in materials:
        mat_id = material["id"]
        mat_quantity = material["quantity"]

        # 取得材料價格（包含 Vendor）
        nq_price, hq_price, vendor_price = get_lowest_price(mat_id, world_or_dc)

        # 決定最佳取得方式（參考 GilGoblin）
        method = "buy"
        best_price = nq_price if nq_price > 0 else hq_price

        # 如果 Vendor 有賣且更便宜
        if vendor_price > 0 and (best_price == 0 or vendor_price < best_price):
            best_price = vendor_price
            method = "vendor"

        # 遞迴計算：檢查自己製作是否更便宜
        if recursive and _depth < max_depth and best_price > 0:
            mat_recipe = get_recipe_by_item_id(mat_id)
            if mat_recipe:
                mat_craft = calculate_crafting_cost(
                    mat_id, world_or_dc, recursive=True,
                    max_depth=max_depth, tax_rate=tax_rate,
                    _depth=_depth + 1
                )
                if not mat_craft.get("error"):
                    craft_price = mat_craft.get("craft_cost", 0)
                    if craft_price > 0 and craft_price < best_price:
                        best_price = craft_price
                        method = "craft"

        total_price = best_price * mat_quantity
        total_craft_cost += total_price

        material_costs.append({
            "id": mat_id,
            "name": material["name"],
            "quantity": mat_quantity,
            "unit_price": best_price,
            "total_price": total_price,
            "method": method,
        })

    # 取得產出物市場價
    market_nq, market_hq, _ = get_lowest_price(item_id, world_or_dc)

    # 計算稅金和實際收入
    tax_nq = int(market_nq * tax_rate) if market_nq > 0 else 0
    tax_hq = int(market_hq * tax_rate) if market_hq > 0 else 0
    revenue_nq = market_nq - tax_nq
    revenue_hq = market_hq - tax_hq

    # 計算利潤（扣除稅金）
    profit_nq = revenue_nq - total_craft_cost if revenue_nq > 0 else 0
    profit_hq = revenue_hq - total_craft_cost if revenue_hq > 0 else 0

    # 計算利潤率
    profit_rate_nq = (profit_nq / total_craft_cost * 100) if total_craft_cost > 0 else 0
    profit_rate_hq = (profit_hq / total_craft_cost * 100) if total_craft_cost > 0 else 0

    # 生成推薦（基於扣稅後的利潤率）
    if profit_rate_hq >= 20:
        recommendation = "推薦製作 HQ 版本"
    elif profit_rate_nq >= 20:
        recommendation = "推薦製作 NQ 版本"
    elif profit_rate_hq >= 10 or profit_rate_nq >= 10:
        recommendation = "可考慮製作"
    elif profit_rate_hq > 0 or profit_rate_nq > 0:
        recommendation = "利潤較低"
    else:
        recommendation = "不推薦製作（虧損）"

    return {
        "item_id": item_id,
        "item_name": item_name,
        "recipe_id": recipe.get("ID"),
        "craft_type": craft_type,
        "materials": material_costs,
        "craft_cost": total_craft_cost,
        "market_price_nq": market_nq,
        "market_price_hq": market_hq,
        "tax_rate": tax_rate,
        "tax_nq": tax_nq,
        "tax_hq": tax_hq,
        "revenue_nq": revenue_nq,
        "revenue_hq": revenue_hq,
        "profit_nq": profit_nq,
        "profit_hq": profit_hq,
        "profit_rate_nq": round(profit_rate_nq, 1),
        "profit_rate_hq": round(profit_rate_hq, 1),
        "recommendation": recommendation,
    }


def get_profitable_items(
    world_or_dc: str = None,
    craft_type: int = None,
    limit: int = 20,
) -> list:
    """取得賺錢排行榜.

    掃描最近交易的物品，計算利潤，返回排行榜。

    Args:
        world_or_dc: 伺服器或資料中心
        craft_type: 職業 ID（0-7），None 表示全部
        limit: 返回數量限制

    Returns:
        利潤排行榜列表
    """
    if world_or_dc is None:
        world_or_dc = DATA_CENTER

    # 取得最近交易的物品
    recent_items = get_recent_activity(world_or_dc, limit=50)

    results = []

    def process_item(item: dict) -> Optional[dict]:
        """處理單一物品."""
        item_id = item.get("id")
        if not item_id:
            return None

        # 檢查是否有配方
        recipe = get_recipe_by_item_id(item_id)
        if not recipe:
            return None

        # 職業篩選
        if craft_type is not None:
            recipe_craft_type = recipe.get("CraftType", {}).get("ID", -1)
            if recipe_craft_type != craft_type:
                return None

        # 計算利潤（不遞迴，加快速度）
        profit_data = calculate_crafting_cost(
            item_id, world_or_dc, recursive=False
        )

        if profit_data.get("error"):
            return None

        # 只返回有利潤的物品
        if profit_data.get("profit_rate_hq", 0) <= 0 and profit_data.get("profit_rate_nq", 0) <= 0:
            return None

        return profit_data

    # 並行處理
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_item, item): item for item in recent_items}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    # 按 HQ 利潤率排序
    results.sort(key=lambda x: x.get("profit_rate_hq", 0), reverse=True)

    return results[:limit]


def format_price(price: int) -> str:
    """格式化價格顯示."""
    if price >= 1000000:
        return f"{price / 1000000:.1f}M"
    if price >= 1000:
        return f"{price / 1000:.1f}K"
    return f"{price:,}"


def format_crafting_result(result: dict) -> str:
    """格式化製作利潤結果為 Markdown.

    Args:
        result: calculate_crafting_cost 的返回值

    Returns:
        Markdown 格式的字串
    """
    if result.get("error"):
        return f"**{result['error']}**"

    # 推薦圖示
    profit_rate = max(result.get("profit_rate_nq", 0), result.get("profit_rate_hq", 0))
    if profit_rate >= 20:
        icon = ""
    elif profit_rate >= 10:
        icon = ""
    elif profit_rate > 0:
        icon = ""
    else:
        icon = ""

    # 取得方式圖示
    method_icons = {
        "vendor": "NPC",
        "buy": "MB",
        "craft": "製作",
    }

    output = f"""## {icon} {result['item_name']}

**職業:** {result['craft_type']}

### 材料清單

| 材料 | 數量 | 單價 | 小計 | 來源 |
|------|------|------|------|------|
"""

    for mat in result.get("materials", []):
        method_text = method_icons.get(mat["method"], mat["method"])
        output += f"| {mat['name']} | {mat['quantity']} | {format_price(mat['unit_price'])} | {format_price(mat['total_price'])} | {method_text} |\n"

    tax_rate_pct = result.get('tax_rate', 0.03) * 100

    output += f"""
### 成本與收益分析

| 項目 | NQ | HQ |
|------|------|------|
| **製作成本** | {format_price(result['craft_cost'])} | {format_price(result['craft_cost'])} |
| **市場價格** | {format_price(result['market_price_nq'])} | {format_price(result['market_price_hq'])} |
| **稅金 ({tax_rate_pct:.0f}%)** | -{format_price(result.get('tax_nq', 0))} | -{format_price(result.get('tax_hq', 0))} |
| **實際收入** | {format_price(result.get('revenue_nq', 0))} | {format_price(result.get('revenue_hq', 0))} |
| **利潤** | {format_price(result['profit_nq'])} | {format_price(result['profit_hq'])} |
| **利潤率** | {result['profit_rate_nq']:+.1f}% | {result['profit_rate_hq']:+.1f}% |

### {icon} {result['recommendation']}

---
<small>計算公式參考 [FFXIVMB](https://www.ffxivmb.com/Recipes) / [FFXIV Tools](https://ffxiv.itinerare.net/crafting) | 材料來源: NPC=商店購買, MB=市場板, 製作=自己做更便宜</small>
"""

    return output
