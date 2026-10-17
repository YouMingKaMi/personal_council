# Personal Council 开发约定

先读 README.md、DEVELOPMENT.md 和 RECOVERY.md。

用户数据仅限本机和用户授权的备份目标，不得提交到 GitHub。不得修改原 Obsidian 库。代码更改先在独立数据目录、独立端口测试，正式入口固定 8765；8766 是跳转。

不得覆盖或删除正在使用的数据库。保持 schema、实体 ID、历史规则和导出兼容。保存失败和备份失败必须明确显示。日常统计使用真实记录。

交付前运行 tests/test_*.py、test_model.mjs、test_treasury.mjs 及相关场景，浏览器验证关键交互。代码发布与数据库备份分别确认，严禁上传 seed.json、data、backups、原文或导出数据。

恢复工具不可覆盖非空数据目录。只有恢复到独立目录验证通过，才算完成恢复演练。
