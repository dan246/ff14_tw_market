"""顯示邏輯函數."""

from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from .api import (
    get_item_info,
    get_market_data,
    get_recent_activity,
    get_tax_rates,
    get_upload_stats,
    search_items,
)
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


def search_and_display(query: str) -> tuple:
    """搜尋並顯示結果.

    Args:
        query: 搜尋關鍵字

    Returns:
        (下拉選單更新, 狀態訊息, None)
    """
    if not query:
        choices = [(name, item_id) for name, item_id in POPULAR_ITEMS.items()]
        return (
            gr.update(choices=choices, value=None),
            "顯示常用物品，或輸入物品名稱/ID搜尋",
            None,
        )

    results = search_items(query)
    if not results:
        return (
            gr.update(choices=[], value=None),
            "找不到符合的物品。提示：可直接輸入物品 ID",
            None,
        )

    choices = [(f"{r['name']} (ID:{r['id']})", r["id"]) for r in results]
    return (
        gr.update(choices=choices, value=None),
        f"找到 {len(results)} 個結果",
        None,
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
        (物品資訊, 上架列表, 交易歷史, 價格圖表, 比價表格, 比價圖表)
    """
    empty_df = pd.DataFrame()
    empty_fig = go.Figure()

    if not item_selection:
        return "", empty_df, empty_df, empty_fig, empty_df, empty_fig

    item_id = item_selection

    # 取得物品資訊
    item_info = get_item_info(item_id)
    item_name = item_info.get("Name", f"物品 {item_id}")
    item_level = item_info.get("LevelItem", 0)

    # 取得市場數據
    world_query = (
        selected_world if selected_world != "全部伺服器" else DATA_CENTER
    )
    market_data = get_market_data(item_id, world_query)

    if not market_data:
        return (
            f"## {item_name}\n\n無法取得市場數據",
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

    return (
        info_text,
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
