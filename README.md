# 局点交付管理系统

目前为可运行的开发演示版本，包含登录、用户创建、局点创建和修改、进展历史、待办、附件上传下载、联系人、群聊、标签、基础自定义字段和离线国家分布图。尚未完成完整筛选和分页界面、审计日志、数据库迁移、外部 API、SFTP 备份等功能，不可用于生产。

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
ADMIN_USERNAME=admin ADMIN_PASSWORD=your-password .venv/bin/uvicorn app:app --reload
```

首次启动时通过环境变量创建管理员；之后更改环境变量不会重置已有管理员密码。API 文档位于 `/docs`。时间输入建议携带时区，数据库保存 UTC。

浏览器访问 `http://127.0.0.1:8000/`。也可设置 `ADMIN_USERNAME`、`ADMIN_PASSWORD` 环境变量后执行 `docker compose up --build`；数据存放在 `data/`。演示数据需自行创建。

执行测试：`.venv/bin/pytest -q`。
