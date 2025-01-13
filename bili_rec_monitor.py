import os, time, yaml, datetime, threading
from wxpusher import WxPusher
from watchdog.observers import Observer
from watchdog.events import *
from watchdog.utils.dirsnapshot import DirectorySnapshot, DirectorySnapshotDiff

version = "1.1.1"

if os.path.exists("config.yml"):
    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
else:
    input("Config file not exists, please create config.yml first!\nPress Enter to exit...")
    exit("Config file not exists!")

if config["version"] != version:
    input("Config file version is not match, please check config.yml!\nPress Enter to exit...")
    exit("Config file version is not match")

if not config["debug"] in [True, False] or not config["pusher"] in [True, False]:
    input("debug or pusher is not bool, please check config.yml!\nPress Enter to exit...")
    exit("debug or pusher is not bool")

if config["watch_dir"] == "" or config["upload_dir"] == "" or config["file_suffix"] == "" or config["timer"] == 0:
    input("Config is error, please check config.yml!\nPress Enter to exit...")
    exit("config error")

if config["cmd"] == "":
    arg = input("未设定触发指令，是否继续运行？（Y/n）")
    if arg == "n" or arg == "N":
        exit("cmd is empty")

def pusher(message):
    if config["appToken"] == "" or config["topic_ids"] == [] or config["topic_ids"] == "":
        print("AppToken or topic_ids is empty, please check config.yml!")
    else:
        WxPusher.send_message(content=message, topic_ids=config["topic_ids"], token=config["appToken"])

class FileEventHandler(FileSystemEventHandler):
    second = 0
    minute = 0
    hour = 0
    def __init__(self, aim_path):
        FileSystemEventHandler.__init__(self)
        self.aim_path = aim_path
        self.timer = None
        self.snapshot = DirectorySnapshot(self.aim_path)

    def Timer(self):
        timer = threading.Timer(config["timer"], self.checkSnapshot)
        timer.start()
        FileEventHandler.second = 0
        FileEventHandler.minute = 0
        FileEventHandler.hour = 0
        return timer

    def cancel_timer(self):
        FileEventHandler.Timer(self).cancel()

    def on_any_event(self, event):
        if FileEventHandler.Timer(self):
            FileEventHandler.cancel_timer(self)

        FileEventHandler.Timer(self)

    def checkSnapshot(self):
        snapshot = DirectorySnapshot(self.aim_path)
        diff = DirectorySnapshotDiff(self.snapshot, snapshot)
        self.snapshot = snapshot
        self.timer = None
        upload_status = False
        file_list = []

        # print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "计时器结束", sep=": ")
        FileEventHandler.cancel_timer(self)

        for file in diff.files_modified + diff.files_created:
            for suffix in config["file_suffix"]:
                if os.path.basename(file).endswith(suffix):
                    upload_dir = os.path.split(file)[0].split(config["watch_dir"])[1].split("/")
                    upload_dir = upload_dir[0] + "/" + upload_dir[2]
                    upload_dir = os.path.join(config["upload_dir"], upload_dir)
                    if not os.path.exists(upload_dir):
                        os.mkdir(upload_dir)
                    os.system(f'cp -r "{file}" {upload_dir}/')
                    log = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {file} - Copied!"
                    if config["debug"]:
                        with open("debug.log", "a+", encoding="utf-8") as f:
                            f.write(log)
                        print(log)
                    else:
                        print(log)
                    file_list.append(f'{file}')
                    upload_status = True

        if upload_status:
            if config["pusher"]:
                if config["debug"]:
                    print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), file_list, sep=": ")
                message = str(file_list).replace("[", "").replace("]", "").replace("'", "").replace(",", "\n").replace(config["watch_dir"] + upload_dir[0] + "/", "")
                pusher(f"Nya-WSL BILIBILI Record Monitor:\n\n已上传文件：\n{message}\n\nBug Report：\nsupport@nya-wsl.com\nhttps://github.com/Nya-WSL/bili_rec_monitor")
            os.system(config["cmd"])

class DirMonitor(object):
    """文件夹监视类"""
    
    def __init__(self, aim_path):
        """构造函数"""
        self.aim_path= aim_path
        self.observer = Observer()
    
    def start(self):
        """启动"""
        event_handler = FileEventHandler(self.aim_path)
        self.observer.schedule(event_handler, self.aim_path, recursive=True)
        self.observer.start()
    
    def stop(self):
        """停止"""
        self.observer.stop()
    
def bili_rec_monitor(path):
    monitor = DirMonitor(path)
    monitor.start()
    try:
        while True:
            time.sleep(1)

            if config["debug"]:
                FileEventHandler.second += 1

                if FileEventHandler.second / 60 == 1:
                    FileEventHandler.second = 0
                    FileEventHandler.minute += 1
                if FileEventHandler.minute / 60 == 1:
                    FileEventHandler.second = 0
                    FileEventHandler.minute = 0
                    FileEventHandler.hour += 1

                print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: {FileEventHandler.hour}h:{FileEventHandler.minute}m:{FileEventHandler.second % 60}s")

    except KeyboardInterrupt:
        monitor.stop()

bili_rec_monitor(config["watch_dir"])