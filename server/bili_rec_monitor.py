from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Callable, Awaitable, Optional, Dict, List
from datetime import datetime
from zoneinfo import ZoneInfo

import ruamel.yaml as YAML
import pcs_auth # 百度云授权函数
import logging
import asyncio
import uvicorn
import shutil
import json
import pcs # 百度云上传函数
import os
import re

# LEVEL: DEBUG INFO WARNING ERROR CRITICAL
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

yaml = YAML.YAML(typ="rt")

if not os.path.exists("config.yml"):
    shutil.copy("config.example.yml", "config.yml")

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.load(f)

time_zone = config["notice"]["TimeZone"]

client_list = {}
auth_list = []

class Timer:
    def __init__(self):
        self._canceled = False
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def _run_timer(self, delay: int, callback: Callable[[], Awaitable[None]] | Callable[[], None]):
        """内部计时逻辑"""
        try:
            await asyncio.sleep(delay) # 等待倒计时结束
            if not self._canceled: # 检查是否被取消
                logging.info("计时结束，执行回调")
                await callback() # 协程回调
        finally:
            self._is_running = False

    async def start(self, delay: int, callback: Callable[[], Awaitable[None]] | Callable[[], None]):
        """启动倒计时"""
        if self._is_running:
            logging.warning("计时器已在运行中")
            return

        self._canceled = False
        self._is_running = True
        logging.info(f"开始 {delay} 秒倒计时")
        
        # 创建计时器
        self._task = asyncio.create_task(self._run_timer(delay, callback))

    def cancel(self):
        """取消计时器"""
        if self._is_running and not self._canceled:
            self._canceled = True
            if self._task:
                self._task.cancel()  # 触发任务取消
            logging.info("计时器已取消")

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.message_history: List[dict] = []
        self.is_finished = False

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logging.info(f"Client {client_id} connected")
        
        # 发送连接成功消息
        await self.send_personal_message({
            "type": "connection_established",
            "message": "Connected successfully",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        }, client_id)

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del client_list[client_id]
            auth_list.remove(client_id)
            logging.info(f"Client {client_id} disconnected")

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logging.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logging.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        for client_id in disconnected_clients:
            self.disconnect(client_id)

    async def handle_message(self, client_id: str, data: dict):
        """处理客户端消息"""
        message_type = data.get("type", "unknown")
        
        if message_type == "ping":
            # 响应ping消息
            response = {
                "type": "pong",
                "timestamp": datetime.now().isoformat(),
                "original_message": data.get("message", "")
            }
            # logging.debug(f"Received ping from {client_id}: {data.get('message', '')}")
            await self.send_personal_message(response, client_id)
            # logging.debug(f"Sent pong to {client_id}: {response}")
        
        elif message_type == "chat":
            # 处理聊天消息
            chat_message = {
                "type": "chat_message",
                "from": client_id,
                "message": data.get("message", ""),
                "timestamp": datetime.now().isoformat()
            }
            self.message_history.append(chat_message)
            # 广播给所有客户端
            await self.broadcast(chat_message)
        
        elif message_type == "get_history":
            # 发送消息历史
            history_response = {
                "type": "message_history",
                "history": self.message_history[-10:],  # 最后10条消息
                "timestamp": datetime.now().isoformat()
            }
            await self.send_personal_message(history_response, client_id)
        
        elif message_type == "auth":
            token = config.get("ws_token", "")
            auth = data.get("token", "")
            if auth != "" or token != "":
                if auth == token:
                    response = {
                        "type": "auth",
                        "timestamp": datetime.now().isoformat(),
                        "code": "200"
                    }
                    await self.send_personal_message(response, client_id)
                    auth_list.append(client_id)
                else:
                    response = {
                        "type": "auth",
                        "timestamp": datetime.now().isoformat(),
                        "code": "403"
                    }
                    await self.send_personal_message(response, client_id)
                    self.disconnect(client_id)
                    return
            else:
                response = {
                    "type": "auth",
                    "timestamp": datetime.now().isoformat(),
                    "code": "403"
                }
                await self.send_personal_message(response, client_id)
                self.disconnect(client_id)
                return
        
        elif message_type == "register":
            if client_id in auth_list:
                client_list[client_id] = data["room_id"]
                response = {
                    "type": "register",
                    "timestamp": datetime.now().isoformat(),
                    "room_id": client_list.get(client_id, [])
                }
                await self.send_personal_message(response, client_id)
        
        elif message_type == "finish":
            self.is_finished = True

# 创建 FastAPI 应用
app = FastAPI()

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建定时器
timer = Timer()

# 创建连接管理器
manager = ConnectionManager()


# 空格定义，微信单行20个字符
def format_msg(message):
    return (message + ((19 - len(message)) * " ") + f"\n" if len(message) < 19 else message[:19] + f"\n")

# 时间数据清洗
def format_time(date_str):
    if '.' in date_str:
        main_part, tz_part = date_str.split('+') if '+' in date_str else (date_str.split('-') if '-' in date_str else (date_str, ''))
        date_part, microsecond = main_part.split('.')
        microsecond = microsecond[:6].ljust(6, '0')  # 确保6位，不足补零
        standardized_str = f"{date_part}.{microsecond}+{tz_part}" if tz_part else f"{date_part}.{microsecond}"
    else:
        standardized_str = date_str

    # 解析时间（兼容Python 3.7+）
    dt = datetime.strptime(standardized_str, '%Y-%m-%dT%H:%M:%S.%f%z')

    # 转换为目标时区
    output_time = dt.astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d %H:%M:%S") + " | " + time_zone
    return output_time

def create_wait_list(payload):
    logging.info("写入wait_list")
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)
    for file_type in config["FileType"]:
        if not os.path.exists("wait_list.json"):
            with open("wait_list.json", "w+", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)

        with open("wait_list.json", "r", encoding="utf-8") as f:
            wait_list = json.load(f)

        with open("wait_list.json", "w+", encoding="utf-8") as f:
            file = "/".join(payload["EventData"]["RelativePath"].split("/", 2)).split(".")[0] + file_type
            if not file in wait_list:
                wait_list.append(file)
                json.dump(wait_list, f, ensure_ascii=False, indent=4)

# 录播文件移动到其他目录
def move_record_file(payload):
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)

    # record_file = "/" + config["local"]["RecordPath"] + payload["EventData"]["RelativePath"].split(".")[0]
    record_file = os.path.join(config["local"]["RecordPath"], payload["EventData"]["RelativePath"].split(".")[0])
    # output_file = "/" + config["local"]["OutputPath"].strip("/") + "/" + "/".join(payload["EventData"]["RelativePath"].split("/", 2)[1:2]).split(".")[0]
    output_file = os.path.join(config["local"]["OutputPath"], payload["EventData"]["RelativePath"].split("/")[1])

    if not os.path.exists(output_file):
        os.makedirs(output_file)

    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    file_size = '{:.2f}'.format(payload["EventData"]["FileSize"] / 1048576) # 文件大小,GB

    logging.info(f"\n文件转存开始 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "文件转存开始信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"文件大小: {file_size} G\n" +
            f"文件原始位置: {record_file}\n" +
            f"文件转存类型: {config['FileType']}\n" +
            f"文件转存位置: {output_file}\n"
    )

    for file_type in config["FileType"]:
        tmp_file = record_file + file_type
        os.system(f'cp -rfv "{tmp_file}" "{output_file}"')

def get_pcs_auth():
    """
    通过code模式获取百度网盘开放平台授权码，如成功获取将返回token，否则返回None
    """
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)
    if config["pcs"]["AccessToken"] in ["", None]:
        try:
            if config["pcs"]["ClientId"] == "" or config["pcs"]["SecretKey"] == "":
                raise ValueError("未配置ClientId或SecretKey")

            access_token = pcs_auth.auth()
            print(access_token)
            config["pcs"]["AccessToken"] = f"{access_token}"

            with open("config.yml", "w", encoding="utf-8") as f:
                yaml.dump(config, f)

            return config["pcs"]["AccessToken"]
        except Exception as e:
            logging.error(e)
            return None
    else:
        return config["pcs"]["AccessToken"]

# 启动时检查百度云token
if config["pcs"]["AccessToken"] in ["", None]:
    access_token = get_pcs_auth()
    if access_token == None:
        logging.error("初始化百度网盘失败")

def upload_pcs(path, file_path):
    """
    :param path: 百度云保存路径
    :param file_path: 本地文件路径
    """
    access_token = get_pcs_auth()
    path = path
    file_path = file_path

    if access_token == None:
        logging.error("获取百度网盘授权失败")
        return

    access_token, path, isdir, size, uploadid, block_list, rtype, file_path, paths, tmp_path=pcs.precreate(access_token, path, file_path)
    pcs.upload(uploadid, path, file_path, access_token, paths)
    pcs.create(access_token, path, isdir, size, uploadid, block_list, rtype, tmp_path)

async def time_out_handler():
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)
    with open("wait_list.json", "r", encoding="utf-8") as f:
        wait_list = json.load(f)

    if config["ws"]:
        if manager.active_connections != {}:
            logging.info("开始通知客户端下载录制文件")
            for client, room_ids in client_list.items():
                if client_list == {}:
                    logging.info("无在线客户端，跳过通知")
                    break
                files = {}
                for room_id in room_ids:
                    for i in wait_list:
                        if re.search(room_id, i):
                            file = config.get("download_url", "http://localhost/") + i
                            files[file] = "/".join(i.split("/", 2)[1:])
                    message = {
                        "type": "record_end",
                        "timestamp": datetime.now().isoformat(),
                        "files": files
                    }
                    await manager.send_personal_message(message, client)
                    logging.info(f"已通知客户端 {client} 下载 {room_id} 文件数: {len(files)}, files: {files}")

                    while not manager.is_finished:
                        await asyncio.sleep(1)
                    else:
                        manager.is_finished = False
    start_pcs()

def start_pcs():
    if config["pcs"]["Enable"]:
        logging.info("开始上传文件到百度网盘")
        with open("wait_list.json", "r", encoding="utf-8") as f:
            wait_list = json.load(f)
        error_list = []
        for file in wait_list:
            try:
                file_path = os.path.join(config["local"]["RecordPath"], file)
                upload_file = os.path.join(config["pcs"]["PcsPath"], "/".join(file.split("/", 2)[1:]))
                upload_pcs(upload_file, file_path)
            except Exception as e:
                import traceback
                error_list.append(file)
                logging.error(f"{file} - 上传失败: {e}")
                logging.error(f"{file} - 上传失败: {traceback.format_exc()}")
            finally:
                with open("wait_list.json", "w+", encoding="utf-8") as f:
                    json.dump(error_list, f, ensure_ascii=False, indent=4)
        logging.info("已全部上传")
    else:
        logging.info("未启用百度网盘上传，跳过上传步骤")


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            # 接收消息
            data = await websocket.receive_json()
            try:
                await manager.handle_message(client_id, data)
            except json.JSONDecodeError:
                error_response = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": datetime.now().isoformat()
                }
                await manager.send_personal_message(error_response, client_id)
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logging.info(f"Client {client_id} disconnected normally")
    except Exception as e:
        manager.disconnect(client_id)
        logging.error(f"Client {client_id} connection error: {e}")

@app.get("/")
async def root():
    return {"message": "WebSocket Server is running", "status": "healthy"}

@app.get("/status")
async def status():
    return {
        "active_connections": len(manager.active_connections),
        "message_history_count": len(manager.message_history),
        "status": "running"
    }

# 定义 Webhook 路由
@app.post("/brec_hook")
async def brec(request: Request):
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)
    # 获取录播姬发送的hook数据
    payload = await request.json()
    # 接收到的数据归纳至info日志
    logging.info(f"收到webhook数据: {payload}")

    event_type = payload["EventType"] # 事件

    if event_type == "StreamStarted":
        logging.info(f'{payload["EventData"]["RoomId"]} 开始直播')
        if timer.is_running:
            timer.cancel()

    elif event_type == "SessionStarted":
        logging.info(f'{payload["EventData"]["RoomId"]} 开始推流')

    elif event_type == "FileOpening":
        logging.info(f'{payload["EventData"]["RoomId"]} 打开文件')

        create_wait_list(payload)

    elif event_type == "FileClosed":
        logging.info(f'{payload["EventData"]["RoomId"]} 关闭文件')
        if config["local"]["enable"]:
            move_record_file(payload)

    elif event_type == "SessionEnded":
        logging.info(f'{payload["EventData"]["RoomId"]} 关闭推流')

    elif event_type == "StreamEnded":
        logging.info(f'{payload["EventData"]["RoomId"]} 结束直播')
        await timer.start(config["timer"]["time"], time_out_handler) # 将回调函数作为参数传递，如果加()将会在倒计时开始前执行

    # 返回响应
    return {"status": "200", "message": "Webhook received"}

# 运行应用
if __name__ == "__main__":
    uvicorn.run(app, host=config["host"], port=config["port"])