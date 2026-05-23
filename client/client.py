# client.py
import websockets
import asyncio
import json
import logging
import aiohttp
import aiofiles
import traceback
import uuid
import os
import ruamel.yaml as YAML

from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

yaml = YAML.YAML(typ="rt")

with open("client.yml", "r", encoding="utf-8") as f:
    config = yaml.load(f)


class WebSocketClient:
    def __init__(self):
        self.client_id = f"{uuid.uuid4().hex[:8]}"
        self.server_url = f'ws://{config["host"]}:{config["port"]}/ws/{self.client_id}'
        self.ws_connection = None
        self.is_connected = False
        self.reconnect_delay = 1  # 初始重连延迟（秒）
        self.max_reconnect_delay = 60  # 最大重连延迟
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10  # 最大重连次数（0表示无限重连）
        self.should_reconnect = True
        self.ping_interval = 30  # 发送ping间隔（秒）

    async def connect(self):
        """连接到WebSocket服务器"""
        url = self.server_url
        logger.info(f"Connecting to {url}")

        try:
            self.ws_connection = await websockets.connect(
                url,
                ping_interval=None,  # 禁用自动ping/pong，我们自己处理
                ping_timeout=120,
                close_timeout=300,
            )
            self.is_connected = True
            self.reconnect_delay = 1  # 重置重连延迟
            self.reconnect_attempts = 0
            logger.info("Connected successfully!")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

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
        while self.is_connected and self.ws_connection:
            try:
                message = await self.ws_connection.recv()
                message_data = json.loads(message)
                await self.handle_message(message_data)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                self.is_connected = False
                break

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
                logger.error("认证失败")
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
        """自动重连逻辑"""
        while self.should_reconnect:
            if not self.is_connected:
                if (
                    self.max_reconnect_attempts > 0
                    and self.reconnect_attempts >= self.max_reconnect_attempts
                ):
                    logger.error("Max reconnection attempts reached. Stopping.")
                    break

                self.reconnect_attempts += 1
                logger.info(
                    f"Attempting to reconnect... (attempt {self.reconnect_attempts})"
                )

                if await self.connect():
                    # 连接成功，启动消息接收
                    await self.send_auth()
                    await self.register_room(config.get("room_id", []))
                    asyncio.create_task(self.receive_messages())
                else:
                    # 连接失败，等待一段时间后重试
                    logger.info(
                        f"Reconnection failed. Waiting {self.reconnect_delay} seconds..."
                    )
                    await asyncio.sleep(self.reconnect_delay)

                    # 指数退避策略
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2, self.max_reconnect_delay
                    )

            await asyncio.sleep(1)  # 检查间隔

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
                if not self.is_connected and not self.should_reconnect:
                    break
        finally:
            logger.info("Shutting down client...")
            self.should_reconnect = False

            # 等待任务完成
            reconnect_task.cancel()
            ping_task.cancel()

            # 关闭连接
            if self.ws_connection:
                await self.ws_connection.close()

            logger.info("Client stopped.")


class DownloadManager:
    async def download_file(self, url, save_path):
        """下载单个文件"""
        with open("client.yml", "r", encoding="utf-8") as f:
            config = yaml.load(f)

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
        # 等待连接建立
        await asyncio.sleep(3)

        # 保持运行
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        client.should_reconnect = False
        client_task.cancel()
    finally:
        client.should_reconnect = False
        client_task.cancel()


if __name__ == "__main__":
    asyncio.run(start())