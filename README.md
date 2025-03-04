# BILIBILI Record Monitor

![python](https://img.shields.io/badge/Version-2.0.0-cyan) ![python](https://img.shields.io/badge/Python->=3.9,<3.14-blue) ![os](https://img.shields.io/badge/OS-Windows|Linux|MacOS-orange)

基于 BililiveRecorder 和 wxpusher 的BILIBILI录播文件监视器，用于监视B站直播状态并通过微信服务号发送对应的通知。

### WatchDog

- [watchdog版本](https://github.com/Nya-WSL/bili_rec_monitor/tree/watchdog)
    - watchdog版本因为设计原因，如果使用pm2守护进程会导致生成大量日志

### Feature

- 目前支持的通知类型：

    - 直播开始
    - 直播结束
    - 开始录制
    - 结束录制
    - 开始写入
    - 结束写入

### TODO

- [x] 接收B站录播姬在直播状态变化时发送的webhook

- [x] 通过微信服务号发送通知

- [x] 支持多个用户接收通知

- [ ] 支持监视多个直播间

- [ ] 支持根据状态变化执行特定的命令