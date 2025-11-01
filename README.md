# BILIBILI Record Monitor

![python](https://img.shields.io/badge/Version-2.4.1-cyan) ![python](https://img.shields.io/badge/Python->=3.9,<3.14-blue) ![os](https://img.shields.io/badge/OS-Linux|MacOS-orange)

基于 BililiveRecorder 和 FastAPI 的BILIBILI录播文件监视器，用于监视B站直播状态并上传至百度网盘。

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

- 上传至百度网盘目前暂不支持并发上传，大文件上传速度可能会较慢

### TODO

- [x] 接收B站录播姬在直播状态变化时发送的webhook
- [x] ~~通过微信服务号发送通知~~（微信政策原因，已失效）
- [x] ~~支持多个用户接收通知~~（微信政策原因，已失效）
- [x] 支持监视多个直播间
- [x] 支持将录播文件移动到其他目录
- [x] 支持上传至百度网盘
- [ ] 百度网盘支持并发上传