# Hiveton H5000M · xxxbug

基于 ImmortalWrt 官方 `25.12.2` 的 Hiveton H5000M 固件构建项目。以原成功构建 `38609714583` 恢复后的配置为基础，修改默认 Wi-Fi 参数、界面名称和版本署名；沿用该基础版本的插件与 Argon 主题。

## 系统与界面

| 项目 | 配置 |
| --- | --- |
| 设备 | Hiveton H5000M |
| 目标平台 | mediatek / filogic / hiveton_h5000m |
| 系统版本 | ImmortalWrt 25.12.2 |
| 左侧及移动端品牌文字 | `Hiveton H5000M` |
| 主题 | 沿用原版 Argon，仅替换品牌文字 |
| 字体与排版 | 保留原字体文件、CSS、模板结构和菜单布局 |
| 无线驱动 | 官方 mt76 与 H5000M 设备树 |

## 首次启动默认配置

| 项目 | 默认值 |
| --- | --- |
| LAN 地址 | `10.0.0.1/24` |
| 管理页面 | [http://10.0.0.1](http://10.0.0.1) |
| DHCP 地址池 | `10.0.0.100–10.0.0.249` |
| 管理用户 | `root` |
| root 密码 | `password` |
| Wi-Fi 国家码 | `AU`（澳大利亚） |

| 无线频段 | SSID（区分大小写） | 模式 | 默认频宽 | 加密 | 密码 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 2.4GHz | `A5KM` | BE / 802.11be | 40MHz（`EHT40`） | WPA2-PSK | `password` | 启用 |
| 5GHz | `A5KM+` | BE / 802.11be | 160MHz（`EHT160`） | WPA2-PSK | `password` | 启用 |

默认值适用于全新配置首次启动。保留旧配置升级时，旧设置可能继续生效。无线脚本按实际识别的频段设置，不依赖 radio0/radio1 的顺序。BE 与 40/160MHz 是请求配置；实际运行模式、频宽及 WPA2 客户端协商结果需结合驱动、AU 信道规则和终端实测。

## 保留的主要插件

| 类别 | 组件 |
| --- | --- |
| 外观 | Argon、Argon 设置 |
| 模组管理 | QModem 3.3.0、QModem Next、监控、TTL/fw4 |
| H5000M 专用 | MT5700M Web/transport、风扇温控、网络模式切换 |
| 网络服务 | OpenClash、ZeroTier、Watchcat |
| 系统工具 | Diskman、TTYD、APK 软件包管理 |
| 网络管理 | 防火墙、带宽监控 nlbwmon、QMI/MBIM 协议支持 |
| 诊断 | USB/PCI 工具、htop、iperf3、iw |

沿用原基础版本的插件选择；本次不加入后续实验版本的 iStore、Docker 或 QuickStart 概览。OpenClash 核心需另行配置。最终安装包以本次构建产物清单为准。


## H5000M-notdream5700：新增 MT5700 Web

本分支从 `main` 的 `03bc9054073b35bdb3e22dbfc07ce0c96b8c47e0` 创建，集成
[inotdream/mt5700webui-openwrt-server](https://github.com/inotdream/mt5700webui-openwrt-server)
的 `7abccd44c81442b13dbf974ad9a0aa67cf527e90`（集成时最新提交）。保留原插件、驱动、
Argon 主题和首次启动配置；新增 `at-webserver`、`luci-app-at-webserver` 及 Python 运行依赖。

- **入口**：LuCI → 服务 → AT WebServer；独立界面为 `http://10.0.0.1/5700/`。
- **默认状态**：预装界面，后台开机自动启用；可在 LuCI 配置页停用。
- **连接参数**：网络模式，模组 `192.168.8.1:20249`；WebSocket `8765`。
  请按实际模组连接方式配置，串口模式需选择真实 AT 端口。
- **共存**：QModem 和原 MT5700M 管理均保留。操作新 Web 前暂停其他服务对同一
  AT 通道的轮询或控制；不要让两个服务同时打开同一串口。新 Web 不会自动停用原插件。
  后台开机即连接模组；如果原插件也配置了自动轮询，需手动停用其中一方的后台访问。
- **访问范围**：沿用上游默认设置，禁止 WAN 访问 WebSocket 和模组 AT 端口。
  首次启动在设备上生成独立的 256 位 WebSocket 密钥，重启保留已有密钥；密钥保存失败则不启动服务。
  在 LuCI → 服务 → AT WebServer → 配置中查看或修改密钥，独立页面首次连接时输入；
  LuCI 的 AT 调试页自动读取密钥。密钥不写入源码或构建产物。独立页面不等同于 LuCI 登录保护。
  上游使用 `ws://`，独立界面请通过受信任 LAN 的 HTTP 地址访问，HTTPS 页面需要另行配置 WSS 代理。
- **兼容补丁**：当前固定 feeds 没有 `python3-aiohttp`。企业微信推送改用 Python
  标准库在线程中发送 HTTPS 请求，保留队列和重试，启用系统 CA 证书校验。
  清空日志改为 LuCI 登录后的 RPC 文件写入，不安装上游未鉴权的清空日志 CGI。
  补丁位于 `patches/mt5700webui/`；前端资源从固定上游提交获取并应用上述补丁。
- **验证**：工作流先验证补丁、Webhook 成功/失败/重试和 WebSocket 鉴权，再编译完整固件；
  `make defconfig` 后检查包选择，最终检查镜像包清单。
  这些检查不代表已完成 H5000M 实机拨号、短信、锁频和刷写验收。

本地运行集成测试（需先拉取上游并应用本分支补丁）：

```sh
python3 -m venv /tmp/mt5700-test
/tmp/mt5700-test/bin/pip install 'websockets==11.0.3' 'pyserial==3.5'
/tmp/mt5700-test/bin/python tests/integration_mt5700webui.py /path/to/upstream/at-webserver/files/usr/bin/at-server.py -v
node tests/integration_mt5700webui_logs.cjs /path/to/upstream/luci-app-at-webserver/htdocs/luci-static/resources/view/at-webserver/logs.js
python3 -m unittest discover -s tests -v
```

## 编译、下载与刷写

1. 推送到 `H5000M-notdream5700` 自动构建，或在 [Actions](https://github.com/xxx00000/ImmortalWrt-Hiveton-H5000M-no.1/actions) 手动运行 **Hiveton H5000M full firmware** 并选择 `H5000M-notdream5700` 分支。
2. 等待编译、镜像校验和产物上传全部成功，进入该次运行的 **Artifacts** 下载 ZIP。
3. 解压后核对 `SHA256SUMS` 与 `IMAGE-INFO.txt`，使用其中的 H5000M `.bin`。
4. 此项目沿用参照固件经用户确认可被 U-Boot 接收的单文件系统容器；新构建仍需实机验收。

| 产物 | 说明 |
| --- | --- |
| `immortalwrt-25.12.2-hiveton_h5000m-AU-full.bin` | 包含内核和根文件系统的完整系统固件 |
| `SHA256SUMS` | 固件 SHA256 校验值 |
| `IMAGE-INFO.txt` | 镜像格式、大小、校验值与无线配置说明 |
| `BUILT-PACKAGES.manifest`、`config-resolved.txt` | 构建包清单与解析后的配置 |
| `SOURCE-COMMIT.txt`、`FEEDS-COMMITS.txt` | 系统及 feeds 来源记录 |
| `PLUGIN-COMMITS.txt`、`MT5700WEBUI-PATCHES.sha256` | 插件固定提交和 Web 兼容补丁校验值 |
| `ORIGINAL-PACKAGES.tsv`、`plugins.tsv` | 上传参照固件的历史清单，不等于本次实际安装清单 |

镜像容器沿用 `squashfs-sysupgrade.bin` 的 TAR/FIT/SquashFS 结构，输出文件名为 `full.bin`；它不包含 Bootloader、分区表或设备独有的 factory/EEPROM 校准数据。刷入前核对设备型号、U-Boot 接收格式和大小限制，并保留原固件及校准区备份。

构建产物保留 14 天。CI 成功表示编译和自动检查完成，不等于实机的 U-Boot 刷写、双频连接、160MHz、模组拨号均已通过。

## 固定源码

系统源码：[immortalwrt/immortalwrt](https://github.com/immortalwrt/immortalwrt)，标签 `v25.12.2`，提交 `4fc16f2985a358bd43bb522e43f05395fcbd6ed5`。插件固定提交见 [构建工作流](.github/workflows/h5000m-build.yml)，实际 feeds 提交见产物记录。
