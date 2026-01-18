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

# 美化的圖表配色方案
CHART_COLORS = {
    "nq": "#8b9dc3",      # 柔和的藍灰色
    "hq": "#ffc107",      # 琥珀金色
    "background": "#1a1a2e",
    "paper": "#0f0f1a",
    "grid": "rgba(255, 255, 255, 0.08)",
    "text": "#e0e0e0",
    "title": "#ffc107",
}

# 自訂圖表佈局模板（不含 title，因為每個圖表需要不同的標題）
CHART_LAYOUT = {
    "paper_bgcolor": CHART_COLORS["paper"],
    "plot_bgcolor": CHART_COLORS["background"],
    "font": {
        "family": "Noto Sans TC, sans-serif",
        "color": CHART_COLORS["text"],
        "size": 12,
    },
    "title_font": {
        "size": 16,
        "color": CHART_COLORS["title"],
    },
    "title_x": 0.5,
    "title_xanchor": "center",
    "legend": {
        "bgcolor": "rgba(0, 0, 0, 0.3)",
        "bordercolor": "rgba(255, 255, 255, 0.1)",
        "borderwidth": 1,
        "font": {"color": CHART_COLORS["text"]},
    },
    "xaxis": {
        "gridcolor": CHART_COLORS["grid"],
        "linecolor": "rgba(255, 255, 255, 0.15)",
        "tickfont": {"color": CHART_COLORS["text"]},
        "title_font": {"color": CHART_COLORS["text"]},
    },
    "yaxis": {
        "gridcolor": CHART_COLORS["grid"],
        "linecolor": "rgba(255, 255, 255, 0.15)",
        "tickfont": {"color": CHART_COLORS["text"]},
        "title_font": {"color": CHART_COLORS["text"]},
    },
    "hoverlabel": {
        "bgcolor": "#2d2d3a",
        "bordercolor": "rgba(255, 193, 7, 0.3)",
        "font": {"color": CHART_COLORS["text"]},
    },
}


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
        fig.update_layout(**CHART_LAYOUT, height=400)
        fig.add_annotation(
            text="無歷史數據",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": CHART_COLORS["text"], "size": 14},
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
            name="NQ (普通品質)",
            line={
                "color": CHART_COLORS["nq"],
                "width": 2,
            },
            marker={
                "size": 8,
                "color": CHART_COLORS["nq"],
                "line": {"width": 1, "color": "#ffffff"},
            },
            hovertemplate="<b>NQ</b><br>價格: %{y:,.0f} Gil<br>時間: %{x}<extra></extra>",
        ))

    if hq_data:
        hq_times, hq_prices = zip(*sorted(hq_data))
        fig.add_trace(go.Scatter(
            x=hq_times,
            y=hq_prices,
            mode="markers+lines",
            name="HQ (高品質)",
            line={
                "color": CHART_COLORS["hq"],
                "width": 2,
            },
            marker={
                "size": 10,
                "symbol": "star",
                "color": CHART_COLORS["hq"],
                "line": {"width": 1, "color": "#ffffff"},
            },
            hovertemplate="<b>HQ ★</b><br>價格: %{y:,.0f} Gil<br>時間: %{x}<extra></extra>",
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        title=f"📈 {item_name} - 價格歷史",
        xaxis_title="交易時間",
        yaxis_title="價格 (Gil)",
        hovermode="x unified",
        height=400,
        margin={"l": 60, "r": 30, "t": 60, "b": 50},
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
            name="NQ (普通品質)",
            x=worlds,
            y=nq_prices,
            marker={
                "color": CHART_COLORS["nq"],
                "line": {"width": 1, "color": "rgba(255,255,255,0.3)"},
            },
            hovertemplate="<b>%{x}</b><br>NQ 最低價: %{y:,.0f} Gil<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="HQ (高品質)",
            x=worlds,
            y=hq_prices,
            marker={
                "color": CHART_COLORS["hq"],
                "line": {"width": 1, "color": "rgba(255,255,255,0.3)"},
            },
            hovertemplate="<b>%{x}</b><br>HQ 最低價: %{y:,.0f} Gil<extra></extra>",
        ))

        fig.update_layout(
            **CHART_LAYOUT,
            title=f"🌐 {item_name} - 跨伺服器比價",
            xaxis_title="伺服器",
            yaxis_title="最低價格 (Gil)",
            barmode="group",
            height=400,
            margin={"l": 60, "r": 30, "t": 60, "b": 50},
            bargap=0.15,
            bargroupgap=0.1,
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
        fig = go.Figure()
        fig.update_layout(**CHART_LAYOUT, height=400)
        return fig

    # 建立漸層色彩
    n_servers = len(stats_df)
    colors = [
        f"rgba(255, {193 - i * 10}, {7 + i * 15}, 0.85)"
        for i in range(n_servers)
    ]

    fig = go.Figure(data=[
        go.Bar(
            x=stats_df["伺服器"],
            y=stats_df["上傳次數"],
            marker={
                "color": colors,
                "line": {"width": 1, "color": "rgba(255,255,255,0.3)"},
            },
            hovertemplate="<b>%{x}</b><br>上傳次數: %{y:,.0f}<extra></extra>",
        )
    ])

    fig.update_layout(
        **CHART_LAYOUT,
        title="📊 繁中服上傳統計",
        xaxis_title="伺服器",
        yaxis_title="上傳次數",
        height=400,
        margin={"l": 60, "r": 30, "t": 60, "b": 50},
        showlegend=False,
    )

    return fig


def create_data_flow_chart(world_status: list[dict]) -> go.Figure:
    """建立資料流狀態圖表（甘特圖風格）.

    Args:
        world_status: 各伺服器狀態列表，來自 get_world_data_status()

    Returns:
        Plotly 圖表物件
    """
    if not world_status:
        fig = go.Figure()
        fig.update_layout(**CHART_LAYOUT, height=350)
        fig.add_annotation(
            text="等待資料中...",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"color": CHART_COLORS["text"], "size": 14},
        )
        return fig

    # 準備數據
    worlds = []
    elapsed_times = []
    event_counts = []
    colors = []

    for status in world_status:
        worlds.append(status["world_name"])
        elapsed = status["elapsed_seconds"]
        count = status["event_count"]
        event_counts.append(count)

        if elapsed < 0:
            # 從未收到數據
            elapsed_times.append(300)  # 顯示為 5 分鐘
            colors.append("rgba(128, 128, 128, 0.6)")  # 灰色
        elif elapsed < 30:
            # 非常新鮮 (30 秒內)
            elapsed_times.append(max(elapsed, 5))
            colors.append("rgba(76, 175, 80, 0.85)")  # 綠色
        elif elapsed < 120:
            # 較新鮮 (2 分鐘內)
            elapsed_times.append(elapsed)
            colors.append("rgba(255, 193, 7, 0.85)")  # 黃色
        elif elapsed < 300:
            # 稍舊 (5 分鐘內)
            elapsed_times.append(elapsed)
            colors.append("rgba(255, 152, 0, 0.85)")  # 橙色
        else:
            # 過時 (超過 5 分鐘)
            elapsed_times.append(min(elapsed, 600))
            colors.append("rgba(244, 67, 54, 0.85)")  # 紅色

    # 建立水平條形圖
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=worlds,
        x=elapsed_times,
        orientation="h",
        marker={
            "color": colors,
            "line": {"width": 1, "color": "rgba(255,255,255,0.3)"},
        },
        text=[
            f"{int(t)}秒 ({c}筆)" if t < 300 else ("無資料" if c == 0 else f">5分 ({c}筆)")
            for t, c in zip(elapsed_times, event_counts)
        ],
        textposition="inside",
        textfont={"color": "#ffffff", "size": 11},
        hovertemplate="<b>%{y}</b><br>距上次更新: %{x:.0f} 秒<extra></extra>",
    ))

    fig.update_layout(
        **CHART_LAYOUT,
        title="📡 各伺服器資料流狀態",
        xaxis_title="距上次收到資料 (秒)",
        yaxis_title="",
        height=350,
        margin={"l": 80, "r": 30, "t": 60, "b": 50},
        showlegend=False,
    )

    # 額外設定 x/y 軸
    fig.update_xaxes(range=[0, 320])
    fig.update_yaxes(autorange="reversed")  # 讓第一個伺服器在最上面

    # 添加說明文字
    fig.add_annotation(
        text="🟢 <30秒  🟡 <2分  🟠 <5分  🔴 >5分  ⚫ 無資料",
        xref="paper",
        yref="paper",
        x=0.5,
        y=-0.12,
        showarrow=False,
        font={"color": CHART_COLORS["text"], "size": 10},
    )

    return fig
