"""Universalis WebSocket API 實現."""

import asyncio
import threading
import time
from typing import Callable, Optional
from queue import Queue

import bson
import websockets

from .config import DATA_CENTER, WORLD_IDS, WORLDS

# WebSocket 設定
UNIVERSALIS_WS_URL = "wss://universalis.app/api/ws"

# 陸行鳥資料中心的所有伺服器 ID
CHOCOBO_WORLD_IDS = list(WORLDS.keys())


class UniversalisWebSocket:
    """Universalis WebSocket 客戶端."""

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._subscriptions: set = set()
        self._callbacks: dict[str, list[Callable]] = {}
        self._message_queue: Queue = Queue()
        self._connected = False
        # 物品數據緩存: {item_id: {"data": {...}, "timestamp": time}}
        self._item_cache: dict[int, dict] = {}
        # 當前訂閱的物品 ID
        self._watched_items: set[int] = set()

    def start(self):
        """啟動 WebSocket 連線（在背景執行緒中運行）."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 WebSocket 連線."""
        self._running = False
        self._connected = False
        if self._ws and self._loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._ws.close(), self._loop
                ).result(timeout=2)
            except Exception:
                pass
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)

    def _run_event_loop(self):
        """在背景執行緒中運行事件循環."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            print(f"WebSocket 事件循環錯誤: {e}")
        finally:
            self._loop.close()

    async def _connect_and_listen(self):
        """連接並監聽 WebSocket."""
        while self._running:
            try:
                async with websockets.connect(
                    UNIVERSALIS_WS_URL,
                    ping_interval=30,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    print("WebSocket 已連接到 Universalis")

                    # 重新訂閱之前的頻道
                    for channel in self._subscriptions:
                        await self._send_subscribe(channel)

                    # 監聽消息
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_message(message)

            except websockets.exceptions.ConnectionClosed:
                print("WebSocket 連線已關閉，嘗試重新連接...")
            except Exception as e:
                print(f"WebSocket 錯誤: {e}")

            self._connected = False
            if self._running:
                await asyncio.sleep(5)  # 等待後重新連接

    async def _send_subscribe(self, channel: str):
        """發送訂閱消息."""
        if self._ws and self._connected:
            msg = bson.encode({"event": "subscribe", "channel": channel})
            await self._ws.send(msg)
            print(f"已訂閱頻道: {channel}")

    async def _send_unsubscribe(self, channel: str):
        """發送取消訂閱消息."""
        if self._ws and self._connected:
            msg = bson.encode({"event": "unsubscribe", "channel": channel})
            await self._ws.send(msg)
            print(f"已取消訂閱頻道: {channel}")

    async def _handle_message(self, message: bytes):
        """處理收到的消息."""
        try:
            data = bson.decode(message)
            event = data.get("event", "")
            item_id = data.get("item")
            world_id = data.get("world")

            # 檢查是否為陸行鳥資料中心的伺服器
            if world_id and world_id not in CHOCOBO_WORLD_IDS:
                return  # 忽略其他資料中心的消息

            # 如果是我們關注的物品，更新緩存
            if item_id and item_id in self._watched_items:
                self._item_cache[item_id] = {
                    "data": data,
                    "timestamp": time.time(),
                    "event": event,
                    "world": world_id,
                }

            # 放入消息佇列
            self._message_queue.put(data)

            # 呼叫回調
            if event in self._callbacks:
                for callback in self._callbacks[event]:
                    try:
                        callback(data)
                    except Exception as e:
                        print(f"回調錯誤: {e}")

        except Exception as e:
            print(f"處理消息錯誤: {e}")

    def subscribe(self, channel: str, world_id: int = None):
        """訂閱頻道.

        Args:
            channel: 頻道名稱 (listings/add, listings/remove, sales/add)
            world_id: 可選的伺服器 ID，用於過濾
        """
        if world_id:
            full_channel = f"{channel}{{world={world_id}}}"
        else:
            full_channel = channel

        self._subscriptions.add(full_channel)

        if self._loop and self._connected:
            asyncio.run_coroutine_threadsafe(
                self._send_subscribe(full_channel), self._loop
            )

    def subscribe_item(self, item_id: int, world_or_dc: str = None):
        """訂閱特定物品的更新.

        Args:
            item_id: 物品 ID
            world_or_dc: 伺服器或資料中心名稱
        """
        # 訂閱該物品的上架和銷售更新
        if world_or_dc and world_or_dc != "全部伺服器":
            world_id = WORLD_IDS.get(world_or_dc)
            if world_id:
                self.subscribe("listings/add", world_id)
                self.subscribe("sales/add", world_id)
        else:
            # 訂閱陸行鳥資料中心所有伺服器
            for world_id in CHOCOBO_WORLD_IDS:
                self.subscribe("listings/add", world_id)
                self.subscribe("sales/add", world_id)

    def unsubscribe(self, channel: str, world_id: int = None):
        """取消訂閱頻道."""
        if world_id:
            full_channel = f"{channel}{{world={world_id}}}"
        else:
            full_channel = channel

        self._subscriptions.discard(full_channel)

        if self._loop and self._connected:
            asyncio.run_coroutine_threadsafe(
                self._send_unsubscribe(full_channel), self._loop
            )

    def on_event(self, event: str, callback: Callable):
        """註冊事件回調.

        Args:
            event: 事件名稱 (listings/add, listings/remove, sales/add)
            callback: 回調函數，接收事件數據
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def get_latest_messages(self, limit: int = 10) -> list:
        """取得最新的消息.

        Args:
            limit: 最大數量

        Returns:
            消息列表
        """
        messages = []
        while not self._message_queue.empty() and len(messages) < limit:
            try:
                messages.append(self._message_queue.get_nowait())
            except:
                break
        return messages

    def is_connected(self) -> bool:
        """檢查是否已連接."""
        return self._connected

    def watch_item(self, item_id: int):
        """開始關注某個物品的更新.

        Args:
            item_id: 物品 ID
        """
        self._watched_items.add(item_id)

    def unwatch_item(self, item_id: int):
        """停止關注某個物品."""
        self._watched_items.discard(item_id)
        self._item_cache.pop(item_id, None)

    def get_cached_data(self, item_id: int) -> Optional[dict]:
        """取得物品的緩存數據.

        Args:
            item_id: 物品 ID

        Returns:
            緩存數據，如果沒有則返回 None
        """
        return self._item_cache.get(item_id)

    def has_update(self, item_id: int, since: float = 0) -> bool:
        """檢查物品是否有新更新.

        Args:
            item_id: 物品 ID
            since: 時間戳，檢查此時間之後是否有更新

        Returns:
            是否有新更新
        """
        cache = self._item_cache.get(item_id)
        if cache and cache["timestamp"] > since:
            return True
        return False

    def clear_cache(self, item_id: int = None):
        """清除緩存.

        Args:
            item_id: 物品 ID，如果為 None 則清除所有
        """
        if item_id:
            self._item_cache.pop(item_id, None)
        else:
            self._item_cache.clear()


# 全域 WebSocket 客戶端實例
_ws_client: Optional[UniversalisWebSocket] = None


def get_ws_client() -> UniversalisWebSocket:
    """取得全域 WebSocket 客戶端."""
    global _ws_client
    if _ws_client is None:
        _ws_client = UniversalisWebSocket()
    return _ws_client


def start_websocket():
    """啟動全域 WebSocket 連線."""
    client = get_ws_client()
    client.start()
    return client


def stop_websocket():
    """停止全域 WebSocket 連線."""
    global _ws_client
    if _ws_client:
        _ws_client.stop()
        _ws_client = None
