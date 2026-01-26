---
title: FF14 繁中服市場板
emoji: 🎮
colorFrom: yellow
colorTo: purple
sdk: gradio
sdk_version: 5.9.1
app_file: app.py
pinned: false
license: mit
tags:
  - ffxiv
  - final-fantasy-xiv
  - market-analysis
  - data-visualization
  - universalis
  - gradio
short_description: FF14 繁中服市場價格查詢與跨服比價工具
---

# FF14 繁中服市場板查詢工具

使用 [Universalis API](https://universalis.app/) 查詢繁體中文伺服器（陸行鳥資料中心）的市場數據。

[![Hugging Face Space](https://img.shields.io/badge/🤗%20Hugging%20Face-Space-blue)](https://huggingface.co/spaces/Daniel246/ff14_tw_market)

## 功能

### 市場查詢
- **物品搜尋** - 支援繁體中文、英文名稱、物品 ID，或直接貼上 Universalis 網址
- **物品分類篩選** - 大分類（武器/防具/素材等）+ 子分類下拉選單，支援分頁瀏覽
- **物品資訊卡** - 顯示獲取方式、用途、裝備屬性、外部連結
- **市場查詢** - 查看當前上架價格（NQ/HQ 分離）
- **交易歷史** - 查看近期成交記錄
- **價格走勢** - 互動式價格歷史圖表，自動標註異常價格
- **跨服比價** - 比較所有繁中服伺服器的價格差異
- **雇員篩選** - 可依雇員名稱篩選上架物品
- **自動刷新** - 5 秒自動更新（使用 WebSocket 緩存）

### 製作利潤
- **利潤計算** - 計算製作成本 vs 市場售價，含 3% 市場稅率
- **遞迴成本計算** - 自動比較「買材料」vs「自己製作材料」哪個便宜
- **賺錢排行榜** - 掃描最近交易物品，找出利潤最高的製作品
- **職業篩選** - 可依職業（木工、鍛冶、裁縫、烹調等）篩選

### 購物助手
- **購物清單** - 輸入多個物品，計算各伺服器總價，找出最便宜的購買方案
- **雇員銷售建議** - 分析銷售速度與價格，推薦值得上架的物品

### 即時追蹤
- **即時交易追蹤** - 顯示繁中服正在發生的市場交易
- **WebSocket 推送** - 數據由 Universalis 即時推送，無需手動刷新
- **自動更新** - 3 秒自動刷新，顯示最新上架和售出
- **資料流狀態** - 顯示各伺服器資料更新時間，以顏色標示新鮮度

### 其他功能
- **市場動態** - 查看最近有人上架或更新價格的物品
- **AI 分析** - 價格趨勢分析、跨服套利機會（需輸入 HuggingFace Token）
- **監看清單** - 追蹤物品價格，設定目標價格提醒（資料儲存於瀏覽器）
- **稅率資訊** - 查看各城市的市場稅率
- **上傳統計** - 查看各伺服器的數據上傳統計

## 支援伺服器

陸行鳥資料中心（繁中服）：

| 伺服器 | World ID |
|--------|----------|
| 伊弗利特 | 4028 |
| 迦樓羅 | 4029 |
| 利維坦 | 4030 |
| 鳳凰 | 4031 |
| 奧汀 | 4032 |
| 巴哈姆特 | 4033 |
| 拉姆 | 4034 |
| 泰坦 | 4035 |

## 本地運行

```bash
# Clone 專案
git clone https://github.com/dan246/ff14_tw_market.git
cd ff14_tw_market

# 安裝依賴
pip install -r requirements.txt

# 運行應用
python app.py
```

在瀏覽器開啟 http://localhost:7860

## 技術架構

| 技術 | 用途 |
|------|------|
| **Gradio 5.x** | Web 介面框架（支援 BrowserState） |
| **WebSocket** | 實時市場數據更新 |
| **Universalis API** | FF14 市場數據 |
| **XIVAPI / Cafemaker** | FF14 物品與配方資料 |
| **Plotly** | 互動式圖表 |
| **Pandas** | 數據處理 |
| **aiohttp** | 異步 HTTP 請求 |

## 專案結構

```
ff14_tw_market/
├── app.py              # 主程式入口
├── requirements.txt    # 依賴套件
├── data/               # 本地資料快取
└── src/
    ├── api.py          # API 請求封裝
    ├── charts.py       # 圖表繪製
    ├── config.py       # 設定與常數（含物品分類定義）
    ├── crafting.py     # 製作利潤計算
    ├── display.py      # 顯示格式化
    ├── shopping.py     # 購物清單與雇員建議
    ├── collectables.py # 收藏品時間表
    ├── watchlist.py    # 監看清單
    ├── websocket_api.py # WebSocket 連線
    ├── ai_analysis.py  # AI 分析功能
    ├── styles.py       # 自訂 CSS 樣式
    └── changelog.py    # 更新紀錄
```

## 更新紀錄

### v1.8.0 (2025-01)
- 新增「物品分類篩選」功能（大分類 + 子分類 + 分頁瀏覽）
- 新增「物品資訊卡」側欄（獲取方式/用途/裝備屬性/外部連結）
- 價格走勢圖新增異常值標註（⚠️ 異常低價/高價）
- 程式碼重構：CSS 和更新紀錄獨立為模組

### v1.7.2 (2025-01)
- 即時追蹤新增「資料流狀態」圖表
- 顯示各伺服器最後收到資料的時間
- 以顏色標示資料新鮮度（綠/黃/橙/紅）

### v1.7.1 (2025-01)
- 新增「即時追蹤」功能
- 顯示繁中服正在發生的市場交易（上架、售出）
- 數據由 Universalis WebSocket 即時推送

### v1.7.0 (2025-01)
- 介面美化：採用 Gradio Soft 主題
- 新增金色漸層頁首設計
- 圖表配色優化

### v1.6.x (2025-01)
- 新增「收藏品時間表」功能
- 新增「老主顧」NPC 資訊

### v1.5.0 (2024-12)
- 新增「購物助手」功能

### v1.4.0 (2024-12)
- 新增「製作利潤」功能

### v1.3.0 (2024-12)
- 改用 WebSocket 驅動實時更新

### v1.2.0 (2024-12)
- 新增 AI 分析功能

### v1.1.0 (2024-12)
- 新增監看清單功能

### v1.0.0 (2024-12)
- 首次發布

## 授權

MIT License

## 致謝

- [Universalis](https://universalis.app/) - 提供市場數據 API
- [XIVAPI](https://xivapi.com/) - 提供物品資料 API
- [Cafemaker](https://cafemaker.wakingsands.com/) - 提供繁中物品資料
- [FINAL FANTASY XIV](https://www.ffxiv.com.tw/) - SQUARE ENIX
