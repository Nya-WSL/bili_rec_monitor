from fastapi import FastAPI, Request
from wxpusher import WxPusher
from datetime import datetime
from zoneinfo import ZoneInfo
import uvicorn
import logging
import shutil
import yaml
import os

# LAVEL: DEBUG INFO WARNING ERROR CRITICAL
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

version = "2.0.0"
time_zone="Asia/Shanghai"

# 创建 FastAPI 应用
app = FastAPI()

# 消息推送
def pusher(content):
    if not os.path.exists("config.yml"):
        shutil.copy("config.example.yml", "config.yml")

    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    if config["pusher"]:
        if config["AppToken"] == "" or config["TopicIds"] == [] or config["TopicIds"] == "":
            print("AppToken or TopicIds not found, please check config.yml.")
        else:
            WxPusher.send_message(content=content, topic_ids=config["TopicIds"], token=config["AppToken"])

# 空格定义，微信单行20个字符
def format_msg(message):
    return (message + ((19 - len(message)) * " ") + f"\n" if len(message) < 19 else message[:19] + f"\n")


# 时间数据清洗
def format_time(date_str):
    output_time = datetime.fromisoformat(date_str).astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d %H:%M:%S") + time_zone
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

    pusher(f"推流开始提醒 | Nya-WSL服务\n\n" + 
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
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025.All Rights reserved."
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

    pusher(f"推流结束提醒 | Nya-WSL服务\n\n" + 
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
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025. All Rights reserved."
)

def notify_session_started(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态

    pusher(f"录制开始提醒 | Nya-WSL服务\n\n" + 
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
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025. All Rights reserved."
)

def notify_session_ended(payload):
    event_time = payload["EventTimestamp"] # 事件时间
    room_id = payload["EventData"]["RoomId"] # 直播间号
    name = payload["EventData"]["Name"] # 用户名
    title = payload["EventData"]["Title"] # 直播间标题
    record_status = payload["EventData"]["Recording"] # brec录制设置状态
    stream_status = payload["EventData"]["Streaming"] # 直播状态
    danmaku_status = payload["EventData"]["DanmakuConnected"] # 弹幕姬连接状态
    
    pusher(f"录制结束提醒 | Nya-WSL服务\n\n" + 
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
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025. All Rights reserved."
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


    pusher(f"文件打开提醒 | Nya-WSL服务\n\n" + 
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
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025. All Rights reserved."
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
    file_close_time = payload["EventData"]["FileCloseTime"] # 文件关闭时间
    file_size = '{:.2f}'.format(int(payload["EventData"]["FileSize"]) / 1048576) # 文件大小,GB


    pusher(f"文件关闭提醒 | Nya-WSL服务\n\n" + 
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
            f"文件大小: {file_size} M\n"
            f"文件相对路径: {relative_path}\n" +
            "====================\n\n\n" +
            "====================\n" +
            f"录播姬状态信息\n" +
            "====================\n" +
            f"录制状态: {record_status}\n" +
            f"推流状态: {stream_status}\n" +
            f"弹幕连接: {danmaku_status}\n" +
            "====================\n\n\n" +
            f"*************************\n" +
            f"联系我们\n\n" +
            f"mail: support@nya-wsl.com\n" +
            f"QQ群: 2219140787\n"
            f"*************************\n" +
            "A Project of Nya-WSL.\n" +
            "髙橋はるき & 狐日泽\n" +
            "Copyright © 2024-2025. All Rights reserved."
    )

# 定义 Webhook 路由
@app.post("/brec_hook")
async def brec(request: Request):
    if not os.path.exists("config.yml"):
        shutil.copy("config.example.yml", "config.yml")

    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    # 获取请求体数据
    payload = await request.json()
    # 打印接收到的数据
    # print("Received webhook data:", payload)

    event_type = payload["EventType"] # 事件

    if event_type == "StreamStarted":
        if config["notice"]["StreamStarted"] == True:
            notify_stream_startd(payload=payload)
    elif event_type == "SessionStarted":
        if config["notice"]["SessionStarted"] == True:
            notify_session_started(payload=payload)
    elif event_type == "FileOpening":
        if config["notice"]["FileOpening"] == True:
            notify_file_opening(payload=payload)
    elif event_type == "FileClosed":
        if config["notice"]["FileClosed"] == True:
            notify_file_closed(payload=payload)
    elif event_type == "SessionEnded":
        if config["notice"]["SessionEnded"] == True:
            notify_session_ended(payload=payload)
    elif event_type == "StreamEnded":
        if config["notice"]["StreamEnded"] == True:
            notify_stream_ended(payload=payload)

    # 返回响应
    return {"status": "200", "message": "Webhook received"}

# 运行应用
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)