from typing import Callable, Awaitable, Optional
from fastapi import FastAPI, Request
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

# LEVEL: DEBUG INFO WARNING ERROR CRITICAL
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

yaml = YAML.YAML(typ="rt")

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
                if asyncio.iscoroutinefunction(callback):
                    await callback() # 协程回调
                else:
                    callback() # 普通回调
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

if not os.path.exists("config.yml"):
    shutil.copy("config.example.yml", "config.yml")

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.load(f)

version = "2.4.1"
time_zone = config["notice"]["TimeZone"]

# 创建 FastAPI 应用
app = FastAPI()
# 创建定时器
timer = Timer()

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

def notify_stream_startd(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    area_name = payload["EventData"]["AreaNameParent"] + "-" + payload["EventData"]["AreaNameChild"] # 直播间分区
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态

    logging.info(f"\n推流开始提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "直播推流信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"分区: {area_name}\n" +
            f"推流时间: {format_time(event_time)}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

def notify_stream_ended(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    area_name = payload["EventData"]["AreaNameParent"] + "-" + payload["EventData"]["AreaNameChild"] # 直播间分区
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    
    logging.info(f"\n推流结束提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "直播推流信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"分区: {area_name}\n" +
            f"推流时间: {format_time(event_time)}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

def notify_session_started(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    
    logging.info(f"\n录制开始提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "直播录制信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"录制开始时间: {format_time(event_time)}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

def notify_session_ended(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    
    logging.info(f"\n录制结束提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "直播录制信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"录制结束时间: {format_time(event_time)}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

def notify_file_opening(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    relative_path = payload["EventData"]["RelativePath"] # 录制文件相对路径
    file_open_time = payload["EventData"]["FileOpenTime"] # 文件打开时间

    logging.info(f"\n文件打开提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "文件打开信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"事件触发时间: {format_time(event_time)}\n" +
            f"文件打开时间: {format_time(file_open_time)}\n"+
            f"文件相对路径: {relative_path}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

def notify_file_closed(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    relative_path = payload["EventData"]["RelativePath"] # 录制文件相对路径
    file_open_time = payload["EventData"]["FileOpenTime"] # 文件打开时间
    file_close_time = payload["EventData"]["FileCloseTime"] # 文件打开时间
    file_size = '{:.2f}'.format(int(payload["EventData"]["FileSize"])/1048576) # 文件大小,MB

    logging.info(f"\n文件关闭提醒 | Nya-WSL服务\n\n" + 
            format_msg(str(room_id) + "-" + name) + 
            format_msg(title) + 
            f"\n\n" +
            "====================\n" +
            "文件关闭信息\n" +
            "====================\n" +
            f"直播标题: {title}\n" +
            f"直播间号: {room_id}\n" +
            f"主播: {name}\n" +
            f"事件触发时间: {format_time(event_time)}\n" +
            f"文件打开时间: {format_time(file_open_time)}\n"+
            f"文件关闭时间: {format_time(file_close_time)}\n"+
            f"文件大小: {file_size} MB\n"
            f"文件相对路径: {relative_path}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"推流状态: {stream_status}\n" +
            f"录制状态: {record_status}\n" +
            f"弹幕连接: {danmaku_status}\n"
    )

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

def time_out_handler():
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)

    if config["pcs"]["Enable"]:
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

# 定义 Webhook 路由
@app.post("/brec_hook")
async def brec(request: Request):
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f)
    # 获取录播姬发送的hook数据
    payload = await request.json()
    # 接收到的数据归纳至debug日志
    logging.debug(f"收到webhook数据: {payload}")

    event_type = payload["EventType"] # 事件

    if event_type == "StreamStarted":
        logging.info(f'{payload["EventData"]["RoomId"]} 开始直播')
        if config["notice"]["StreamStarted"] == True:
            notify_stream_startd(payload)
        if timer.is_running:
            timer.cancel()

    elif event_type == "SessionStarted":
        logging.info(f'{payload["EventData"]["RoomId"]} 开始推流')
        if config["notice"]["SessionStarted"] == True:
            notify_session_started(payload)

    elif event_type == "FileOpening":
        logging.info(f'{payload["EventData"]["RoomId"]} 打开文件')
        if config["notice"]["FileOpening"] == True:
            notify_file_opening(payload)

        create_wait_list(payload)

    elif event_type == "FileClosed":
        logging.info(f'{payload["EventData"]["RoomId"]} 关闭文件')
        if config["notice"]["FileClosed"] == True:
            notify_file_closed(payload)

        if config["local"]["enable"]:
            move_record_file(payload)

    elif event_type == "SessionEnded":
        logging.info(f'{payload["EventData"]["RoomId"]} 关闭推流')
        if config["notice"]["SessionEnded"] == True:
            notify_session_ended(payload)

    elif event_type == "StreamEnded":
        logging.info(f'{payload["EventData"]["RoomId"]} 结束直播')
        if config["notice"]["StreamEnded"] == True:
            notify_stream_ended(payload)

        await timer.start(config["timer"]["time"], time_out_handler) # 将回调函数作为参数传递，如果加()将会在倒计时开始前执行

    # 返回响应
    return {"status": "200", "message": "Webhook received"}

# 运行应用
if __name__ == "__main__":
    uvicorn.run(app, host=config["host"], port=config["port"])