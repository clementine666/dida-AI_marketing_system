# 飞书云文档读取脚本

## 脚本

```powershell
cd multi-agent-marketing-system

# 读取营销活动流程图文档
py -3.11 scripts/feishu_read_docx.py "https://didatravel.feishu.cn/docx/N0V5dJWHtom5BsxzlEXcJ2nqnlh" -o docs/feishu_import/营销活动流程.md

# 读取 8/18 会议纪要
py -3.11 scripts/feishu_read_docx.py "https://didatravel.feishu.cn/docx/FOp5d9wpOoOP8jxNW5ncMxADn4c" -o docs/feishu_import/会议纪要对齐.md
```

## 凭证配置（二选一）

### 方式 A：用户访问令牌（推荐，个人文档最快）

1. 飞书开放平台创建应用或使用已有应用
2. 获取 **user_access_token**（需 OAuth 或开发者工具）
3. 设置环境变量：

```powershell
$env:FEISHU_USER_ACCESS_TOKEN = "u-xxxxxxxx"
py -3.11 scripts/feishu_read_docx.py "文档链接" -o docs/feishu_import/out.md
```

### 方式 B：应用 tenant_access_token

1. 在 [飞书开放平台](https://open.feishu.cn/) 创建企业自建应用
2. 开通权限：`docx:document:readonly`
3. 发布应用并在目标文档添加该应用（文档右上角 … → 添加文档应用）
4. 写入 `config/integrations.yaml`：

```yaml
feishu:
  app_id: "cli_xxxxxxxx"
  app_secret: "xxxxxxxx"
```

或环境变量：

```powershell
$env:FEISHU_APP_ID = "cli_xxx"
$env:FEISHU_APP_SECRET = "xxx"
```

## 限制说明

| 能力 | 说明 |
| --- | --- |
| ✅ 纯文本 | `raw_content` API，标题、段落、列表文字 |
| ❌ 流程图结构 | 图中节点/连线不会结构化导出，仅可能有少量文字 |
| ❌ 图片 | 不下载图片，需对照飞书原文 |
| ✅ Wiki 链接 | 支持 `/wiki/{token}` 自动转 document_id |

导出后可将 Markdown 交给 Cursor 做流程对齐分析。

## 常见错误

| 错误 | 处理 |
| --- | --- |
| 未配置凭证 | 配置 app_id/secret 或 user_token |
| 1770032 无权限 | 文档添加应用，或换 user_access_token |
| 1770002 not found | 检查链接是否有效、文档是否删除 |
| 1770033 内容过大 | 分段复制或联系管理员 |
