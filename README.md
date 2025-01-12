# BILIBILI Record Monitor

![python](https://img.shields.io/badge/Version-1.1.0-cyan) ![python](https://img.shields.io/badge/Python->=3.9,<3.14-blue) ![watchdog](https://img.shields.io/badge/watchdog-6.0.0-blue) ![os](https://img.shields.io/badge/OS-Only_Linux-orange)

基于[OneDrive Client for Linux](https://github.com/abraunegg/onedrive/)和 `watchdog` 的文件监视器，用于监视指定文件夹中的文件变化，并在文件发生变化时进行相应的操作。

注：仅支持 **`Linux`** ，仅在  **`Ubuntu Server`** & **`Kali Linux`** 中进行过测试

### Feature

- 监视指定文件夹中指定后缀文件的变化
- 在文件发生变化时，重置计时器
- 在文件停止变化并在计时器结束后，触发指定的命令

### Usage

- ### Linux
  
    - 安装依赖
    
        ```
        # use portry
        pip install poetry
        poetry install
        ```

        or

        ```
        # use pip
        pip install -r requirements.txt
        ```
    
    - 修改配置
    
        - 修改 `config.yml`
        
            - #### debug

                - 值：[true, false]
                - 输出计时器计数到终端中，还会在log中写入日志

            - #### pusher

                - 值：[true, false]
                - 是否启用微信推送

            - #### file_suffix

                - 值：str
                - 监听的文件后缀

            - #### timer

                - 值：[float, int]
                - 单位：秒
                - 计时器时长

            - #### appToken

                - 值：str
                - 微信推送平台的appToken，见https://wxpusher.zjiecode.com/admin
            
            - #### topic_ids

                - 值：list
                - 微信推送平台的群发主题id，见https://wxpusher.zjiecode.com/admin

            - #### watch_dir

                - 值：str，绝对路径
                - 需监听的目录，末尾必须加“/”

            - #### upload_dir

                - 值：str，绝对路径

                - 需上传的目录，末尾的“/”可以不加

            - #### cmd

                - 触发计时器后的指令
        
    - 运行程序
      
        - 直接运行

            ```
            poetry run python3 bili_rec_monitor.py

            # or

            poetry run python bili_rec_monitor.py

            # or

            python3 bili_rec_monitor.py

            # or

            python bili_rec_monitor.py
            ```

        - 后台运行

            - pm2

                ```
                npm install pm2 -g
                pm2 startup
                cd /project_path # cd /opt/bili_rec_monitor
                poetry self add poetry-plugin-shell
                portry shell
                pm2 start bili_rec_monitor.py --name Project_Name
                # pm2 start bili_rec_monitor.py --name bili_rec_monitor
                pm2 save
                ```
