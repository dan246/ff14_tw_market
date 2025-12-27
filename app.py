"""FF14 繁中服市場板查詢工具 - Gradio 介面."""

import gradio as gr

# 檢查 Gradio 版本，決定使用 BrowserState 或 State
GRADIO_VERSION = int(gr.__version__.split(".")[0])
USE_BROWSER_STATE = GRADIO_VERSION >= 5

from src.config import POPULAR_ITEMS, WORLD_NAMES
from src.display import (
    display_item_market,
    display_market_activity,
    display_tax_rates,
    display_upload_stats,
    search_and_display,
)
from src.watchlist import (
    add_item_to_list,
    get_watchlist_with_alerts,
    remove_item_from_list,
)
from src.ai_analysis import analyze_item_with_ai, get_market_summary
from src.websocket_api import start_websocket


def refresh_watchlist_with_notify(watchlist: list):
    """刷新監看清單並顯示達標通知."""
    if watchlist is None:
        watchlist = []
    df, alerts = get_watchlist_with_alerts(watchlist)
    if alerts:
        gr.Info("\n".join(alerts))
    return df


def create_app() -> gr.Blocks:
    """建立 Gradio 應用.

    Returns:
        Gradio Blocks 應用
    """
    with gr.Blocks(
        title="FF14 繁中服市場板",
        theme=gr.themes.Soft(primary_hue="amber", neutral_hue="slate"),
    ) as app:
        # 使用 BrowserState（Gradio 5+）或 State（Gradio 4）儲存監看清單
        if USE_BROWSER_STATE:
            watchlist_state = gr.BrowserState(
                default_value=[],
                storage_key="ff14_watchlist",
            )
        else:
            watchlist_state = gr.State(value=[])

        gr.Markdown("""
        # FF14 繁中服市場板查詢工具

        使用 [Universalis API](https://universalis.app/) 查詢繁體中文伺服器（陸行鳥資料中心）的市場數據

        **支援伺服器:** 伊弗利特、迦樓羅、利維坦、鳳凰、奧汀、巴哈姆特、拉姆、泰坦

        > **搜尋提示:** 可輸入繁體中文、英文名稱、物品 ID，或貼上 Universalis 網址

        🔗 **WebSocket 已連線** - 使用異步 API 加速查詢
        """)

        with gr.Tabs():
            _build_market_tab()
            _build_ai_tab()
            _build_activity_tab()
            _build_watchlist_tab(watchlist_state)
            _build_tax_tab()
            _build_stats_tab()
            _build_changelog_tab()

    return app


def _build_market_tab() -> None:
    """建立市場查詢頁籤."""
    with gr.TabItem("市場查詢"):
        gr.Markdown("""
        查詢物品的市場價格、上架情況和交易紀錄。
        支援繁體中文搜尋，也可以直接貼上 Universalis 網址。
        """)
        with gr.Row():
            with gr.Column(scale=2):
                search_input = gr.Textbox(
                    label="搜尋物品",
                    placeholder="繁體中文、英文名稱、物品 ID 或 Universalis 網址",
                    lines=1,
                )
                search_status = gr.Markdown(
                    "顯示常用物品，或輸入物品名稱/ID搜尋"
                )
                item_dropdown = gr.Dropdown(
                    label="選擇物品",
                    choices=[
                        (name, item_id)
                        for name, item_id in POPULAR_ITEMS.items()
                    ],
                    interactive=True,
                )

            with gr.Column(scale=1):
                world_select = gr.Dropdown(
                    label="選擇伺服器",
                    choices=["全部伺服器"] + WORLD_NAMES,
                    value="全部伺服器",
                )
                quality_select = gr.Radio(
                    label="品質篩選",
                    choices=[("全部", "all"), ("NQ", "nq"), ("HQ", "hq")],
                    value="all",
                )
                retainer_filter = gr.Textbox(
                    label="雇員名稱篩選",
                    placeholder="輸入雇員名稱（可部分匹配）",
                    lines=1,
                )
                with gr.Row():
                    search_btn = gr.Button("查詢市場", variant="primary")
                    auto_refresh = gr.Checkbox(
                        label="自動刷新 (5秒)",
                        value=False,
                    )

        item_info = gr.Markdown("")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 當前上架")
                listings_table = gr.Dataframe(
                    headers=[
                        "品質", "單價", "數量", "總價",
                        "雇員", "伺服器", "更新時間",
                    ],
                    interactive=False,
                )

            with gr.Column():
                gr.Markdown("### 交易歷史")
                history_table = gr.Dataframe(
                    headers=[
                        "品質", "單價", "數量", "總價",
                        "買家", "伺服器", "成交時間",
                    ],
                    interactive=False,
                )

        gr.Markdown("### 價格走勢")
        price_chart = gr.Plot()

        gr.Markdown("### 跨伺服器比價")
        with gr.Row():
            comparison_table = gr.Dataframe(interactive=False)
            comparison_chart = gr.Plot()

        # 自動刷新用的計時器 (5秒，使用 WebSocket 緩存)
        timer = gr.Timer(value=5, active=False)

        # 事件綁定
        search_input.change(
            fn=search_and_display,
            inputs=[search_input],
            outputs=[item_dropdown, search_status, item_info],
        )

        search_btn.click(
            fn=display_item_market,
            inputs=[item_dropdown, world_select, quality_select, retainer_filter],
            outputs=[
                item_info, listings_table, history_table,
                price_chart, comparison_table, comparison_chart,
            ],
        )

        item_dropdown.change(
            fn=display_item_market,
            inputs=[item_dropdown, world_select, quality_select, retainer_filter],
            outputs=[
                item_info, listings_table, history_table,
                price_chart, comparison_table, comparison_chart,
            ],
        )

        # 自動刷新開關
        auto_refresh.change(
            fn=lambda x: gr.Timer(active=x),
            inputs=[auto_refresh],
            outputs=[timer],
        )

        # 計時器觸發刷新
        timer.tick(
            fn=display_item_market,
            inputs=[item_dropdown, world_select, quality_select, retainer_filter],
            outputs=[
                item_info, listings_table, history_table,
                price_chart, comparison_table, comparison_chart,
            ],
        )


def _build_activity_tab() -> None:
    """建立市場動態頁籤."""
    with gr.TabItem("市場動態"):
        gr.Markdown("""
        最近有人上架或更新價格的物品，方便你看看現在市場在賣什麼。
        """)

        with gr.Row():
            activity_world_select = gr.Dropdown(
                label="選擇伺服器",
                choices=["全部伺服器"] + WORLD_NAMES,
                value="全部伺服器",
            )
            refresh_activity_btn = gr.Button("重新整理", variant="primary")
            auto_refresh_activity = gr.Checkbox(
                label="自動刷新 (60秒)",
                value=False,
            )

        activity_table = gr.Dataframe(
            headers=[
                "物品 ID", "物品名稱", "NQ 最低價",
                "HQ 最低價", "上架數", "更新時間",
            ],
            interactive=False,
        )

        # 自動刷新計時器
        activity_timer = gr.Timer(value=60, active=False)

        # 事件綁定
        refresh_activity_btn.click(
            fn=display_market_activity,
            inputs=[activity_world_select],
            outputs=[activity_table],
        )

        activity_world_select.change(
            fn=display_market_activity,
            inputs=[activity_world_select],
            outputs=[activity_table],
        )

        # 自動刷新開關
        auto_refresh_activity.change(
            fn=lambda x: gr.Timer(active=x),
            inputs=[auto_refresh_activity],
            outputs=[activity_timer],
        )

        # 計時器觸發刷新
        activity_timer.tick(
            fn=display_market_activity,
            inputs=[activity_world_select],
            outputs=[activity_table],
        )


def _build_watchlist_tab(watchlist_state) -> None:
    """建立監看清單頁籤."""
    with gr.TabItem("監看清單"):
        if USE_BROWSER_STATE:
            gr.Markdown("""
            把想追蹤的物品加到清單，設定目標價格，低於目標時會提示你。
            資料儲存在你的瀏覽器，不同裝置或瀏覽器的清單是獨立的。
            """)
        else:
            gr.Markdown("""
            把想追蹤的物品加到清單，設定目標價格，低於目標時會提示你。
            注意：關閉網頁後清單會清空。
            """)

        with gr.Row():
            with gr.Column(scale=2):
                list_search = gr.Textbox(
                    label="搜尋物品",
                    placeholder="輸入物品名稱",
                )
                list_item_dropdown = gr.Dropdown(
                    label="選擇物品",
                    choices=[],
                )
            with gr.Column(scale=1):
                target_price_input = gr.Number(
                    label="目標價格 (Gil)",
                    value=0,
                )
                add_btn = gr.Button("加入清單", variant="primary")

        add_status = gr.Markdown("")

        with gr.Row():
            remove_id_input = gr.Number(label="要移除的物品 ID")
            remove_btn = gr.Button("移除物品", variant="secondary")

        with gr.Row():
            refresh_list_btn = gr.Button("重新整理清單")
            auto_refresh_list = gr.Checkbox(
                label="自動刷新 (60秒)",
                value=False,
            )

        watchlist_table = gr.Dataframe(
            headers=[
                "物品 ID", "物品名稱", "目標價格", "當前最低價", "狀態",
            ],
            interactive=False,
        )

        # 自動刷新計時器
        watchlist_timer = gr.Timer(value=60, active=False)

        # 事件綁定
        list_search.change(
            fn=search_and_display,
            inputs=[list_search],
            outputs=[list_item_dropdown, gr.State(), gr.State()],
        )

        add_btn.click(
            fn=add_item_to_list,
            inputs=[list_item_dropdown, target_price_input, watchlist_state],
            outputs=[add_status, watchlist_table, watchlist_state],
        )

        remove_btn.click(
            fn=remove_item_from_list,
            inputs=[remove_id_input, watchlist_state],
            outputs=[add_status, watchlist_table, watchlist_state],
        )

        refresh_list_btn.click(
            fn=refresh_watchlist_with_notify,
            inputs=[watchlist_state],
            outputs=[watchlist_table],
        )

        # 自動刷新開關
        auto_refresh_list.change(
            fn=lambda x: gr.Timer(active=x),
            inputs=[auto_refresh_list],
            outputs=[watchlist_timer],
        )

        # 計時器觸發刷新
        watchlist_timer.tick(
            fn=refresh_watchlist_with_notify,
            inputs=[watchlist_state],
            outputs=[watchlist_table],
        )


def _build_tax_tab() -> None:
    """建立稅率資訊頁籤."""
    with gr.TabItem("稅率資訊"):
        gr.Markdown("""
        各城市的市場稅率，賣東西前可以先看看哪邊稅比較低。
        """)
        tax_world_select = gr.Dropdown(
            label="選擇伺服器",
            choices=["全部伺服器"] + WORLD_NAMES,
            value="全部伺服器",
        )
        refresh_tax_btn = gr.Button("重新整理", variant="primary")
        tax_table = gr.Dataframe(interactive=False)

        # 事件綁定
        refresh_tax_btn.click(
            fn=display_tax_rates,
            inputs=[tax_world_select],
            outputs=[tax_table],
        )

        tax_world_select.change(
            fn=display_tax_rates,
            inputs=[tax_world_select],
            outputs=[tax_table],
        )


def _build_stats_tab() -> None:
    """建立統計資訊頁籤."""
    with gr.TabItem("上傳統計"):
        gr.Markdown("""
        各伺服器玩家上傳市場資料的次數。上傳越多，這裡的價格資訊就越準。
        """)
        refresh_stats_btn = gr.Button("重新整理", variant="primary")
        with gr.Row():
            stats_table = gr.Dataframe(interactive=False)
            stats_chart = gr.Plot()

        # 事件綁定
        refresh_stats_btn.click(
            fn=display_upload_stats,
            outputs=[stats_table, stats_chart],
        )


def _build_ai_tab() -> None:
    """建立 AI 分析頁籤."""
    with gr.TabItem("AI 分析"):
        gr.Markdown("""
        分析物品價格趨勢、跨服套利機會。
        輸入你的 HuggingFace Token 可啟用 AI 買賣建議。
        """)

        with gr.Row():
            with gr.Column(scale=2):
                ai_search_input = gr.Textbox(
                    label="搜尋物品",
                    placeholder="輸入物品名稱或 ID",
                    lines=1,
                )
                ai_item_dropdown = gr.Dropdown(
                    label="選擇物品",
                    choices=[
                        (name, item_id)
                        for name, item_id in POPULAR_ITEMS.items()
                    ],
                    interactive=True,
                )

            with gr.Column(scale=1):
                hf_token_input = gr.Textbox(
                    label="HuggingFace Token（選填）",
                    placeholder="hf_xxxx...",
                    type="password",
                    lines=1,
                )
                gr.Markdown(
                    "[免費申請 Token](https://huggingface.co/settings/tokens)",
                    elem_classes=["small-text"],
                )
                analyze_btn = gr.Button("開始分析", variant="primary")
                summary_btn = gr.Button("市場摘要", variant="secondary")

        ai_result = gr.Markdown("")

        # 事件綁定
        ai_search_input.change(
            fn=search_and_display,
            inputs=[ai_search_input],
            outputs=[ai_item_dropdown, gr.State(), gr.State()],
        )

        def run_ai_analysis(item_selection, user_token):
            """執行 AI 分析."""
            if not item_selection:
                return "請先選擇一個物品"
            # item_selection 是 (name, id) tuple 或單純的 id
            if isinstance(item_selection, tuple):
                item_id = item_selection[1]
            else:
                item_id = item_selection
            return analyze_item_with_ai(int(item_id), user_token)

        analyze_btn.click(
            fn=run_ai_analysis,
            inputs=[ai_item_dropdown, hf_token_input],
            outputs=[ai_result],
        )

        summary_btn.click(
            fn=get_market_summary,
            outputs=[ai_result],
        )


def _build_changelog_tab() -> None:
    """建立更新紀錄頁籤."""
    with gr.TabItem("更新紀錄"):
        gr.Markdown("""
### v1.3.0 (2024-12)
- 改用 WebSocket 驅動實時更新
- 首次查詢用 REST API，之後用 WebSocket 緩存
- 自動刷新改為 5 秒（使用緩存時幾乎無延遲）
- 物品資訊與市場數據並行請求

### v1.2.0 (2024-12)
- 新增 AI 分析功能
- 支援跨服套利判斷
- 手機版面優化

### v1.1.0 (2024-12)
- 新增監看清單功能
- 支援設定目標價格提醒
- 資料儲存於瀏覽器 LocalStorage

### v1.0.0 (2024-12)
- 首次發布
- 支援繁體中文搜尋物品
- 市場價格查詢、交易紀錄
- 跨伺服器比價
- 稅率資訊、上傳統計

---
資料來源: [Universalis API](https://universalis.app/)
        """)


if __name__ == "__main__":
    # 啟動 WebSocket 連線（背景執行）
    print("啟動 WebSocket 連線...")
    ws_client = start_websocket()

    # 訂閱陸行鳥資料中心的所有伺服器更新
    from src.config import WORLDS
    for world_id in WORLDS.keys():
        ws_client.subscribe("listings/add", world_id)
        ws_client.subscribe("sales/add", world_id)
    print("已訂閱陸行鳥資料中心的市場更新")

    application = create_app()
    application.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )

