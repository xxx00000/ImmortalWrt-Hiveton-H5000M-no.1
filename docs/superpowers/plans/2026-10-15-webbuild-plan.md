# Hiveton H5000M WebBuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在用户现有编译仓库上交付可运行的中文定制网页、安全后端与私人固件下载。

**Architecture:** 同源 Node.js 服务提供网页和 API，GitHub App 完成登录与编译调度。Actions 使用 OIDC 领取任务配置并上传结果，现有固件构建保持增量修改。

**Tech Stack:** Node.js 24 LTS、内置 HTTP/crypto/node:test、jose、Python 3、Docker Compose、Caddy、GitHub App/OIDC。

**Spec:** [已批准规格](../specs/2026-10-15-webbuild-design.md)

## Global Constraints

- 仅写 Hiveton-H5000M-WebBuild 分支，不修改 main，不自动合并。
- 保留现有插件、模组管理、驱动、源码版本与固定提交，以及原有镜像安全检查。
- 原有插件默认全部保留；仅本次额外添加的软件包可以删除。
- LAN 默认 10.0.0.1/24；SSID 默认 A3KM、A3KM+；无线 WPA2-PSK。
- 密码不进入模板、URL、公开仓库、公开日志或公开 artifacts。
- 单实例、HTTPS、7 天结果保留期、失败配置最多保留 24 小时。
- 没有真实证据不宣称已上线、固件编译通过或硬件可刷。

## Review Focus

- 网络前缀改变后 DHCP 池越界：任务 1 拒绝网络/广播地址和池溢出。
- 浏览器导入模板带未知字段或秘密：任务 1/5 拒绝未知字段并清除密码。
- 后端重启或重复提交：任务 2/3 持久化幂等键，触发结果不确定时不自动重复派发。
- OIDC 有效但属于其他 run、ref 或 workflow：任务 3 拒绝领取和上传。
- 已存在 AP、无线设备顺序变化或缺少 band：任务 4 保留其他接口，不猜测未知设备。

---

### Task 1: 配置模型与边界校验

**Files:** Create `webbuild/shared/config.mjs`, `webbuild/policy.json`, `webbuild/package.json`; Test `webbuild/test/config.test.mjs`。

**Interfaces:** `validateConfig(input, policy, {secretsRequired}) -> normalizedConfig`；`toTemplate(config) -> publicConfig`；`preview(config) -> redactedConfig`。模型包含 schemaVersion、author、notes、hostname、timezone、lan、wifi2g、wifi5g、theme、extraPackages。白名单与保护基线由仓库配置生成并版本化。

- [ ] 写失败测试：默认地址与 SSID；/24、/30 合法池；/31、广播地址、池溢出、控制字符、超长 UTF-8 SSID、非法密码、未知包和未知字段被拒绝；模板不含密码。
- [ ] 运行 `node --test webbuild/test/config.test.mjs`，确认因模块缺失失败。
- [ ] 实现模型与校验，包名仅 ASCII 包名字符且必须命中 policy；主题与时区均为白名单；不接受 shell 或自由构建参数。
- [ ] 重跑测试通过，提交 `feat: validate WebBuild configuration and protect package baseline`。

### Task 2: GitHub App、会话与加密存储

**Files:** Create `webbuild/server/settings.mjs`, `github.mjs`, `store.mjs`, `session.mjs`; Test `webbuild/test/auth-store.test.mjs`。

**Interfaces:** `GitHubClient` 提供 OAuth 身份、安装令牌、仓库权限与固定 workflow 请求；`Store.createTask(ownerId, config, idempotencyKey)`、`readTask(ownerId,id)`、`expire(now)`；`Session.requireUser(request)`、`verifyCsrf(request)`。

- [ ] 写失败测试：OAuth state 重放、错误 Origin/CSRF、会话过期、权限撤销、其他用户读任务、加密文件损坏、秘密过期及幂等键冲突。
- [ ] 运行对应 node:test，确认预期失败。
- [ ] 实现 GitHub App JWT 与安装令牌缓存；OAuth 回调固定地址；Cookie 安全属性；AES-256-GCM 加密配置、原子文件写入、私有目录及清理；从标准输入调用 openssl 生成 root 哈希，不将密码放进参数。
- [ ] 测试通过，提交 `feat: add authenticated encrypted WebBuild service foundation`。

### Task 3: 调度、OIDC、运行关联与私有结果

**Files:** Create `webbuild/server/tasks.mjs`, `oidc.mjs`, `results.mjs`, `http.mjs`, `main.mjs`; Test `webbuild/test/api.test.mjs`, `oidc.test.mjs`。

**Interfaces:** `/api/session`、`/api/policy`、`POST /api/tasks`、`GET /api/tasks`、`GET /api/tasks/:id`、`GET /api/tasks/:id/files/:name`；`POST /internal/tasks/:id/claim`、`PUT /internal/tasks/:id/result` 使用 OIDC。定制运行标题为 `WebBuild <UUID>`。

- [ ] 写失败测试：伪造 JWT、错误 audience/仓库 ID/ref/workflow、错误 run ID、重复领取、上传超限、路径穿越、越权下载、GitHub 派发超时及延迟运行出现。
- [ ] 运行测试，确认失败。
- [ ] 用 jose 验证 GitHub JWKS 和全部绑定声明；通过 GitHub API 再核对 run 名称、head SHA、事件和 workflow，原子绑定 run ID；同 run 重试允许受限领取，其他 run 拒绝。重复派发需要显式重试，避免盲目重发。
- [ ] 实现上传临时文件、大小与文件名限制、完成后原子发布与清理；下载每次重新检查仓库权限。HTTP 默认拒绝 CORS、设置 CSP、限流、请求上限及不回显输入的错误。
- [ ] 测试通过，提交 `feat: dispatch verified builds and serve private firmware results`。

### Task 4: 固件生成器与 workflow 增量集成

**Files:** Create `scripts/webbuild-config.py`, `scripts/webbuild-transfer.py`; Modify `.github/workflows/h5000m-build.yml`, `files/usr/libexec/h5000m-firstboot`, `files/etc/uci-defaults/99-h5000m-defaults`, `scripts/validate-rootfs.py`; Test `tests/test_webbuild_config.py`, `tests/test_webbuild_workflow.py`。

**Interfaces:** 生成器接受权限受限 JSON 文件、wrt 路径与 policy 路径；生成额外包选择、UCI 配置和 shadow 哈希；transfer 客户端通过 Actions OIDC 请求 claim/result，秘密只存在临时文件。

- [ ] 写失败测试：用户值含引号/换行/命令替换不会执行；包选择被 defconfig 丢弃即失败；基线不被删除；顺序颠倒无线设备仍按频段配置；其他 AP 保留；旧配置恢复不被覆盖。
- [ ] 运行新增 Python 测试，确认失败。
- [ ] 现有 workflow_dispatch 增加可选 task_id；新分支增加独立质量检查 workflow，只有明确派发才执行固件编译。定制路径移除 ROOT_PASSWORD 明文依赖，通过 OIDC 领取，生成器在原配置之后、defconfig 之前运行。
- [ ] 修改首次启动脚本读取定制值并保留默认路径。band 缺失时只接受可确认的 hwmode/能力，不确定则失败重试。保持模组所有权脚本及 AU/EHT 参数。
- [ ] rootfs 验收支持定制预期，避免现有硬编码 SSID/密码检查错误拒绝定制镜像；仍检查实际镜像、架构及保护包。
- [ ] 定制编译和诊断日志仅写受限文件；所有公开 artifact 步骤对定制任务禁用；仅上传经过批准的结果文件，不上传构建目录或秘密配置。完成/失败最后一步通知后端并清理。
- [ ] 运行全部原有及新增 Python 测试、shell 语法检查和 YAML 检查，提交 `feat: integrate private WebBuild tasks without changing firmware baseline`。

### Task 5: 中文响应式网页

**Files:** Create `webbuild/public/index.html`, `app.mjs`, `style.css`; Test `webbuild/test/templates.test.mjs`, `ui.test.mjs`。

**Interfaces:** 使用任务 1 的模型和任务 3 的 API；状态明确区分未登录、服务未配置、提交中、排队、编译、失败、完成及结果过期。

- [ ] 写失败测试：模板导出无秘密、导入覆盖旧密码为空、失败提示不泄漏输入、状态链接来自固定仓库且下载需会话。
- [ ] 运行测试，确认失败。
- [ ] 实现中文表单、默认配置、受保护插件清单、额外包增减、主题选择、脱敏预览、本地模板、导入导出、构建确认及任务轮询。使用 textContent 渲染用户内容，禁止 innerHTML 注入。
- [ ] 测试通过，在浏览器检查桌面/手机尺寸、键盘操作、导入失败与无后端配置状态，提交 `feat: add Chinese responsive WebBuild interface`。

### Task 6: 部署、验证和交付

**Files:** Create `webbuild/Dockerfile`, `webbuild/compose.yaml`, `webbuild/Caddyfile`, `webbuild/.env.example`, `.github/workflows/webbuild-check.yml`, `docs/webbuild-deploy.zh-CN.md`; Modify `README.md`。

**Interfaces:** Docker 数据卷存储 `/data`；GitHub App 私钥以只读 secret 文件提供；HTTPS 公网 origin 用于 OAuth 和 Actions OIDC audience。固定目标仓库/ref，部署配置不可由前端修改。

- [ ] 编写部署检查测试：缺少关键凭据时服务拒绝启动编译接口；错误 origin、可公开数据目录、无有效加密密钥都被拒绝；健康接口不泄漏配置。
- [ ] 提供 App 创建/权限/安装步骤、环境配置、启动、备份、密钥轮换、结果过期、回滚及真实联调说明；明确未上线时仅可本地预览。
- [ ] 运行全部 Node/Python 测试与可用的镜像构建检查；秘密哨兵扫描公开输出，比较保护包/驱动选择无删除；浏览器实测真实服务。
- [ ] 独立代码审查后修复问题，重新验证；推送指定分支并创建草稿 PR，不合并。重新读取 main SHA 证明未改变。
- [ ] 提供源码包、部署文档、本地网页入口和 PR；公网部署及真实 Actions 编译仅在凭据和服务器配置完成后验证，硬件验证单独标明。

## 计划自检

已覆盖配置、身份认证、秘密传递、基线保护、首次启动、网页、部署与测试。最需关注的实际风险是固件中必然包含 Wi-Fi 密钥，因此下载必须受控；公开 runner 编译期间不能打印生成文件；旧 rootfs 验收需同步适配定制预期。原始基线 10 项 Python 测试已通过。
