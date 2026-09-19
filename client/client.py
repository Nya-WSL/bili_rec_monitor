# client.py
import websockets
import asyncio
import json
import logging
import aiohttp
import aiofiles
import config_loader  # 配置文件加载/同步
import traceback
import uuid
import os
import random
import time

from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 启动时核对配置文件：缺失项补默认值，多余项移除
config = config_loader.load_config()


class WebSocketClient:
    def __init__(self):
        self.client_id = f"{uuid.uuid4().hex[:8]}"
        self.server_url = f'ws://{config["host"]}:{config["port"]}/ws/{self.client_id}'
        self.ws_connection = None
        self.is_connected = False
        self._receive_task = None
        self._connected_at = 0.0

        # 重连相关配置（均可在 client.yml 的 reconnect 段中覆盖）
        reconnect_cfg = config.get("reconnect") or {}
        self.initial_reconnect_delay = float(reconnect_cfg.get("initial_delay", 1))  # 初始重连延迟（秒）
        self.reconnect_delay = self.initial_reconnect_delay
        self.max_reconnect_delay = float(reconnect_cfg.get("max_delay", 300))  # 最大重连延迟
        self.backoff_factor = float(reconnect_cfg.get("backoff_factor", 1.5))  # 退避倍数
        # 0 表示无限重连；用尽后不会停止，而是转为 max_delay 间隔的保活重试
        self.max_reconnect_attempts = int(reconnect_cfg.get("max_attempts", 0))
        # 连接稳定维持超过该时长（秒）后，重置退避延迟与重试计数
        self.stable_connection_time = float(reconnect_cfg.get("stable_time", 60))
        self.open_timeout = float(reconnect_cfg.get("open_timeout", 15))  # 握手超时
        self.reconnect_attempts = 0
        self.should_reconnect = True
        self.ping_interval = 30  # 发送ping间隔（秒）

    async def connect(self):
        """连接到WebSocket服务器"""
        url = self.server_url
        logger.info(f"Connecting to {url}")

        # 清理上一次连接残留
        await self._close_connection()

        try:
            self.ws_connection = await websockets.connect(
                url,
                ping_interval=None,  # 禁用自动ping/pong，我们自己处理
                ping_timeout=120,
                close_timeout=10,
                open_timeout=self.open_timeout,
            )
            self.is_connected = True
            self.reconnect_delay = self.initial_reconnect_delay
            self.reconnect_attempts = 0
            self._connected_at = time.monotonic()
            logger.info("Connected successfully!")
            return True

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Connection failed: {type(e).__name__}: {e}")
            self.is_connected = False
            await self._close_connection()
            return False

    async def _close_connection(self):
        """安全关闭当前连接"""
        ws = self.ws_connection
        self.ws_connection = None
        if ws is None:
            return
        try:
            await ws.close()
        except Exception:
            pass

    def _reset_backoff(self):
        """连接稳定运行后重置退避状态"""
        if time.monotonic() - self._connected_at >= self.stable_connection_time:
            self.reconnect_delay = self.initial_reconnect_delay
            self.reconnect_attempts = 0

    async def send_message(self, message: dict):
        """发送消息到服务器"""
        if self.is_connected and self.ws_connection:
            try:
                await self.ws_connection.send(json.dumps(message))
                logger.debug(f"Sent: {message}")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                self.is_connected = False
        else:
            logger.warning("Not connected, cannot send message")

    async def receive_messages(self):
        """接收消息"""
        try:
            while self.is_connected and self.ws_connection:
                try:
                    message = await self.ws_connection.recv()
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"Connection closed: {e}")
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Error receiving message: {type(e).__name__}: {e}")
                    break

                # 单条消息处理异常不应导致整个连接被丢弃
                try:
                    message_data = json.loads(message)
                    await self.handle_message(message_data)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error(f"Error handling message: {traceback.format_exc()}")
        finally:
            # 只有仍标记为已连接时才置为断开，避免打断正在进行的重连
            if self.is_connected:
                self._reset_backoff()
                self.is_connected = False
            await self._close_connection()

    async def handle_message(self, message: dict):
        """处理接收到的消息"""
        message_type = message.get("type")

        if message_type == "connection_established":
            logger.info(f"Connection established: {message.get('message')}")

        elif message_type == "pong":
            # logger.debug(f"Received pong: {message.get('original_message')}")
            pass

        elif message_type == "chat_message":
            logger.info(
                f"Chat message from {message.get('from')}: {message.get('message')}"
            )

        elif message_type == "message_history":
            history = message.get("history", [])
            logger.info(f"Received message history ({len(history)} messages)")
            for msg in history:
                logger.info(f"  - {msg.get('from')}: {msg.get('message')}")

        elif message_type == "error":
            logger.error(f"Error from server: {message.get('message')}")

        elif message_type == "auth":
            if message.get("code", 0) == "200":
                logger.info("认证成功")
            else:
                # 认证失败属于服务端明确拒绝，重试无意义，交由人工修正 token
                logger.error("认证失败，停止客户端，请检查 client.yml 中的 token")
                self.should_reconnect = False
                self.is_connected = False

        elif message_type == "register":
            logger.info(f"已注册直播间：{message.get('room_id', [])}")

        elif message_type == "record_end":
            dl_manager = DownloadManager()
            await dl_manager.cmd(
                message.get("files", [])
            )

        else:
            logger.info(f"Received unknown message type: {message_type}")

    async def start_ping(self):
        """定期发送ping消息"""
        while self.should_reconnect:
            if self.is_connected:
                ping_message = {
                    "type": "ping",
                    "message": f"Ping from {self.client_id}",
                    "timestamp": datetime.now().isoformat(),
                }
                await self.send_message(ping_message)
            await asyncio.sleep(self.ping_interval)

    async def send_chat_message(self, message: str):
        """发送聊天消息"""
        chat_message = {
            "type": "chat",
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "client_id": self.client_id,
        }
        await self.send_message(chat_message)

    async def send_auth(self):
        """发送认证消息"""
        auth = {"type": "auth", "token": config["token"], "client_id": self.client_id}
        await self.send_message(auth)

    async def register_room(self, room_id):
        """注册直播间"""
        message = {"type": "register", "room_id": room_id}
        await self.send_message(message)

    async def get_message_history(self):
        """获取消息历史"""
        history_request = {
            "type": "get_history",
            "timestamp": datetime.now().isoformat(),
        }
        await self.send_message(history_request)

    async def auto_reconnect(self):
        """自动重连逻辑（默认无限重试，指数退避 + 抖动）"""
        while self.should_reconnect:
            if not self.is_connected:
                if not await self._reconnect_once():
                    break
            await asyncio.sleep(1)  # 检查间隔

    async def _reconnect_once(self):
        """执行一次重连尝试，返回是否需要继续重连"""
        self.reconnect_attempts += 1

        if self.max_reconnect_attempts > 0:
            logger.info(
                f"Attempting to reconnect... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})"
            )
        else:
            logger.info(f"Attempting to reconnect... (attempt {self.reconnect_attempts})")

        if await self.connect():
            await self._on_connected()
        else:
            await self._wait_before_retry()

        return self.should_reconnect

    async def _on_connected(self):
        """连接建立后的初始化：认证、注册、启动接收任务"""
        try:
            await self.send_auth()
            await self.register_room(config.get("room_id", []))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(f"Failed to initialize session: {traceback.format_exc()}")
            self.is_connected = False
            await self._close_connection()
            return

        # 避免重复创建接收任务
        if self._receive_task is not None and not self._receive_task.done():
            self._receive_task.cancel()
        self._receive_task = asyncio.create_task(self.receive_messages())

    async def _wait_before_retry(self):
        """等待下一次重试"""
        if self.max_reconnect_attempts > 0 and self.reconnect_attempts >= self.max_reconnect_attempts:
            # 达到上限不停机，转为定频保活重试，等待服务端恢复
            logger.warning(
                f"已连续重连失败 {self.reconnect_attempts} 次，"
                f"转为每 {self.max_reconnect_delay:.0f} 秒一次的保活重试"
            )
        delay = min(self.reconnect_delay, self.max_reconnect_delay)
        # 加入抖动，避免多客户端同时重连造成惊群
        delay *= random.uniform(0.8, 1.2)
        logger.info(f"Reconnection failed. Waiting {delay:.1f} seconds...")
        await asyncio.sleep(delay)

        # 指数退避策略
        self.reconnect_delay = min(
            self.reconnect_delay * self.backoff_factor, self.max_reconnect_delay
        )

    async def run(self):
        """运行客户端"""
        # 启动自动重连
        reconnect_task = asyncio.create_task(self.auto_reconnect())

        # 启动ping任务
        ping_task = asyncio.create_task(self.start_ping())

        try:
            # 保持主循环运行
            while self.should_reconnect:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Shutting down client...")
            self.should_reconnect = False
            self.is_connected = False

            tasks = [reconnect_task, ping_task, self._receive_task]
            for task in tasks:
                if task is not None and not task.done():
                    task.cancel()
            # 等待被取消的任务真正结束
            await asyncio.gather(*[t for t in tasks if t is not None], return_exceptions=True)

            # 关闭连接
            await self._close_connection()

            logger.info("Client stopped.")


class DownloadManager:
    async def download_file(self, url, save_path):
        """下载单个文件"""
        config = config_loader.load_config()

        file = url.split("/")[-1]
        auth = aiohttp.BasicAuth(config["user"], config["password"]) if config.get("user") and config.get("password") else None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, auth=auth) as response:
                    if response.status != 200:
                        logger.error(f"下载失败: {file}, HTTP状态码: {response.status}")
                        await session.close()
                        return False

                    file_path = save_path
                    save_path = "/".join(file_path.split("/")[:-1])
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)

                    async with aiofiles.open(file_path, "wb") as f:
                        logger.info(f"开始下载: {file}")
                        while True:
                            chunk = await response.content.read(1024)

                            if not chunk:
                                await asyncio.sleep(1)  # 确保文件完全写入
                                break
                            await f.write(chunk)

        except Exception:
            logger.error(f"下载异常: {file}, 错误: {traceback.format_exc()}")
            return False
        logger.info(f"下载完成: {file}")
        return True

    async def cmd(self, files, max_concurrent=5):
        """并发下载多个文件"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_download(url, save_path):
            async with semaphore:
                return await self.download_file(url, save_path)

        tasks = [bounded_download(url, f'{config["save_path"]}/{path}') for url, path in files.items()]
        results = await asyncio.gather(*tasks)

        successful = sum(results)
        logger.info(f"下载统计: 成功 {successful}/{len(files)}")
        message = {"type": "finish"}
        asyncio.create_task(self.send_message(message))
        return successful

    async def send_message(self, message):
        await client.send_message(message)


client = WebSocketClient()


async def start():
    # 启动客户端
    client_task = asyncio.create_task(client.run())

    try:
        # 客户端因认证失败等原因自行结束时，进程随之退出，避免空转僵死
        while not client_task.done():
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在停止客户端...")
    finally:
        client.should_reconnect = False
        if not client_task.done():
            client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass
        logger.info("客户端已退出")


if __name__ == "__main__":
    asyncio.run(start())