# 个人决策团 · Personal Council

在 Mac 上运行的本地个人系统：每日任务、习惯记录、事件式编年史、月报、Markdown 笔记和资产记录。Python 标准库后端、SQLite、原生 JavaScript 前端；默认只监听 `127.0.0.1:8765`。

此仓库仅包含程序和空白初始结构，不包含个人笔记、资产、数据库或云盘备份。

## 换电脑恢复

完整图文式操作步骤见 **[RECOVERY.md](RECOVERY.md)**。

1. 下载并解压本仓库。
2. 从 iCloud Drive 的“个人决策团备份”下载最近的 `council-…zip`。
3. 先双击 **恢复数据.command**，把备份拖入窗口，等到校验和恢复成功。
4. 双击 **启动个人决策团.command**，打开 http://127.0.0.1:8765/。
5. 登录 iCloud 后双击 **配置云盘备份.command**，重启服务并检查设置页的备份状态。

需要 Python 3.9 或以上。尚未恢复就启动，会创建空白数据；恢复工具会拒绝覆盖已有数据，请改在一份全新解压的程序目录里恢复。

## 代码与数据

- 程序在本机运行，数据默认在 `data/personal.sqlite3`；可使用 `python3 server.py --data /本地数据目录` 指定。
- SQLite 在线备份包含正式、测试两个空间和保存快照；先校验再写入配置的云盘文件夹。
- 默认数据目录放在本机，云盘只接收不可变的完整备份包，不直接同步正在使用的数据库。
- 网页设置显示的是文件夹写入结果，无法确认 iCloud 的上传完成状态。
- `8766` 只跳转到 `8765`；开发副本请使用 `8877` 和独立数据目录。
- 只有已保存记录进入备份；浏览器草稿、外观选择和 Obsidian 外部附件不包含。

## 检查

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_model.mjs
node tests/test_treasury.mjs
node tests/test_habit_completion.mjs
```

## 持续更新

修改前阅读 AGENTS.md。先在独立数据副本测试，再更新程序。新版本发布后把通过检查的代码同步到本仓库；备份不能替代代码版本保存。不要提交 `data/`、`seed.json`、`backups/`、数据库或任何带个人内容的导出文件。
