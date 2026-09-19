# BILIBILI Record Monitor

![server](https://img.shields.io/badge/Server-2.7.2-cyan) ![client](https://img.shields.io/badge/Client-2.7.2-cyan) ![python](https://img.shields.io/badge/Python->=3.9,<3.14-blue) ![os](https://img.shields.io/badge/OS-Linux|MacOS-orange) ![uv](https://img.shields.io/badge/deps-uv-blueviolet)

基于 BililiveRecorder 和 FastAPI 的BILIBILI录播文件监视器，用于监视B站直播状态并 `上传至百度网盘/下载至其他设备` 。

### WatchDog

- [watchdog版本](https://github.com/Nya-WSL/bili_rec_monitor/tree/watchdog)
    - watchdog版本如果使用pm2守护进程会导致生成大量日志

### Feature

- 目前支持的通知类型：

    - 直播开始
    - 直播结束
    - 开始录制
    - 结束录制
    - 开始写入
    - 结束写入

- 百度网盘目前暂不支持并发上传，大文件上传速度可能会较慢

- 在启用ws的情况下，上传至百度云将会在所有下载结束后开始，如果没有注册过的房间号或无客户端在线将直接开始上传

- 客户端默认无限重连：采用指数退避 + 抖动策略，服务端临时不可用/握手超时不会导致客户端停机（仅 token 认证失败会退出）
- 可在 `client.yml` 的 `reconnect` 段自定义重连参数（`initial_delay`、`max_delay`、`backoff_factor`、`max_attempts`、`stable_time`、`open_timeout`）

### Usage

> 服务端与客户端的依赖已统一由仓库根目录的 `pyproject.toml` / `uv.lock` 管理，`server/` 与 `client/` 目录下的旧 `pyproject.toml` 已移除。

- 安装依赖

    - 安装uv
        ```bash
        # linux
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # windows需修改powershell的执行策略
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        ```

    - 分别在录播姬所在系统（服务端）和需保存录播文件的系统（客户端） clone 本仓库，在仓库根目录执行

        ```bash
        # 公共依赖（服务端必需）
        uv sync

        # 客户端额外依赖（fastapi/uvicorn/aiofiles），在客户端机器上追加安装
        uv sync --group client
        ```

        > 旧版本遗留的 `server/uv.lock`、`client/uv.lock` 已不再使用，请统一使用仓库根目录的 `uv.lock`。

- 配置

    - 分别在服务端/客户端运行一次程序，自动生成 `server/config.yml` 与 `client/client.yml`
    - 每次启动时会自动以 `*.example.yml` 为模板核对配置文件：**缺失项补默认值、多余/废弃项移除**，已有值保持不变，无需手动迁移配置
    - 参考示例文件 `server/config.example.yml`、`client/client.example.yml` 修改配置
        - 服务端：webhook 监听地址与端口、ws 开关与 token、录制文件路径、百度网盘开放平台 AppKey/SecretKey 等
        - 客户端：服务端 ws 地址与端口、token、录播姬基本认证、需注册的房间号、文件保存路径

- 运行

    ```bash
    # 可使用pm2或systemctl等后台运行
    # 依赖安装在仓库根目录，运行时需进入对应目录（config.yml/client.yml 生成在当前工作目录）

    # 服务端（在录播姬所在机器）
    cd server
    uv run bili_rec_monitor.py

    # 客户端（在需保存录播文件的机器）
    cd client
    uv run client.py
    ```

    > 首次使用百度网盘上传时，可在 `server` 目录执行 `uv run pcs_auth.py` 获取 `access_token`。

### Structure

```text
├── pyproject.toml        # 统一依赖管理（含 client 依赖组）
├── uv.lock
├── server/               # 服务端：接收 webhook、处理与上传录播文件
│   ├── bili_rec_monitor.py
│   ├── config_loader.py  # 配置加载与同步（比对 config.example.yml）
│   ├── pcs.py / pcs_auth.py
│   └── openapi_client/   # 百度网盘开放平台接口
└── client/               # 客户端：通过 ws 下载录播文件到本地
    ├── client.py
    └── config_loader.py  # 配置加载与同步（比对 client.example.yml）
```


### TODO

- [x] 接收B站录播姬在直播状态变化时发送的webhook
- [x] ~~通过微信服务号发送通知~~（微信政策原因，已失效）
- [x] ~~支持多个用户接收通知~~（微信政策原因，已失效）
- [x] 支持监视多个直播间
- [x] 支持将录播文件移动到其他目录
- [x] 支持上传至百度网盘
- [x] 支持WebSocket
- [ ] 百度网盘支持并发上传