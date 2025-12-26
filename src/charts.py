"""圖表生成函數."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .api import get_market_data
from .config import WORLD_NAMES
from .utils import format_relative_time


def _normalize_timestamp(timestamp: int) -> int:
    """正規化時間戳（毫秒轉秒）."""
    if timestamp > 9999999999:
        return timestamp // 1000
    return timestamp


def create_price_chart(market_data: dict, item_name: str) -> go.Figure:
    """建立價格歷史圖表.

    Args:
        market_data: 市場數據（包含 recentHistory）
        item_name: 物品名稱

    Returns:
        Plotly 圖表物件
    """
    entries = market_data.get("recentHistory", [])
    if not entries:
        fig = go.Figure()
        fig.add_annotation(
            text="無歷史數據",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return fig

    # 分離 HQ 和 NQ 數據
    hq_data = [
        (
            datetime.fromtimestamp(_normalize_timestamp(e["timestamp"])),
            e["pricePerUnit"],
        )
        for e in entries
        if e.get("hq")
    ]
    nq_data = [
        (
            datetime.fromtimestamp(_normalize_timestamp(e["timestamp"])),
            e["pricePerUnit"],
        )
        for e in entries
        if not e.get("hq")
    ]

    fig = go.Figure()

    if nq_data:
        nq_times, nq_prices = zip(*sorted(nq_data))
        fig.add_trace(go.Scatter(
            x=nq_times,
            y=nq_prices,
            mode="markers+lines",
            name="NQ",
            line={"color": "#6c757d"},
            marker={"size": 6},
        ))

    if hq_data:
        hq_times, hq_prices = zip(*sorted(hq_data))
        fig.add_trace(go.Scatter(
            x=hq_times,
            y=hq_prices,
            mode="markers+lines",
            name="HQ",
            line={"color": "#ffc107"},
            marker={"size": 6, "symbol": "star"},
        ))

    fig.update_layout(
        title=f"{item_name} - 價格歷史",
        xaxis_title="時間",
        yaxis_title="價格 (Gil)",
        hovermode="x unified",
        template="plotly_dark",
        height=400,
    )

    return fig


def _fetch_world_data(item_id: int, world_name: str) -> Optional[dict]:
    """取得單一伺服器的市場數據（用於並行處理）."""
    market_data = get_market_data(item_id, world_name)
    if not market_data:
        return None

    listings = market_data.get("listings", [])
    if not listings:
        return None

    nq_prices = [
        listing["pricePerUnit"]
        for listing in listings
        if not listing.get("hq")
    ]
    hq_prices = [
        listing["pricePerUnit"]
        for listing in listings
        if listing.get("hq")
    ]

    return {
        "伺服器": world_name,
        "NQ 最低價": min(nq_prices) if nq_prices else "無",
        "HQ 最低價": min(hq_prices) if hq_prices else "無",
        "上架數量": len(listings),
        "最後更新": format_relative_time(
            market_data.get("lastUploadTime", 0)
        ),
    }


def create_cross_world_comparison(
    item_id: int,
    item_name: str,
) -> Tuple[pd.DataFrame, go.Figure]:
    """建立跨伺服器比價（並行請求加速）.

    Args:
        item_id: 物品 ID
        item_name: 物品名稱

    Returns:
        (比價表格 DataFrame, 比價圖表)
    """
    comparison_data = []

    # 使用 ThreadPoolExecutor 並行請求所有伺服器
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(_fetch_world_data, item_id, world): world
            for world in WORLD_NAMES
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                comparison_data.append(result)

    # 按伺服器名稱排序
    comparison_data.sort(key=lambda x: WORLD_NAMES.index(x["伺服器"]))

    df = pd.DataFrame(comparison_data)

    # 建立圖表
    fig = go.Figure()

    if comparison_data:
        worlds = [d["伺服器"] for d in comparison_data]
        nq_prices = [
            d["NQ 最低價"] if isinstance(d["NQ 最低價"], int) else 0
            for d in comparison_data
        ]
        hq_prices = [
            d["HQ 最低價"] if isinstance(d["HQ 最低價"], int) else 0
            for d in comparison_data
        ]

        fig.add_trace(go.Bar(
            name="NQ",
            x=worlds,
            y=nq_prices,
            marker_color="#6c757d",
        ))
        fig.add_trace(go.Bar(
            name="HQ",
            x=worlds,
            y=hq_prices,
            marker_color="#ffc107",
        ))

        fig.update_layout(
            title=f"{item_name} - 跨伺服器比價",
            xaxis_title="伺服器",
            yaxis_title="價格 (Gil)",
            barmode="group",
            template="plotly_dark",
            height=400,
        )

    return df, fig


def create_upload_stats_chart(stats_df: pd.DataFrame) -> go.Figure:
    """建立上傳統計圖表.

    Args:
        stats_df: 統計數據 DataFrame

    Returns:
        Plotly 圖表物件
    """
    if stats_df.empty:
        return go.Figure()

    fig = px.bar(
        stats_df,
        x="伺服器",
        y="上傳次數",
        title="繁中服上傳統計",
        template="plotly_dark",
    )

    return fig
