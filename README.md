# Hiveton H5000M 固件构建

本仓库只保留一条 H5000M 构建流程：ImmortalWrt 官方稳定版 `25.12.2`，设备 `mediatek/filogic/hiveton_h5000m`，按参照固件可由 U-Boot 接收的单个 `squashfs-sysupgrade.bin` 容器输出。旧工作流、定时发布和清理项目已从当前树移除；旧提交仍可在 Git 历史中恢复。

提交到 `main` 会自动构建，也可在 Actions 手动运行。构建成功后，从该次运行的 Artifacts 下载唯一的 `.bin` 文件和校验清单。工作流不自动发布 Release，也不会刷写设备。

首次启动默认值：LAN `10.0.0.1/24`、DHCP `10.0.0.100–249`、root 密码 `password`、2.4GHz `A5KM`（BE / `EHT40`）、5GHz `A5KM+`（BE / `EHT160`），两网均启用、WPA2-PSK、Wi-Fi 密码 `password`，Wi-Fi 国家码 `AU`。无线脚本按实际识别到的 2.4/5GHz radio 设置，不依赖 `radio0/radio1` 顺序。

固件使用官方 `mt76` 无线驱动和设备树，并启用 USB、QMI、MBIM、NCM、RNDIS 与 MHI/t7xx 蜂窝驱动。QModem 固定在上游正式版 `v3.3.0`；MT5700 使用 FAN789 H5000M transport/LuCI 插件。RM500Q、RM520N、FM350 的具体拨号协议仍取决于型号后缀和 USB/PCIe 接线。澳大利亚监管域下是否能实际协商 BE 模式及 40/160MHz，必须用 H5000M 和支持 160MHz 的客户端实测；配置值本身不代表射频验收通过。

`baseline/all-packages.tsv` 和 `baseline/plugins.tsv` 是上传固件的原始包清单与 23 个 LuCI 应用基线。构建保留并重建当前已确认兼容的系统插件、OpenClash、Diskman、Argon、QModem 和 H5000M 模组/风扇/网络模式组件。MTK 专有加速插件、旧 iStore/opkg 管理器，以及缺少可信源码或与新 ABI 不兼容的旧 Web/辅助插件在迁移表中单列，不能算作已迁移；构建产物会附带清单，实机测试前不标为稳定版。

刷入前核对 U-Boot 页面接受的文件大小上限，并保存原固件、分区表、Bootloader 环境及 factory 校准区备份。该 `.bin` 与参照固件一样是 H5000M 的完整系统更新容器，不含 Bootloader 或每台设备独有的 factory 校准数据。
