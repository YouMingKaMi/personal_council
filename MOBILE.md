# 手机随手记 · 接口 v1

手机只负责新增记录；电脑负责确认入库。手机和电脑不互相覆盖整份数据库。云端只保存录入配置、手机提交和处理状态，不接收完整个人数据库。

## 第一版

- 支持花销、每日任务、编年史、想法暂存、信息原料、习惯记录。
- 手机网页支持安卓与 iPhone；正文可使用系统键盘语音输入。没有接外部 AI、录音或图片识别。
- 一次在线打开后缓存网页；未发送记录、各功能草稿保存在该浏览器。联网事件、重新打开和手动重试会补发。浏览器后台被挂起时不能保证即时发送；清除网站数据／无痕窗口结束会丢失尚未发送的本机草稿。
- 已提交不等于已入库。Mac 每 20 秒尝试接收；侧栏“手机收件箱”显示待确认记录。点确认直接保存，或先更正字段再确认；不采纳的原文保留。
- 习惯记录采用“当日总值”，已有当天记录绝不静默覆盖。此时在记录库处理已有记录，手机条目可以不采纳。
- 月报、个人思考、重要日子、国库与历史修改尚未提供手机录入；之后新增相应契约与表单。

## 稳定契约

请求封套字段固定：`version: 1`、稳定 `id`、`kind`、带时区 `createdAt`、`payload`。

| kind | payload |
| --- | --- |
| expense | date、title、amountCents（整数分）、categoryId、necessity（necessary/optional/undecided） |
| task | date、title |
| chronicle | date、text、可选 endDate（null 或 YYYY-MM-DD） |
| ideas / materials | date、body（保留原文与换行） |
| habit | date、habitId、versionId、kind，及对应 value / checked / items |

金额禁止浮点元；日期是记录发生的自然日 YYYY-MM-DD，不按上传时刻改日期。分类、习惯规则和清单使用稳定 ID，不按显示名称匹配。手机可获得分类路径与版本化习惯定义，但不获得习惯完成情况或其他历史。

布局或文案改变不得改已有字段语义。新增功能单独声明 kind/字段；不支持的版本、类型或未知字段明确报错，不能丢弃后继续保存。破坏性变更必须新增版本并保留旧适配器，包含“旧手机离线记录在电脑升级后上传”的兼容测试。不可自动改变已发出请求的内容或 ID。

`capture_contract.py` 校验并适配到既有 schema v8；`static/capture-form.js` 为电脑检查表单和手机共享字段适配器。已有电脑录入继续使用原业务模型；转换输出由既有后端 domain 校验。

## 数据流与原子性

1. 手机先持久保存待发请求，提交 `/api/submit`。中转站用 ID + 内容一致性幂等接收；网络丢失响应时同 ID 重试。
2. `mobile_bridge.py` 由 Mac 发起出站 HTTPS 请求，发布最少录入配置并获取待处理条目。
3. `mobile_inbox` 表保留原提交、审核结果和记录标识。确认时使用 SQLite 单事务读取最新正式状态、校验、保存状态与快照、写回执。电脑旧窗口继续受 revision CAS 保护。
4. 手机凭证只能提交和查看收件箱。电脑凭证只能发布配置、拉取待处理和回传 imported/rejected；中转站不存在远程确认入库或读取个人库的接口。
5. 回执失败会重试；同 ID 不重复写入。待处理接收、确认和不采纳均触发现有数据库备份。完整 SQLite 备份包含待处理和回执表；单纯导出业务 JSON 不包含该表，已入库的业务记录在 JSON 中仍保留。

中转站数据仍存在服务器上，并非端到端加密；使用 HTTPS、专属随机连接码、分离权限和受限文件权限。不要向他人分享连接码。旧提交和已处理内容保留在中转站，手机最多展示最近 500 条；第一版不自动清理，待处理上限 500 条。连接码轮换需同步更新电脑配置／重新登录手机。

## 部署与恢复

中转站仅需 Python 3.9+（部署脚本使用较新 pathlib API，建议 Python 3.11）、Caddy 和 systemd。只部署：`capture_relay.py`、`capture_contract.py`、`mobile/{index.html,app.js,style.css,sw.js}`、`static/capture-form.js`。不部署 server.py、seed.json、query、个人数据库或本机配置。

首次安装脚本 `mobile/install_relay.py` 接收 HTTPS origin（独立 9443 端口），建立非 root 服务账号、受限数据目录；验证并备份 Caddy 配置后追加独立站点。源码 `/opt/personal-council-capture/app`，数据 `/var/lib/personal-council-capture`，服务 `personal-council-capture`。对外只开放 HTTPS，Python 只监听 127.0.0.1:8890。已有站点不改。

服务器首次启动创建仅服务账号可读的 `credentials.json`，内含 phoneToken 与 desktopToken，不打印、不提交 Git。
Mac 数据目录的 `mobile-bridge.json`（0600）含 `url`、`desktopToken`。该凭证文件不在 Git 或现有数据库备份内，换机恢复后需重新配置。手机输入 phoneToken 换取 HttpOnly、SameSite=Strict、Secure 会话 cookie；连接码不放 URL。

服务器重启由 systemd 恢复；Mac 登录后由现有本地后台服务恢复。服务器磁盘损坏仍可能丢失尚未到达 Mac 的提交，应另将服务器数据目录纳入你自己的私人备份。不要把同步当作备份。

回退电脑程序可恢复升级前代码，保留数据库和新表；旧程序忽略手机收件箱。回退中转站时停用该独立 service、移除带标记的独立 Caddy 站点并验证后 reload，不删除数据目录。恢复已入库记录按原 RECOVERY.md；收件箱亦需恢复 SQLite，不仅业务 JSON。

## 验证

`tests/test_mobile_capture.py` 覆盖：Unicode 原文、所有首版文本类型、金额与日期校验、未知版本/字段、重复 ID 内容冲突、并发确认、分类失效、习惯历史保护、事务回执、备份恢复、手机/电脑权限隔离及完整中转流程。另运行原有 Python 与 Node 回归，并在独立测试数据下做手机尺寸与电脑 UI 验证。
