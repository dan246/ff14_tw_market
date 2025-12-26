"""AI 價格分析模組 - 使用 HuggingFace Inference API."""

import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv 不是必須的，HuggingFace Spaces 會自動載入環境變數
    pass

from huggingface_hub import InferenceClient

from opencc import OpenCC

from .api import get_market_data, get_item_info
from .config import DATA_CENTER, WORLDS

# 簡體轉繁體轉換器
_s2t_converter = OpenCC('s2t')

# 使用免費的 LLM 模型做分析
ANALYSIS_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
BACKUP_MODEL = "Qwen/Qwen2.5-72B-Instruct"


def _get_client(user_token: str = None) -> Optional[InferenceClient]:
    """取得 HuggingFace Inference Client.

    Args:
        user_token: 使用者提供的 HF token，如果沒有則不使用 AI
    """
    token = user_token.strip() if user_token else None
    if not token:
        return None
    return InferenceClient(token=token)


def _format_price(price: int) -> str:
    """格式化價格顯示."""
    if price >= 1000000:
        return f"{price / 1000000:.1f}M"
    if price >= 1000:
        return f"{price / 1000:.1f}K"
    return str(price)


def _calculate_statistics(prices: list) -> dict:
    """計算價格統計資料."""
    if not prices:
        return {}

    prices_sorted = sorted(prices)
    n = len(prices_sorted)

    return {
        "min": prices_sorted[0],
        "max": prices_sorted[-1],
        "avg": sum(prices) / n,
        "median": prices_sorted[n // 2],
        "count": n,
        "spread": prices_sorted[-1] - prices_sorted[0],
        "spread_pct": ((prices_sorted[-1] - prices_sorted[0]) / prices_sorted[0] * 100) if prices_sorted[0] > 0 else 0,
    }


def _analyze_price_trend(history: list) -> dict:
    """分析價格趨勢."""
    if len(history) < 3:
        return {"trend": "資料不足", "change_pct": 0}

    # 按時間排序（舊到新）
    sorted_history = sorted(history, key=lambda x: x.get("timestamp", 0))

    # 取最近的價格和較早的價格比較
    recent_prices = [h["pricePerUnit"] for h in sorted_history[-5:]]
    older_prices = [h["pricePerUnit"] for h in sorted_history[:5]]

    recent_avg = sum(recent_prices) / len(recent_prices)
    older_avg = sum(older_prices) / len(older_prices)

    if older_avg == 0:
        return {"trend": "無法計算", "change_pct": 0}

    change_pct = ((recent_avg - older_avg) / older_avg) * 100

    if change_pct > 10:
        trend = "上漲 📈"
    elif change_pct < -10:
        trend = "下跌 📉"
    else:
        trend = "穩定 ➡️"

    return {"trend": trend, "change_pct": round(change_pct, 1)}


def _find_arbitrage_opportunities(item_id: int) -> list:
    """尋找跨服套利機會."""
    opportunities = []
    world_prices = {}

    # 取得各伺服器價格
    for _, world_name in WORLDS.items():
        try:
            data = get_market_data(item_id, world_name)
            listings = data.get("listings", [])
            if listings:
                min_price = min(l["pricePerUnit"] for l in listings)
                world_prices[world_name] = min_price
        except Exception:
            continue

    if len(world_prices) < 2:
        return []

    # 找出最低和最高價差
    min_world = min(world_prices, key=world_prices.get)
    max_world = max(world_prices, key=world_prices.get)

    min_price = world_prices[min_world]
    max_price = world_prices[max_world]

    if min_price > 0:
        profit_pct = ((max_price - min_price) / min_price) * 100
        # 只要有 5% 以上價差就顯示（玩家自己判斷是否值得）
        if profit_pct >= 5:
            opportunities.append({
                "buy_world": min_world,
                "buy_price": min_price,
                "sell_world": max_world,
                "sell_price": max_price,
                "profit_pct": round(profit_pct, 1),
                "all_prices": world_prices,  # 附上所有伺服器價格
            })

    return opportunities


def analyze_item_with_ai(item_id: int, user_token: str = None) -> str:
    """分析物品價格，可選擇使用 AI 建議.

    Args:
        item_id: 物品 ID
        user_token: 使用者的 HuggingFace token（可選）

    Returns:
        分析結果文字
    """
    # 取得物品資訊
    item_info = get_item_info(item_id)
    item_name = item_info.get("Name", f"物品 {item_id}")

    # 取得市場數據
    market_data = get_market_data(item_id, DATA_CENTER)
    if not market_data:
        return f"❌ 無法取得 {item_name} 的市場資料"

    listings = market_data.get("listings", [])
    history = market_data.get("recentHistory", [])

    if not listings:
        return f"❌ {item_name} 目前沒有上架"

    # 計算統計
    nq_prices = [l["pricePerUnit"] for l in listings if not l.get("hq")]
    hq_prices = [l["pricePerUnit"] for l in listings if l.get("hq")]

    nq_stats = _calculate_statistics(nq_prices)
    hq_stats = _calculate_statistics(hq_prices)

    # 分析趨勢
    trend_info = _analyze_price_trend(history)

    # 尋找套利機會
    arbitrage = _find_arbitrage_opportunities(item_id)

    # 組合分析報告
    report = f"""## 📊 {item_name} 價格分析

### 當前價格統計
"""

    if nq_stats:
        report += f"""
**NQ (普通品質)**
- 最低價: {_format_price(nq_stats['min'])} Gil
- 最高價: {_format_price(nq_stats['max'])} Gil
- 平均價: {_format_price(int(nq_stats['avg']))} Gil
- 上架數: {nq_stats['count']} 件
- 價差: {nq_stats['spread_pct']:.1f}%
"""

    if hq_stats:
        report += f"""
**HQ (高品質)**
- 最低價: {_format_price(hq_stats['min'])} Gil
- 最高價: {_format_price(hq_stats['max'])} Gil
- 平均價: {_format_price(int(hq_stats['avg']))} Gil
- 上架數: {hq_stats['count']} 件
- 價差: {hq_stats['spread_pct']:.1f}%
"""

    report += f"""
### 價格趨勢
- 趨勢: {trend_info['trend']}
- 變化幅度: {trend_info['change_pct']:+.1f}%
"""

    if arbitrage:
        opp = arbitrage[0]
        all_prices = opp.get('all_prices', {})

        # 按價格排序顯示所有伺服器
        sorted_prices = sorted(all_prices.items(), key=lambda x: x[1])

        report += f"""
### 💰 跨服套利機會
**買入:** {opp['buy_world']} ({_format_price(opp['buy_price'])} Gil) ← 最低價
**賣出:** {opp['sell_world']} ({_format_price(opp['sell_price'])} Gil) ← 最高價
**價差:** {opp['profit_pct']}%

**各伺服器價格（由低到高）:**
"""
        for world, price in sorted_prices:
            marker = "🟢" if world == opp['buy_world'] else ("🔴" if world == opp['sell_world'] else "⚪")
            report += f"- {marker} {world}: {_format_price(price)} Gil\n"
    else:
        report += """
### 跨服套利
目前各伺服器價差小於 5%，沒有明顯套利機會。
"""

    # 嘗試用 AI 生成建議（需要使用者提供 token）
    client = _get_client(user_token)
    if client:
        try:
            ai_suggestion = _get_ai_suggestion(client, item_name, nq_stats, hq_stats, trend_info, arbitrage)
            if ai_suggestion:
                report += f"""
### 🤖 AI 建議
{ai_suggestion}
"""
        except Exception:
            report += """
### 🤖 AI 建議
（AI 分析暫時無法使用，請檢查 token 是否正確）
"""
    else:
        report += """
### 🤖 AI 建議
輸入你的 HuggingFace Token 即可啟用 AI 建議功能。
[免費申請 Token](https://huggingface.co/settings/tokens)
"""

    return report


def _get_ai_suggestion(
    client: InferenceClient,
    item_name: str,
    nq_stats: dict,
    hq_stats: dict,
    trend_info: dict,
    arbitrage: list
) -> str:
    """使用 AI 生成買賣建議."""

    # 準備提示詞
    context = f"""你是 FF14 市場板專家。根據以下資料，用繁體中文給出簡短的買賣建議（2-3 句話）。

物品: {item_name}
價格趨勢: {trend_info['trend']}，變化 {trend_info['change_pct']:+.1f}%
"""

    if nq_stats:
        context += f"NQ 最低價: {nq_stats['min']} Gil，上架 {nq_stats['count']} 件\n"
    if hq_stats:
        context += f"HQ 最低價: {hq_stats['min']} Gil，上架 {hq_stats['count']} 件\n"
    if arbitrage:
        opp = arbitrage[0]
        context += f"套利機會: {opp['buy_world']} → {opp['sell_world']}，利潤 {opp['profit_pct']}%\n"

    context += "\n請給出買賣建議："

    try:
        response = client.chat_completion(
            model=ANALYSIS_MODEL,
            messages=[
                {"role": "user", "content": context}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        # 強制轉換為繁體中文
        return _s2t_converter.convert(result)
    except Exception:
        # 嘗試備用模型
        try:
            response = client.chat_completion(
                model=BACKUP_MODEL,
                messages=[
                    {"role": "user", "content": context}
                ],
                max_tokens=150,
                temperature=0.7,
            )
            result = response.choices[0].message.content.strip()
            # 強制轉換為繁體中文
            return _s2t_converter.convert(result)
        except Exception:
            return None


def get_market_summary(world_or_dc: str = None) -> str:
    """取得市場整體摘要.

    Args:
        world_or_dc: 伺服器或資料中心

    Returns:
        市場摘要文字
    """
    from .api import get_recent_activity

    if world_or_dc is None or world_or_dc == "全部伺服器":
        world_or_dc = DATA_CENTER

    activity = get_recent_activity(world_or_dc, limit=10)

    if not activity:
        return "❌ 無法取得市場動態資料"

    summary = f"""## 📈 {world_or_dc} 市場摘要

### 最近活躍的物品
"""

    for item in activity[:5]:
        nq_price = f"{_format_price(item['nq_min'])}" if item['nq_min'] else "無"
        hq_price = f"{_format_price(item['hq_min'])}" if item['hq_min'] else "無"
        summary += f"- **{item['name']}** - NQ: {nq_price} / HQ: {hq_price} ({item['listing_count']} 件上架)\n"

    return summary
