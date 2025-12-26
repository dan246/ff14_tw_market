---
title: FF14 繁中服市場板
emoji: 🎮
colorFrom: yellow
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# FF14 繁中服市場板查詢工具

使用 [Universalis API](https://universalis.app/) 查詢繁體中文伺服器（陸行鳥資料中心）的市場數據。

## 功能

- 🔍 **物品搜尋** - 搜尋 FF14 中的任何物品
- 💰 **市場查詢** - 查看當前上架價格（NQ/HQ 分離）
- 📜 **交易歷史** - 查看近期成交記錄
- 📈 **價格走勢** - 視覺化價格歷史圖表
- 🌐 **跨服比價** - 比較所有繁中服伺服器的價格
- 📝 **監看清單** - 追蹤物品價格，設定目標價格
- 💵 **稅率資訊** - 查看各城市的市場稅率
- 📊 **上傳統計** - 查看各伺服器的數據上傳統計

## 支援伺服器

陸行鳥資料中心（繁中服）：
- 伊弗利特
- 迦樓羅
- 利維坦
- 鳳凰
- 奧汀
- 巴哈姆特
- 拉姆
- 泰坦

## 本地運行

```bash
# 安裝依賴
pip install -r requirements.txt

# 運行應用
python app.py
```

然後在瀏覽器開啟 http://localhost:7860

## 技術

- **Gradio** - Web 介面框架
- **Universalis API** - FF14 市場數據 API
- **XIVAPI** - FF14 物品資料 API
- **Plotly** - 互動式圖表
- **Pandas** - 數據處理

## 授權

MIT License

## 致謝

- [Universalis](https://universalis.app/) - 提供市場數據 API
- [XIVAPI](https://xivapi.com/) - 提供物品資料 API
- [FINAL FANTASY XIV](https://www.ffxiv.com.tw/) - SQUARE ENIX
