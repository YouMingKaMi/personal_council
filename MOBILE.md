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

## 个人推进台扩展（2026-10-26）

原 v1 六类提交字段不变。新增两个 kind：

- `problem`：date、domainId、title，body / next 可省略；创建独立问题并保留实际记录日期。
- `progress`：date、domainId、body，problemId 可为 null；进入领域进展或对应问题。

配置在已启用推进台时增加 domains（仅 id/name）与 problems（仅未解决、未移除问题的 id/domainId/title）。不会发布问题正文、进展正文、计时明细或领域目标。手机和电脑检查表单共用同一适配器，领域变化后清空问题选择；失效领域／问题明确报错，原提交保留，允许检查修改后确认。新中转站同时接受旧四字段配置和扩展配置，旧离线消费／任务请求仍可确认。

## 2026-10-27 方案录入扩展
新增 `kind=plan`：date/domainId/problemId/title，body 可省略；创建问题下的持久方案。原 `progress` 请求可选添加 planId，指定时必须与 domainId、problemId 同属；省略时保持原领域／问题进展的含义。新旧字段均不改名、不改类型，不根据正文自动猜归属。
配置可增加 plans，每项严格仅 id/domainId/problemId/title，供手机和电脑审核表单选择；正文、计时和历史不发布。中转站兼容原四字段配置、domains/problems 扩展及 plans 扩展。方案／问题选择变化时清除下级旧选择。失效引用明确报错，原提交仍在收件箱，用户检查并修正后确认。旧手机离线的 problem/progress/消费等请求照常接受。方案完成或移除后不出现在新选择中，既有正式记录引用继续保留。

## 手机工作台计时（2026-10-27）
手机新增独立“工作台”页，按领域／可选问题／方案开始，支持暂停、继续、结束、取消与撤销取消。使用持久保存的开始／结束时间计算，锁屏或页面挂起不依赖后台逐秒运行；刷新恢复正在进行或暂停的计时。结束后可写进展，再发送至原中转站。Mac 离线时中转站照常暂存；电脑收件箱确认后才计入 advancement.sessions 与按日／按月统计。手机计时不占用或停止电脑当前计时。

新 `kind=focus`，封套仍为 v1：payload 为 date（首个有效时段的北京时间日期）、domainId、可选 problemId／planId、title、note、segments（按顺序且不重叠的 `{start,end}` 整数 Unix 毫秒）、durationMs（片段总和）。最多 1000 段、总时长 30 天；暂停间隙不计入，跨日按原始片段拆分。审阅时可选 adjustedDurationMs（整数毫秒，0—24 小时），明确修正后按所选日期补记，original 保留全部原始片段。已发请求冻结内容和稳定 ID，旧九类请求不变。

审批校验领域／问题／方案归属，重复确认只入库一次；进展跟随同一事务追加。与已保存或正在运行的电脑时段重叠时阻止直接确认，待处理原稿保留，允许核对／修正用时。手机与电脑不会自动合并重叠计时，也不覆盖旧记录。新配置可增加 focusDomainIds（仅公开给本人手机的领域 ID 列表），旧四字段配置和原 domains/problems/plans 配置继续接受；不发送领域目标、历史或时长数据库。

计时存储独立于原录入草稿；结束后先持久保存冻结提交，再写入待发送队列，成功后才清除本机当前计时。重试与响应丢失沿用同 ID，不重建已发送请求。现代浏览器可用 Web Locks 时串行处理同浏览器多标签操作；其它浏览器采用最新本机存储与跨页通知。设备时间倒退或异常跨越 30 天会暂停并提示检查。关闭／锁屏不等于暂停；忘记结束时需核对实际用时。清除网站数据仍会删除未上传的本机草稿与计时。

中转站追加静态白名单 mobile/timer-model.js、mobile/timer-workbench.js，并接收新版 focus 配置与提交；不会开放远程审批。手机图标沿用 static/favicon.ico、icon-32.png、icon-180.png。Service Worker 更新 shell 缓存（含计时模块与图标），不清空 localStorage，不强制重载当前计时页。

## 2026-10-27 长期使用与近期任务
新增 taskPlan：payload.date 是录入日期（封套既有自然日语义），title、schedule（recent/day/deadline）；day 必须 scheduledDate，deadline 必须 deadline，可选 deadlineTime=HH:mm（北京时间）。recent 不填 scheduledDate/deadline/time，不把录入日期变成任务安排日。电脑转换为同一 task 的 schedule/date/deadline/deadlineTime，后续安排编辑不更换 ID。旧 task 仍仅 date/title，直接安排到该日，不接受改名或 null date。
expense 可选 allocation={startDate,expectedEndDate}，支持 null；旧五个字段完全不变。新增手机消费仅发送预计使用期，endDate/resaleCents 结算保留在电脑端办理，避免把旧消费覆盖成新消费。金额保持 amountCents 整数分，审核与总体验证均检查日期先后，不丢弃无效字段。已发送封套 ID 和内容冻结，升级 Service Worker 不清空草稿／队列／当前计时；旧离线数据继续接受。
部署时除既有文件，还需 expense_allocation.py、task_domain.py、static/expense-allocation.js、static/expense-allocation-form.js、static/task-model.js。更新手机 app/style/sw、共享 capture-form、capture_contract 和静态白名单，保留服务器凭证及待处理数据库，更新后验证新三个 JS 均为 200。配置增加 taskPlan kind，不增加用户私人历史字段；电脑后台同步后发布最少录入配置。无远程审批权限扩张。

手机界面将每日与近期合为单个“任务”入口，内选近期／具体日期／截止日期。新界面继续使用已支持的 taskPlan，不改旧 task 的 date 含义；旧 task 草稿、队列和回执保留，在缺少 taskPlan 配置时仍展示旧入口。optional 的显示名改为非必要，封套 necessity 值不变，旧手机发送 optional 仍以同一必要性确认入库。
