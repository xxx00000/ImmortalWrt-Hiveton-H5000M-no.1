# Hiveton H5000M WebBuild 部署与使用

这是一套可运行的中文配置网页、Node.js 后端和现有 GitHub Actions 的增量集成。代码在 `Hiveton-H5000M-WebBuild` 分支；不需要合并到 main 即可部署。不要把后台凭据放入 GitHub Pages，也不要把本服务的 `/data` 映射为静态文件。

## 1. 先在电脑打开网页

安装 Node.js 24 LTS，然后运行：

```sh
git clone --branch Hiveton-H5000M-WebBuild --single-branch https://github.com/xxx00000/OpenWRT-CI-H5000M.git
cd OpenWRT-CI-H5000M
PREVIEW=1 node webbuild/server/main.mjs
```

打开 http://127.0.0.1:8787 。可操作表单、校验、预览、保存和导入导出模板。预览模式明确禁用 GitHub 登录和编译，不会伪造构建结果。它仅监听本机，不能用 `HOST=0.0.0.0` 将预览暴露到公网。

Windows PowerShell 用 `$env:PREVIEW='1'; node webbuild/server/main.mjs`。生产服务使用下述 Linux Docker 部署，因为 root 哈希需要 OpenSSL 的 SHA-512 crypt；macOS 系统自带的 LibreSSL 不支持该命令。

## 2. 准备服务器与域名

需要运行 Docker Engine/Compose 的 Linux 服务器、解析到服务器的域名、可达的 80/443 端口及足够磁盘空间。每个私人固件包最多 1 GiB，结果默认保留 7 天；建议至少预留 20 GiB 并监控磁盘。只运行一个后端实例，不要横向扩容共享同一数据卷。

GitHub Actions 需要能通过公网 HTTPS 访问服务。私人配置不能通过纯静态站点完成安全编译。

## 3. 创建仅用于此仓库的 GitHub App

在 GitHub Settings → Developer settings → GitHub Apps → New GitHub App 创建自有 App：

- Homepage URL：你的 `https://build.example.com`。
- Callback URL：`https://build.example.com/auth/callback`，不要添加通配符。
- 关闭 Webhook（本服务轮询状态，不需要 webhook）。
- Repository permissions：**Actions: Read and write**，**Contents: Read-only**；Metadata 为默认只读。
- 不申请组织、管理、仓库写入、Secrets 或其他权限。
- 安装范围选择 **Only select repositories**，仅勾选 `xxx00000/OpenWRT-CI-H5000M`。

记录 App ID、Client ID，生成 Client secret 和 App private key。安装后的页面 URL 含 installation ID，例如 `/settings/installations/12345678`。

用户通过这个 App 的 GitHub OAuth 登录。后端每次读取任务、下载或发起编译都会重新检查用户对固定仓库是否拥有 push/admin 权限；其他账号无法使用。服务端安装令牌只负责调度，不替代用户权限检查。

App 的权限授予与私钥创建请由仓库所有者在 GitHub 界面完成。无需提供 PAT。

## 4. 配置服务并启动

在服务器上取得该分支，进入 `webbuild`：

```sh
cd OpenWRT-CI-H5000M/webbuild
mkdir -p secrets
cp .env.example .env
chmod 700 secrets
chmod 600 .env
```

将下载的 App 私钥保存为 `secrets/github-app.pem`；设为 `600` 权限，并确保容器内 UID 1000 可读取（Linux 可按实际环境使用 `sudo chown 1000:1000 secrets/github-app.pem`）。不要将私钥提交到任何仓库。

编辑 `.env` 填入真实值：

| 字段 | 内容 |
|---|---|
| PUBLIC_HOST | 域名，不带协议，如 build.example.com |
| PUBLIC_ORIGIN | 完整 HTTPS origin，无末尾斜线 |
| GITHUB_APP_ID / GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET | App 设置页的值 |
| GITHUB_INSTALLATION_ID | 仅安装到目标仓库的 installation ID |
| DATA_KEY | 32 随机字节的 base64，重启时保持不变 |
| EXPECTED_SHA | 当前已审核 `Hiveton-H5000M-WebBuild` 分支完整提交 SHA |

可用以下命令把随机 DATA_KEY 直接写入 `.env`，避免显示到终端：

```sh
python3 - <<'PY'
import base64,pathlib,secrets
p=pathlib.Path('.env')
s=p.read_text().replace('DATA_KEY=replace-me','DATA_KEY='+base64.b64encode(secrets.token_bytes(32)).decode())
p.write_text(s)
p.chmod(0o600)
PY
```

查看分支提交：`git rev-parse HEAD`。把完整 SHA 填到 EXPECTED_SHA。每次更新源码后先审核，再同步 EXPECTED_SHA；服务拒绝向未经审核的新提交传递私人配置。

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=50 webbuild
```

Caddy 自动申请 HTTPS 证书。不要另行发布 8787 端口到公网。Compose 仅在后端端口不对公网开放时启用 TRUST_PROXY；Caddy 会覆盖 X-WebBuild-Client-IP，按真实客户端分别限流，登录用户和 OIDC 另有独立预算。不要在可被直接访问的后端上信任该请求头。默认没有代理访问日志，以免记录 OAuth 回调中的临时代码；如自加代理，必须关闭或脱敏 `/auth/callback` 日志。

健康接口：`https://你的域名/healthz`。它只返回存活状态，不表示 GitHub 配置已经联调成功。

## 5. 配置 GitHub Actions 公开变量

目标仓库 Settings → Secrets and variables → Actions → Variables：

- `WEBBUILD_URL`：和 `PUBLIC_ORIGIN` 完全一致，如 `https://build.example.com`。

这里不需要设置管理员/Wi-Fi 密码，也不需要设置 PAT 或 App 私钥。Actions 通过 GitHub 签发的 OIDC 身份领取配置；后端验证签名、仓库 ID、所有者 ID、分支、workflow、提交、事件、运行编号及任务标题。只接受首次运行，GitHub 的“Re-run jobs”不能复用私人配置；请从网页新建任务。

原有 `h5000m-build.yml` 已在 main 上存在 `workflow_dispatch`，因此可以指定本分支运行；新增的 `task_id` 只有 UUID。若 GitHub 返回 workflow input/ref 错误，确认 App 已安装、分支包含完整 workflow，且该文件仍存在于默认分支；不要为此修改 main。可在分支手动 Run workflow（task_id 留空）测试原有默认编译。

## 6. 网页使用与首次真实联调

1. 打开 HTTPS 网页，用仓库所有者或有写入权限的 GitHub 账号登录。
2. 设置编译者、备注、LAN/网段、DHCP、主机名、时区、主题、额外插件和双频 Wi-Fi。
3. 主动输入 root 和两个 Wi-Fi 密码。`password` 仅为界面示例，未自动写入表单。
4. 点击“校验并预览配置”，确认全新配置启动及私人固件保管提示，提交。
5. 构建记录显示真实排队/编译/完成/失败状态；Actions 链接可查看步骤状态，编译细节在私人诊断包中。
6. 成功后从网页下载私人固件压缩包。检查包内 SHA256 校验文件，按现有 U-Boot 刷机流程处理。不要把私人固件转存到公开 Release 或公开网盘。

首次联调应使用专用测试密码，检查公开 Actions 日志与 artifacts 没有这些测试值。再在 H5000M 硬件上使用全新配置验证 LAN、DHCP、双频、密码、主题、MT5700/FM350/移远页面及串口所有权管理。此前已能工作的旧固件不代表这次定制镜像已完成硬件验收。

### 默认值与保护范围

- 管理地址 `10.0.0.1/24`，DHCP 偏移 100、数量 150（地址 .100–.249）。修改前缀后需匹配地址池，不能包含管理 IP。
- SSID `A3KM` / `A3KM+`，WPA2-PSK；Wi-Fi 密码限定 8–63 位可打印 ASCII。
- 原有 69 个显式选择包全部保留，含模组管理、USB/PCIe 驱动、Wi-Fi 驱动、OpenClash、iStore、Docker 等。
- 本期只可删除本次额外添加的包，不能删除原有插件或驱动。白名单在 `webbuild/policy.json`；管理员审核新包后才可扩展。
- 默认 LuCI 主题可选 Argon、Bootstrap、Material；选择主题不会移除 Argon 或其他原组件。
- 保留原有 AU、EHT20/EHT160 无线参数，不预设 radio0/radio1。频段不能确认时停止并重试，不猜测。

### 恢复旧配置

新默认值用于全新配置启动。启动早期检测 sysupgrade 配置备份，保留恢复的网络/无线与 shadow；不会强制把保留配置改成新值。以后再次升级时保留应用标记。手动恢复备份发生在设备启动之后时，以恢复的配置为准；需要新默认值应清除旧配置后重启。原模组互斥管理逻辑保持原样。

## 7. 密码保护与保存期限

- 浏览器模板、导出 JSON 和脱敏预览均不含密码；载入模板会清空密码框。
- root 明文只用于服务端 OpenSSL 标准输入生成 SHA-512 crypt 哈希，不通过命令参数传递；持久化的任务只有 root 哈希与 AES-256-GCM 加密的无线配置。
- App 凭据只在服务端；会话 HttpOnly/Secure/SameSite，写入请求校验 Origin/CSRF。
- 定制任务仅把 UUID 传给 workflow；不使用 Secrets API 动态写入共享密码，不在公开 Actions inputs、输出、artifact 上传私人配置。
- 定制编译日志重定向到 runner 私有文件，失败诊断同样受下载权限保护。既有空任务默认构建仍采用原来的公开默认值与公开 artifact。
- 密码仍会存在于浏览器内存、可信后端内存、构建 runner，以及固件中的 Wi-Fi 配置里；任何拥有这些主机管理权限的人都可能读取它。无法让嵌入 Wi-Fi 密码的固件在公开后仍保密。
- 构建完成后删除任务配置；未完成/失败配置至多 24 小时；结果和任务记录 7 天自动清理，浏览器会话 8 小时过期，重启服务后需要重新登录。
- 任务文件和临时文件按 600 权限保存，结果目录 700；Docker 数据卷及其备份也需私有保护。

## 8. 运维、故障与回滚

- **派发结果不确定**：不要立即重复提交。先刷新记录并查看对应 UUID 的 Actions 运行；后端会识别延迟出现的运行。若确认未创建，可新建任务，旧配置 24 小时后清理。
- **OIDC 校验失败**：检查 PUBLIC_ORIGIN、WEBBUILD_URL、EXPECTED_SHA、分支及 App 安装仓库；不要关闭证书或签名校验。
- **状态暂不可用**：网页保留上次状态，不假装完成。检查 GitHub API/App 权限与网络。
- **依赖/主题包缺失**：构建校验会失败，不会静默生成删减原插件的固件。
- **容器读私钥失败**：检查 secrets 文件 UID/权限；不要把后端改为 root 运行。
- **磁盘不足**：停止新建任务，备份后清理过期数据；服务不会自动删除未过期私人结果。
- **备份**：停止 webbuild 容器后备份 tasks 数据卷及 DATA_KEY，二者分别安全保存。没有 DATA_KEY 无法恢复任务。备份也包含私人固件，不能公开。
- **密钥轮换**：先停止接收任务，等待构建结束并导出需保留结果，停止服务并归档旧卷；使用新空卷及 DATA_KEY 重启。不要直接替换 DATA_KEY 读取旧卷。App 私钥/Client secret 在 GitHub 轮换后更新文件/环境，再重启服务。
- **更新/回滚**：切换到审核过的本分支提交，更新 EXPECTED_SHA，`docker compose up -d --build`。原 main 和此前固件不受影响。回滚网页代码不能回滚已刷设备的配置。
- **停止**：`docker compose down` 保留数据卷；不要随意加 `-v`，它会删除保留结果。

## 9. 开发验证

```sh
node --test webbuild/test/*.test.mjs
python3 -m unittest discover -s tests -v
```

CI 在本分支 push 和 PR 上执行 Node/Python 测试、workflow shell 语法和容器构建。完整 ImmortalWrt 编译耗时较长，需服务部署后从网页触发；源码测试通过不等于固件已编译或通过设备验收。
