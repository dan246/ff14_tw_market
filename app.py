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
from src.crafting import (
    calculate_crafting_cost,
    format_crafting_result,
    get_profitable_items,
    CRAFT_TYPES,
)
from src.shopping import (
    parse_shopping_list,
    resolve_item_ids,
    calculate_shopping_cost,
    format_shopping_result,
    get_retainer_suggestions,
    format_retainer_suggestions,
)
from src.collectables import (
    get_eorzea_time_str,
    get_current_collectables,
    format_collectables_table,
    format_appraisers_table,
    format_custom_delivery_table,
    refresh_collectables_data,
    GATHERING_JOBS,
)
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
            _build_crafting_tab()
            _build_shopping_tab()
            _build_collectables_tab()
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


def _build_crafting_tab() -> None:
    """建立製作利潤頁籤."""
    with gr.TabItem("製作利潤"):
        gr.Markdown("""
        計算製作物品的成本與利潤，找出最賺錢的製作物品。
        支援遞迴計算材料成本（比較買材料 vs 自己做哪個便宜）。
        """)

        with gr.Tabs():
            # 單品利潤計算
            with gr.TabItem("利潤計算"):
                with gr.Row():
                    with gr.Column(scale=2):
                        craft_search_input = gr.Textbox(
                            label="搜尋物品",
                            placeholder="輸入要製作的物品名稱",
                            lines=1,
                        )
                        craft_item_dropdown = gr.Dropdown(
                            label="選擇物品",
                            choices=[
                                (name, item_id)
                                for name, item_id in POPULAR_ITEMS.items()
                            ],
                            interactive=True,
                        )

                    with gr.Column(scale=1):
                        craft_world_select = gr.Dropdown(
                            label="選擇伺服器",
                            choices=["全部伺服器"] + WORLD_NAMES,
                            value="全部伺服器",
                        )
                        craft_recursive = gr.Checkbox(
                            label="遞迴計算材料成本",
                            value=True,
                        )
                        calc_profit_btn = gr.Button(
                            "計算利潤",
                            variant="primary",
                        )

                craft_result = gr.Markdown("")

                # 事件綁定
                craft_search_input.change(
                    fn=search_and_display,
                    inputs=[craft_search_input],
                    outputs=[craft_item_dropdown, gr.State(), gr.State()],
                )

                def run_profit_calc(item_selection, world, recursive):
                    """執行利潤計算."""
                    if not item_selection:
                        return "請先選擇一個物品"

                    # item_selection 是 (name, id) tuple 或單純的 id
                    if isinstance(item_selection, tuple):
                        item_id = item_selection[1]
                    else:
                        item_id = item_selection

                    if world == "全部伺服器":
                        world = None

                    result = calculate_crafting_cost(
                        int(item_id), world, recursive=recursive
                    )
                    return format_crafting_result(result)

                calc_profit_btn.click(
                    fn=run_profit_calc,
                    inputs=[craft_item_dropdown, craft_world_select, craft_recursive],
                    outputs=[craft_result],
                )

            # 賺錢排行榜
            with gr.TabItem("賺錢排行榜"):
                gr.Markdown("""
                掃描最近交易的物品，找出利潤最高的可製作物品。
                """)

                with gr.Row():
                    rank_world_select = gr.Dropdown(
                        label="選擇伺服器",
                        choices=["全部伺服器"] + WORLD_NAMES,
                        value="全部伺服器",
                    )
                    rank_craft_type = gr.Dropdown(
                        label="職業篩選",
                        choices=[("全部職業", -1)] + [
                            (name, cid) for cid, name in CRAFT_TYPES.items()
                        ],
                        value=-1,
                    )
                    refresh_rank_btn = gr.Button(
                        "刷新排行榜",
                        variant="primary",
                    )

                rank_status = gr.Markdown("點擊「刷新排行榜」開始掃描...")

                rank_table = gr.Dataframe(
                    headers=[
                        "物品名稱", "職業", "製作成本", "市場價(HQ)",
                        "利潤", "利潤率", "推薦",
                    ],
                    interactive=False,
                )

                def run_rank_scan(world, craft_type_selection):
                    """執行排行榜掃描."""
                    if world == "全部伺服器":
                        world = None

                    # craft_type_selection 是 (name, id) tuple 或單純的 id
                    if isinstance(craft_type_selection, tuple):
                        craft_type = craft_type_selection[1]
                    else:
                        craft_type = craft_type_selection

                    if craft_type == -1:
                        craft_type = None

                    results = get_profitable_items(world, craft_type, limit=20)

                    if not results:
                        return "沒有找到有利潤的製作物品", []

                    # 轉換為表格資料
                    table_data = []
                    for r in results:
                        # 推薦圖示
                        rate = r.get("profit_rate_hq", 0)
                        if rate >= 20:
                            rec = "推薦"
                        elif rate >= 10:
                            rec = "可考慮"
                        else:
                            rec = "一般"

                        table_data.append([
                            r.get("item_name", ""),
                            r.get("craft_type", ""),
                            f"{r.get('craft_cost', 0):,}",
                            f"{r.get('market_price_hq', 0):,}",
                            f"{r.get('profit_hq', 0):,}",
                            f"{r.get('profit_rate_hq', 0):+.1f}%",
                            rec,
                        ])

                    return f"找到 {len(results)} 個有利潤的物品", table_data

                refresh_rank_btn.click(
                    fn=run_rank_scan,
                    inputs=[rank_world_select, rank_craft_type],
                    outputs=[rank_status, rank_table],
                )


def _build_shopping_tab() -> None:
    """建立購物清單與雇員銷售頁籤."""
    with gr.TabItem("購物助手"):
        gr.Markdown("""
        購物清單計算最佳購買伺服器，雇員建議找出最值得賣的物品。
        """)

        with gr.Tabs():
            # 購物清單
            with gr.TabItem("購物清單"):
                gr.Markdown("""
                輸入想買的物品，自動計算各伺服器總價，找出最便宜的購買方案。

                **格式**: 每行一個物品，可加數量（例如: `黃金礦 x10`）
                """)

                with gr.Row():
                    with gr.Column(scale=2):
                        shopping_input = gr.Textbox(
                            label="購物清單",
                            placeholder="黃金礦 x5\n白銀礦 x10\n祕銀錠 3",
                            lines=8,
                        )
                    with gr.Column(scale=1):
                        gr.Markdown("**範例格式:**\n- 物品名稱\n- 物品名稱 x數量\n- 物品名稱 *數量\n- 物品ID")
                        calc_shopping_btn = gr.Button(
                            "計算最佳購買方案",
                            variant="primary",
                        )

                shopping_result = gr.Markdown("")

                def run_shopping_calc(text):
                    """執行購物清單計算."""
                    if not text or not text.strip():
                        return "請輸入購物清單"

                    # 解析清單
                    items = parse_shopping_list(text)
                    if not items:
                        return "無法解析購物清單，請檢查格式"

                    # 解析物品 ID
                    resolved = resolve_item_ids(items)

                    # 計算成本
                    result = calculate_shopping_cost(resolved)

                    return format_shopping_result(result)

                calc_shopping_btn.click(
                    fn=run_shopping_calc,
                    inputs=[shopping_input],
                    outputs=[shopping_result],
                )

            # 雇員銷售建議
            with gr.TabItem("雇員銷售建議"):
                gr.Markdown("""
                分析市場動態，找出銷售速度快且價格高的物品，幫你決定雇員該賣什麼。
                """)

                with gr.Row():
                    retainer_world_select = gr.Dropdown(
                        label="選擇伺服器",
                        choices=["全部伺服器"] + WORLD_NAMES,
                        value="全部伺服器",
                    )
                    refresh_retainer_btn = gr.Button(
                        "分析銷售建議",
                        variant="primary",
                    )

                retainer_status = gr.Markdown("點擊「分析銷售建議」開始...")
                retainer_result = gr.Markdown("")

                def run_retainer_analysis(world):
                    """執行雇員銷售分析."""
                    if world == "全部伺服器":
                        world = None

                    suggestions = get_retainer_suggestions(world, limit=20)
                    if not suggestions:
                        return "分析完成", "目前沒有找到推薦的銷售物品"

                    return f"找到 {len(suggestions)} 個推薦物品", format_retainer_suggestions(suggestions)

                refresh_retainer_btn.click(
                    fn=run_retainer_analysis,
                    inputs=[retainer_world_select],
                    outputs=[retainer_status, retainer_result],
                )


def _build_collectables_tab() -> None:
    """建立收藏品時間表頁籤."""
    with gr.TabItem("收藏品時間表"):
        gr.Markdown("""
        大地使者（採礦工、園藝工、捕魚人）收藏品採集時間表。
        顯示目前可採集和即將出現的收藏品，包含 ET 時間、地點、工票獎勵、老主顧 NPC 資訊。
        """)

        with gr.Row():
            et_time_display = gr.Markdown("**當前 ET 時間:** 載入中...")
            job_filter_select = gr.Dropdown(
                label="職業篩選",
                choices=[("全部職業", "")] + [
                    (name, name) for name in GATHERING_JOBS.values()
                ],
                value="",
            )
            refresh_coll_btn = gr.Button("重新整理", variant="primary")
            auto_refresh_coll = gr.Checkbox(
                label="自動刷新 (10秒)",
                value=True,
            )

        gr.Markdown("### 目前可採集")
        available_table = gr.Dataframe(
            headers=[
                "物品名稱", "職業", "等級", "地點", "座標",
                "出現時間", "剩餘時間", "工票", "老主顧",
            ],
            interactive=False,
        )

        gr.Markdown("### 即將出現")
        upcoming_table = gr.Dataframe(
            headers=[
                "物品名稱", "職業", "等級", "地點", "座標",
                "出現時間", "等待時間", "工票", "老主顧",
            ],
            interactive=False,
        )

        with gr.Accordion("老主顧位置一覽 (Custom Delivery)", open=False):
            gr.Markdown("""
            **老主顧**是每週可交納收藏品獲得額外獎勵的 NPC：
            """)
            custom_delivery_table = gr.Dataframe(
                headers=["等級範圍", "NPC 名稱", "地點", "座標"],
                value=format_custom_delivery_table(),
                interactive=False,
            )

        with gr.Accordion("收藏品交易員位置一覽", open=False):
            gr.Markdown("""
            **收藏品交易員**可隨時交納收藏品換取工票（無每週限制）：
            """)
            appraiser_table = gr.Dataframe(
                headers=["等級範圍", "NPC 名稱", "地點", "座標"],
                value=format_appraisers_table(),
                interactive=False,
            )

        with gr.Accordion("資料管理", open=False):
            gr.Markdown("""
            資料來源: [FFXIV Teamcraft](https://github.com/ffxiv-teamcraft/ffxiv-teamcraft)

            資料會自動快取 7 天，如果資料過期或需要更新，請點擊下方按鈕。
            """)
            refresh_data_btn = gr.Button("強制刷新資料", variant="secondary")
            refresh_data_status = gr.Markdown("")

        # 自動刷新計時器 (10秒)
        coll_timer = gr.Timer(value=10, active=True)

        def update_collectables(job_filter):
            """更新收藏品資料."""
            if job_filter == "":
                job_filter = None

            et_time = get_eorzea_time_str()
            available, upcoming = get_current_collectables(job_filter)

            available_data = format_collectables_table(available, is_available=True)
            upcoming_data = format_collectables_table(upcoming, is_available=False)

            return (
                f"**當前 ET 時間:** {et_time}",
                available_data,
                upcoming_data,
            )

        def force_refresh_data():
            """強制刷新資料."""
            try:
                refresh_collectables_data()
                return "資料刷新成功！"
            except Exception as e:
                return f"刷新失敗: {e}"

        # 事件綁定
        refresh_coll_btn.click(
            fn=update_collectables,
            inputs=[job_filter_select],
            outputs=[et_time_display, available_table, upcoming_table],
        )

        job_filter_select.change(
            fn=update_collectables,
            inputs=[job_filter_select],
            outputs=[et_time_display, available_table, upcoming_table],
        )

        # 自動刷新開關
        auto_refresh_coll.change(
            fn=lambda x: gr.Timer(active=x),
            inputs=[auto_refresh_coll],
            outputs=[coll_timer],
        )

        # 計時器觸發刷新
        coll_timer.tick(
            fn=update_collectables,
            inputs=[job_filter_select],
            outputs=[et_time_display, available_table, upcoming_table],
        )

        # 強制刷新資料
        refresh_data_btn.click(
            fn=force_refresh_data,
            outputs=[refresh_data_status],
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
### v1.6.1 (2025-01)
- 收藏品時間表新增「老主顧」NPC 資訊
- 顯示對應等級範圍的老主顧名稱與位置座標
- 新增「老主顧位置一覽」快速參考表

### v1.6.0 (2025-01)
- 新增「收藏品時間表」功能
- 顯示大地使者（採礦工、園藝工、捕魚人）收藏品採集時間
- 即時 ET（艾歐澤亞時間）顯示
- 顯示目前可採集和即將出現的收藏品
- 包含採集地點、座標、工票獎勵
- 資料自動快取，支援強制刷新

### v1.5.0 (2024-12)
- 新增「購物助手」功能
- 購物清單：輸入多個物品，計算各伺服器總價，找最便宜的購買方案
- 雇員銷售建議：分析銷售速度與價格，推薦值得上架的物品

### v1.4.0 (2024-12)
- 新增「製作利潤」功能
- 計算製作成本 vs 市場售價
- 遞迴計算材料成本（比較買 vs 自己做）
- 賺錢排行榜：動態掃描最近交易物品
- 職業篩選（木工、鍛冶、裁縫、烹調等）

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

