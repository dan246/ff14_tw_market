"""顯示邏輯函數."""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

import time

from .api import (
    get_full_item_data_fast,
    get_item_info,
    get_market_data,
    get_recent_activity,
    get_tax_rates,
    get_upload_stats,
    search_items,
)
from .websocket_api import get_ws_client
from .charts import (
    create_cross_world_comparison,
    create_price_chart,
    create_upload_stats_chart,
)
from .config import (
    DATA_CENTER,
    POPULAR_ITEMS,
    WORLD_NAMES,
    WORLDS,
)
from .utils import (
    format_price,
    format_relative_time,
    process_history,
    process_listings,
)


def search_and_display(query: str, category: int = 0, page: int = 1) -> tuple:
    """搜尋並顯示結果.

    Args:
        query: 搜尋關鍵字
        category: 物品分類 ID (ItemSearchCategory)，0 表示全部
        page: 頁碼

    Returns:
        (下拉選單更新, 狀態訊息, None, 頁碼, 總頁數)
    """
    # 如果沒有搜尋關鍵字且沒有選擇分類，顯示常用物品
    if not query and category == 0:
        choices = [(name, item_id) for name, item_id in POPULAR_ITEMS.items()]
        return (
            gr.update(choices=choices, value=None),
            "顯示常用物品，或輸入物品名稱/ID搜尋",
            None,
            1,  # 當前頁
            1,  # 總頁數
        )

    # 有分類時，即使沒有關鍵字也進行搜尋（使用空白作為萬用搜尋）
    search_query = query if query else " "
    result = search_items(search_query, category=category, page=page)
    items = result.get("items", [])
    pagination = result.get("pagination", {})

    current_page = pagination.get("page", 1)
    total_pages = pagination.get("page_total", 1)
    total_results = pagination.get("results_total", 0)

    if not items:
        return (
            gr.update(choices=[], value=None),
            "找不到符合的物品。提示：可直接輸入物品 ID",
            None,
            1,
            1,
        )

    choices = [(f"{r['name']} (ID:{r['id']})", r["id"]) for r in items]

    # 狀態訊息顯示分頁資訊
    if total_pages > 1:
        status = f"共 {total_results} 個結果，第 {current_page}/{total_pages} 頁"
    else:
        status = f"找到 {total_results} 個結果"

    return (
        gr.update(choices=choices, value=None),
        status,
        None,
        current_page,
        total_pages,
    )


def display_item_market(
    item_selection: int,
    selected_world: str,
    quality_filter: str,
    retainer_filter: str = "",
) -> tuple:
    """顯示物品市場資訊.

    Args:
        item_selection: 選擇的物品 ID
        selected_world: 選擇的伺服器
        quality_filter: 品質篩選
        retainer_filter: 雇員名稱篩選

    Returns:
        (物品資訊, 物品卡片, 上架列表, 交易歷史, 價格圖表, 比價表格, 比價圖表)
    """
    empty_df = pd.DataFrame()
    empty_fig = go.Figure()

    if not item_selection:
        return "", "", empty_df, empty_df, empty_fig, empty_df, empty_fig

    item_id = item_selection
    world_query = (
        selected_world if selected_world != "全部伺服器" else DATA_CENTER
    )

    # 開始關注此物品的 WebSocket 更新
    ws_client = get_ws_client()
    if ws_client:
        ws_client.watch_item(item_id)

    # 檢查 WebSocket 是否有此物品的緩存數據
    ws_data = None
    if ws_client:
        ws_data = ws_client.get_cached_data(item_id)

    if ws_data and ws_data.get("data", {}).get("listings"):
        # 使用 WebSocket 緩存的數據（更快）
        cached = ws_data["data"]
        item_info = get_item_info(item_id)  # 物品資訊還是用 API
        market_data = {
            "listings": cached.get("listings", []),
            "recentHistory": cached.get("recentHistory", []),
            "currentAveragePrice": cached.get("currentAveragePrice", 0),
            "averagePrice": cached.get("averagePrice", 0),
            "minPrice": cached.get("minPrice", 0),
            "maxPrice": cached.get("maxPrice", 0),
            "listingsCount": len(cached.get("listings", [])),
            "regularSaleVelocity": cached.get("regularSaleVelocity", 0),
            "lastUploadTime": int(ws_data["timestamp"] * 1000),
        }
    else:
        # 首次查詢，使用 REST API
        full_data = get_full_item_data_fast(item_id, world_query)
        item_info = full_data.get("item_info", {})
        market_data = full_data.get("market_data", {})

    item_name = item_info.get("Name", f"物品 {item_id}")
    item_level = item_info.get("LevelItem", 0)

    if not market_data:
        return (
            f"## {item_name}\n\n無法取得市場數據",
            "",
            empty_df,
            empty_df,
            empty_fig,
            empty_df,
            empty_fig,
        )

    # 當選擇特定伺服器時，傳入伺服器名稱作為預設值
    default_world = selected_world if selected_world != "全部伺服器" else None

    # 處理上架列表（支援雇員篩選）
    listings_df = process_listings(
        market_data.get("listings", []),
        quality_filter,
        default_world,
        retainer_filter.strip() if retainer_filter else None,
    )

    # 處理交易歷史
    history_df = process_history(
        market_data.get("recentHistory", []),
        quality_filter,
        default_world,
    )

    # 建立價格圖表
    price_chart = create_price_chart(market_data, item_name)

    # 建立跨伺服器比價
    comparison_df, comparison_chart = create_cross_world_comparison(
        item_id,
        item_name,
    )

    # 計算統計資訊
    current_avg = market_data.get("currentAveragePrice", 0)
    avg_price = market_data.get("averagePrice", 0)
    min_price = market_data.get("minPrice", 0)
    max_price = market_data.get("maxPrice", 0)
    listing_count = market_data.get("listingsCount", 0)
    sale_velocity = market_data.get("regularSaleVelocity", 0)
    last_update = format_relative_time(market_data.get("lastUploadTime", 0))

    info_text = f"""## {item_name}
**物品等級:** IL{item_level}

### 市場統計
| 項目 | 數值 |
|------|------|
| 當前均價 | {format_price(int(current_avg))} Gil |
| 歷史均價 | {format_price(int(avg_price))} Gil |
| 最低價 | {format_price(min_price)} Gil |
| 最高價 | {format_price(max_price)} Gil |
| 上架數量 | {listing_count} |
| 日銷售量 | {sale_velocity:.1f} |

*最後更新: {last_update}*
"""

    # 建立物品資訊卡
    # 取得物品描述
    item_desc = item_info.get("Description", "")
    if item_desc:
        # 截斷過長的描述
        if len(item_desc) > 150:
            item_desc = item_desc[:150] + "..."

    # 判斷是否可交易
    is_untradable = item_info.get("IsUntradable", False)
    tradable_text = "❌ 不可交易" if is_untradable else "✅ 可交易"

    # 堆疊上限
    stack_size = item_info.get("StackSize", 1)

    # NPC 售價（賣給商店的價格）
    vendor_price = item_info.get("PriceLow", 0)

    # ClassJob ID 對應表
    craft_job_names = {
        8: "刻木匠", 9: "鍛鐵匠", 10: "鑄甲匠", 11: "雕金匠",
        12: "製革匠", 13: "裁縫師", 14: "煉金術士", 15: "烹調師",
    }

    # 職業縮寫對應表
    job_abbr_names = {
        "PLD": "騎士", "WAR": "戰士", "DRK": "暗黑騎士", "GNB": "絕槍戰士",
        "WHM": "白魔法師", "SCH": "學者", "AST": "占星術士", "SGE": "賢者",
        "MNK": "武僧", "DRG": "龍騎士", "NIN": "忍者", "SAM": "武士", "RPR": "鐮刀師", "VPR": "蝰蛇劍士",
        "BRD": "吟遊詩人", "MCH": "機工士", "DNC": "舞者",
        "BLM": "黑魔法師", "SMN": "召喚師", "RDM": "赤魔法師", "PCT": "繪靈法師",
        "PGL": "格鬥家", "GLA": "劍術師", "MRD": "斧術師", "LNC": "槍術師",
        "ARC": "弓箭手", "ROG": "雙劍師", "THM": "咒術師", "ACN": "秘術師", "CNJ": "幻術師",
        "CRP": "刻木匠", "BSM": "鍛鐵匠", "ARM": "鑄甲匠", "GSM": "雕金匠",
        "LTW": "製革匠", "WVR": "裁縫師", "ALC": "煉金術士", "CUL": "烹調師",
        "MIN": "採礦工", "BTN": "園藝工", "FSH": "捕魚人",
        "BLU": "青魔法師",
    }

    # === A. 獲取方式 ===
    obtain_methods = []
    gcl = item_info.get("GameContentLinks", {})
    if not isinstance(gcl, dict):
        gcl = {}

    # 可製作
    recipes = item_info.get("Recipes", [])
    if recipes:
        craft_jobs = []
        for recipe in recipes[:2]:
            job_id = recipe.get("ClassJobID", 0)
            job_name = craft_job_names.get(job_id, "")
            level = recipe.get("Level", 0)
            if job_name:
                craft_jobs.append(f"{job_name} Lv.{level}")
        if craft_jobs:
            obtain_methods.append(f"🔨 製作: {', '.join(craft_jobs)}")

    # 可採集
    if gcl.get("GatheringItem"):
        obtain_methods.append("⛏️ 採集")

    # NPC 商店
    if gcl.get("GilShopItem"):
        npc_price = item_info.get("PriceMid", 0)
        if npc_price > 0:
            obtain_methods.append(f"🏪 NPC 商店: {npc_price:,} Gil")
        else:
            obtain_methods.append("🏪 NPC 商店")

    # 雇員探險
    if gcl.get("RetainerTaskNormal"):
        obtain_methods.append("📦 雇員探險")

    obtain_text = "\n".join(obtain_methods) if obtain_methods else "（無資料）"

    # === B. 用途資訊 ===
    usage_methods = []

    # 作為製作材料
    recipe_links = gcl.get("Recipe", {})
    ingredient_keys = [k for k in recipe_links.keys() if k.startswith("ItemIngredient")]
    if ingredient_keys:
        total_recipes = sum(len(recipe_links[k]) for k in ingredient_keys)
        usage_methods.append(f"🔧 製作材料 ({total_recipes} 個配方)")

    # 軍隊製作
    if gcl.get("CompanyCraftSupplyItem"):
        usage_methods.append("🏠 部隊工房材料")

    # 理符任務
    if gcl.get("CraftLeve") or gcl.get("LeveRewardItemGroup"):
        usage_methods.append("📋 理符任務")

    # 軍票上交
    if gcl.get("GCSupplyDuty"):
        usage_methods.append("🎖️ 軍票上交")

    usage_text = "\n".join(usage_methods) if usage_methods else "（無資料）"

    # === C. 裝備屬性 ===
    equip_text = ""
    equip_level = item_info.get("LevelEquip", 0)
    damage_phys = item_info.get("DamagePhys", 0)
    damage_mag = item_info.get("DamageMag", 0)
    defense_phys = item_info.get("DefensePhys", 0)
    defense_mag = item_info.get("DefenseMag", 0)

    # 檢查是否為裝備（必須有傷害/防禦或裝備槽位）
    equip_slot = item_info.get("EquipSlotCategory") or {}
    is_equipment = (
        damage_phys > 0 or damage_mag > 0 or
        defense_phys > 0 or defense_mag > 0 or
        equip_slot.get("MainHand") or equip_slot.get("OffHand") or
        equip_slot.get("Head") or equip_slot.get("Body") or
        equip_slot.get("Gloves") or equip_slot.get("Legs") or
        equip_slot.get("Feet") or equip_slot.get("Ears") or
        equip_slot.get("Neck") or equip_slot.get("Wrists") or
        equip_slot.get("FingerL") or equip_slot.get("FingerR")
    )

    if is_equipment:
        equip_lines = [f"**裝備等級:** Lv.{equip_level}"]

        # 職業限制
        cjc = item_info.get("ClassJobCategory") or {}
        jobs = [job_abbr_names.get(k, k) for k, v in cjc.items()
                if v == 1 and not k.endswith("Target") and k != "ID" and k in job_abbr_names]
        if jobs:
            if len(jobs) > 5:
                equip_lines.append(f"**職業:** {', '.join(jobs[:5])} 等 {len(jobs)} 職業")
            else:
                equip_lines.append(f"**職業:** {', '.join(jobs)}")

        # 武器傷害
        if damage_phys > 0 or damage_mag > 0:
            if damage_phys > damage_mag:
                equip_lines.append(f"⚔️ 物理傷害: {damage_phys}")
            else:
                equip_lines.append(f"✨ 魔法傷害: {damage_mag}")

        # 防具防禦
        if defense_phys > 0 or defense_mag > 0:
            equip_lines.append(f"🛡️ 防禦: {defense_phys} / 魔防: {defense_mag}")

        # 屬性加成
        stats = []
        for i in range(6):
            param = item_info.get(f"BaseParam{i}Target")
            value = item_info.get(f"BaseParamValue{i}", 0)
            if param and value:
                # param 可能是字典或字串
                if isinstance(param, dict):
                    name = param.get("Name", "")
                else:
                    name = str(param) if param else ""
                if name:
                    stats.append(f"{name} +{value}")
        if stats:
            equip_lines.append(f"📊 {', '.join(stats[:4])}")

        equip_text = "\n".join(equip_lines)

    # 組合物品資訊卡
    item_card = f"""### 🏷️ 物品資訊
**物品 ID:** `{item_id}` | 📦 堆疊: {stack_size}

{tradable_text}
{f"💰 NPC 售價: {vendor_price:,} Gil" if vendor_price > 0 else ""}
"""

    # 裝備屬性（如果是裝備）
    if equip_text:
        item_card += f"""
---
### ⚔️ 裝備屬性
{equip_text}
"""

    # 獲取方式
    item_card += f"""
---
### 📍 獲取方式
{obtain_text}
"""

    # 用途資訊
    if usage_methods:
        item_card += f"""
---
### 📦 用途
{usage_text}
"""

    # 外部連結
    item_card += f"""
---
### 🔗 外部連結
- [Universalis](https://universalis.app/market/{item_id})
- [Teamcraft](https://ffxivteamcraft.com/db/zh/item/{item_id})
- [Garland Tools](https://garlandtools.org/db/#item/{item_id})
"""

    # 物品說明
    if item_desc:
        item_card += f"""
---
### 📜 說明
*{item_desc}*
"""

    return (
        info_text,
        item_card,
        listings_df,
        history_df,
        price_chart,
        comparison_df,
        comparison_chart,
    )


def _format_tax_row(world: str, tax_data: dict) -> Optional[dict]:
    """格式化單一伺服器的稅率資料."""
    if not tax_data:
        return None
    uldah_tax = tax_data.get("Ul'dah", 0)
    return {
        "伺服器": world,
        "利姆薩·羅敏薩": f"{tax_data.get('Limsa Lominsa', 0)}%",
        "格里達尼亞": f"{tax_data.get('Gridania', 0)}%",
        "烏爾達哈": f"{uldah_tax}%",
        "伊修加德": f"{tax_data.get('Ishgard', 0)}%",
        "黃金港": f"{tax_data.get('Kugane', 0)}%",
        "水晶都": f"{tax_data.get('Crystarium', 0)}%",
        "舊薩雷安": f"{tax_data.get('Old Sharlayan', 0)}%",
        "圖萊尤拉": f"{tax_data.get('Tuliyollal', 0)}%",
    }


def display_tax_rates(selected_world: str) -> pd.DataFrame:
    """顯示稅率資訊.

    Args:
        selected_world: 選擇的伺服器

    Returns:
        稅率 DataFrame
    """
    if selected_world == "全部伺服器":
        # 並行請求所有伺服器的稅率
        all_taxes = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_world = {
                executor.submit(get_tax_rates, world): world
                for world in WORLD_NAMES
            }
            for future in future_to_world:
                world = future_to_world[future]
                tax_data = future.result()
                row = _format_tax_row(world, tax_data)
                if row:
                    all_taxes.append(row)

        # 按原始順序排序
        all_taxes.sort(key=lambda x: WORLD_NAMES.index(x["伺服器"]))
        return pd.DataFrame(all_taxes)

    tax_data = get_tax_rates(selected_world)
    if not tax_data:
        return pd.DataFrame({"訊息": ["無法取得稅率資訊"]})

    return pd.DataFrame([
        {"城市": city, "稅率": f"{rate}%"}
        for city, rate in tax_data.items()
    ])


def display_market_activity(selected_world: str) -> pd.DataFrame:
    """顯示市場動態.

    Args:
        selected_world: 選擇的伺服器

    Returns:
        市場動態 DataFrame
    """
    world_query = selected_world if selected_world != "全部伺服器" else None
    activity = get_recent_activity(world_query, limit=20)

    if not activity:
        return pd.DataFrame({"訊息": ["無法取得市場動態"]})

    data = []
    for item in activity:
        nq_price = item["nq_min"]
        hq_price = item["hq_min"]
        data.append({
            "物品 ID": item["id"],
            "物品名稱": item["name"],
            "NQ 最低價": format_price(nq_price) if nq_price else "-",
            "HQ 最低價": format_price(hq_price) if hq_price else "-",
            "上架數": item["listing_count"],
            "更新時間": format_relative_time(item["last_update"]),
        })

    return pd.DataFrame(data)


def display_upload_stats() -> Tuple[pd.DataFrame, go.Figure]:
    """顯示上傳統計.

    Returns:
        (統計 DataFrame, 統計圖表)
    """
    stats = get_upload_stats()
    if not stats:
        return pd.DataFrame({"訊息": ["無法取得統計資訊"]}), go.Figure()

    # 繁中服伺服器名稱列表
    tw_world_names = set(WORLDS.values())

    # 篩選繁中服的數據
    tw_stats = []
    for world_name, data in stats.items():
        if world_name in tw_world_names:
            count = data.get("count", 0) if isinstance(data, dict) else data
            tw_stats.append({
                "伺服器": world_name,
                "上傳次數": count,
            })

    df = pd.DataFrame(tw_stats)
    fig = create_upload_stats_chart(df)

    return df, fig
