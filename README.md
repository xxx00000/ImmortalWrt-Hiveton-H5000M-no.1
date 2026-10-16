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
| H5000M 专用 | 新版 MT5700 Web、共享 AT 服务、风扇温控、网络模式切换 |
| 网络服务 | OpenClash、ZeroTier、Watchcat |
| 系统工具 | Diskman、TTYD、APK 软件包管理 |
| 网络管理 | 防火墙、带宽监控 nlbwmon、QMI/MBIM 协议支持 |
| 诊断 | USB/PCI 工具、htop、iperf3、iw |

沿用原基础版本的插件选择；本次不加入后续实验版本的 iStore、Docker 或 QuickStart 概览。OpenClash 核心需另行配置。最终安装包以本次构建产物清单为准。


## H5000M-notdream5700：新 Web 与共享 AT 服务

本分支从 `main` 的 `03bc9054073b35bdb3e22dbfc07ce0c96b8c47e0` 创建，使用
[inotdream/mt5700webui-openwrt-server](https://github.com/inotdream/mt5700webui-openwrt-server)
的固定提交 `7abccd44c81442b13dbf974ad9a0aa67cf527e90`。按最新要求移除旧 FAN789
`luci-app-mt5700m`、其翻译包和 `mt5700m-transport`，保留 QModem、其他插件及驱动。

- **入口**：LuCI → 调制解调器 → **模组界面**，位于 QModem 上方；分组位置不变。
  页面直接嵌入新版 Web，也可访问 `http://10.0.0.1/5700/`。
- **默认启用**：公共 AT 服务先启动，新 Web 后台开机启动。无模组时 WebSocket 仍可启动，
  操作显示未就绪；不会猜测 USB 端口，也不会退回直接访问串口。
- **公共 AT 通道**：仅 `ubus-at-daemon` 打开串口/TCP。QModem 的 `tom_modem`、扫描器、
  短信及新 Web 均通过同一服务的端口租约排队。短信模式、提示符、PDU、最终响应属于同一个事务。
  Web 从 QModem 读取实际 `at_port`；只有一个可用设备时自动选择，多个设备需在“连接设置”选定。
  TCP 端口使用 `tcp://IPv4:port`，由 QModem 设备配置提供，不使用独立的 Web 串口设置。
- **拨号配置**：QModem 负责自动拨号和重连。Web 的自动拨号开关、主 PDP/APN 设置写入
  QModem 后调用其控制器；自动拨号查询显示 QModem 配置，操作成功仅表示控制器接受请求。
  QModem 全局停用时不会被 Web 绕过。双 SIM 独立 APN、多 PDP、固定地址及不支持的拨号模式
  应在 QModem 配置，Web 会明确拒绝这些修改。原 Web 定时自动命令关闭。
- **故障隔离**：模组响应超时、超长或短信取消无法确认时，服务隔离该端口，防止迟到响应
  被下一位调用者误收。先排查/恢复模组，再执行 `/etc/init.d/ubus-at-daemon restart` 重新连接。
  不应另外运行直接打开同一 AT 端口的软件。
- **鉴权**：设备首次启动通过 Python `secrets` 生成独立的 256 位 WebSocket 密钥，重启保留；
  不依赖固件中缺失的 `od`。生成/保存失败时不启动 Web。在“模组界面 → 连接设置”查看密钥，
  独立 Web 首次连接输入；LuCI AT 调试页自动读取。密钥不写入源码或构建产物。
  WebSocket 默认禁止 WAN 访问。上游使用 `ws://`，通过受信任 LAN 的 HTTP 地址访问，
  HTTPS 页面需自行配置 WSS。独立 Web 的密钥鉴权不等同于 LuCI 登录。
- **兼容和迁移**：保留系统 CA 校验的标准库 Webhook、登录后清空日志及 Python 构建依赖补丁；
  修复 `/5700/` 资源路径，LuCI 资源加新版本命名空间。保留配置升级时清理旧 MT5700M
  服务/菜单，并强制两个客户端使用公共通道。
- **编译前验证**：Actions 的 `webui-check` 先编译并运行 Linux 原生 `ubusd`、公共 AT daemon、
  QModem CLI，使用模拟模组验证并发响应隔离、短信事务、取消、过期、超时和 URC；再运行 WebSocket
  鉴权、Webhook、日志、菜单和包集成检查。完整固件 job 依赖所有前置检查通过。
  镜像生成后再验证包清单和实际 SquashFS 中的新组件、启动链接、菜单及旧组件缺失。
  模拟模组和完整编译均不代表 H5000M 实机刷写、拨号、短信或锁频验收。

本地验证（上游目录需已应用本分支相应补丁；Linux 原生测试另需 cmake/build-essential/libjson-c-dev/pkg-config）：

```sh
python3 -m venv /tmp/mt5700-test
/tmp/mt5700-test/bin/pip install 'websockets==11.0.3'
PYTHONPATH="$PWD/files/usr/lib/at-webserver" /tmp/mt5700-test/bin/python tests/integration_mt5700webui.py /path/to/web/at-webserver/files/usr/bin/at-server.py -v
node tests/integration_mt5700webui_logs.cjs /path/to/web/luci-app-at-webserver/htdocs/luci-static/resources/view/at-webserver/logs.js
python3 -m unittest discover -s tests -v
python3 scripts/check-shared-packages.py /path/to/web /path/to/qmodem
bash scripts/check-shared-at-native.sh /path/to/qmodem
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
| `QMODEM-PATCHES.sha256`、`SHARED-AT-VALIDATION.txt` | 公共 AT 补丁校验及实际根文件系统检查结果 |
| `ORIGINAL-PACKAGES.tsv`、`plugins.tsv` | 上传参照固件的历史清单，不等于本次实际安装清单 |

镜像容器沿用 `squashfs-sysupgrade.bin` 的 TAR/FIT/SquashFS 结构，输出文件名为 `full.bin`；它不包含 Bootloader、分区表或设备独有的 factory/EEPROM 校准数据。刷入前核对设备型号、U-Boot 接收格式和大小限制，并保留原固件及校准区备份。

构建产物保留 14 天。CI 成功表示编译和自动检查完成，不等于实机的 U-Boot 刷写、双频连接、160MHz、模组拨号均已通过。

## 固定源码

系统源码：[immortalwrt/immortalwrt](https://github.com/immortalwrt/immortalwrt)，标签 `v25.12.2`，提交 `4fc16f2985a358bd43bb522e43f05395fcbd6ed5`。插件固定提交见 [构建工作流](.github/workflows/h5000m-build.yml)，实际 feeds 提交见产物记录。
