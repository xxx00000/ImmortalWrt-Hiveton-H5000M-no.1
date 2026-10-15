# Hiveton H5000M 固件

适用于 Hiveton H5000M（MT7987 / MT7992），通过 GitHub Actions 编译。

## 源码

- 系统：[ImmortalWrt 官方源码 v25.12.2](https://github.com/immortalwrt/immortalwrt/tree/v25.12.2)
- 固定提交：`4fc16f2985a358bd43bb522e43f05395fcbd6ed5`
- 设备目标：`mediatek/filogic/hiveton_h5000m`
- 编译配置：[h5000m-build.yml](.github/workflows/h5000m-build.yml)

## 编译与下载

进入 [Actions](https://github.com/xxx00000/OpenWRT-CI-H5000M/actions/workflows/h5000m-build.yml)，选择 **Run workflow** 发起编译。提交到 `main` 也会自动构建。

编译成功后，在对应运行页面的 **Artifacts** 下载压缩包，解压取得固件 `.bin`、SHA256 校验文件和构建清单。

## 首次启动默认设置

| 项目 | 设置 |
|---|---|
| LAN / 管理地址 | `10.0.0.1/24` / http://10.0.0.1 |
| 用户名 / 密码 | `root` / `password` |
| DHCP 地址池 | `10.0.0.100–249` |
| 2.4GHz Wi-Fi | `A3KM`，密码 `password` |
| 5GHz Wi-Fi | `A3KM+`，密码 `password` |
| 无线加密 | WPA2-PSK，双频启用 |
| 无线地区 / 5GHz 模式 | `AU` / `HE160` |

以上设置用于全新配置首次启动。160MHz 实际运行情况需使用支持该频宽的客户端验证。

## 模组与插件

包含 QModem 3.3.0、MT5700 管理、风扇控制、网络模式切换、OpenClash、Diskman、Argon 等组件。提供 RM500Q、RM520N、FM350 所需的常用 USB / PCIe 驱动，实际拨号需按模组型号和连接方式测试。

原插件的保留、替换及缺失情况见 [插件清单](baseline/plugins.tsv)。OpenClash 需另行准备运行核心和有效配置。

## 固件格式

输出单个包含完整内核和根文件系统的 `.bin`，不含 Bootloader、分区表及 factory 校准数据。

当前包内标识使用 `hiveton_h5000m`，参照固件使用 `hiveton,h5000m`。当前 U-Boot 对该格式的接受情况尚未实机验证，刷入前需确认格式、目标区域和文件大小上限。
