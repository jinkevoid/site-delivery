# 局点交付管理系统

目前为可运行的开发演示版本，包含登录、用户创建、局点创建和修改、进展历史、待办、附件回收站、联系人、群聊、标签、基础自定义字段、离线国家分布图、基础审计、外部令牌、状态管理和 Excel 导出。尚未完成数据库迁移、完整审计详情、外部请求幂等、完整筛选界面及自动 SFTP 备份，不可用于生产。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
ADMIN_USERNAME=admin ADMIN_PASSWORD=your-password .venv/bin/uvicorn app:app --reload
```

首次启动时通过环境变量创建管理员；之后更改环境变量不会重置已有管理员密码。API 文档位于 `/docs`。时间输入建议携带时区，数据库保存 UTC。

管理员可以在设置中创建绑定到用户的外部访问令牌，令牌只显示一次。外部工具可通过 `Authorization: Bearer <令牌>` 调用 `/api/v1` 接口，服务端执行绑定用户的权限。当前外部写入没有幂等去重，调用方应避免盲目重试。

浏览器访问 `http://127.0.0.1:8000/`。也可设置 `ADMIN_USERNAME`、`ADMIN_PASSWORD` 环境变量后执行 `docker compose up --build`；数据存放在 `data/`。演示数据需自行创建。

执行测试：`.venv/bin/pytest -q`。

备份脚本 `backup.py` 支持通过环境变量配置 SFTP：`SFTP_HOST`、`SFTP_PORT`、`SFTP_USER`、`SFTP_PASSWORD`、`SFTP_DIRECTORY`、`SFTP_KNOWN_HOSTS`。脚本对数据库使用 SQLite 在线备份，并打包快照引用的附件；SFTP 主机密钥必须预先放入 known_hosts。定时执行、保留策略和自动恢复尚未实现。
