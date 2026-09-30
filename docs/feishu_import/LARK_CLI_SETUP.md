# 飞书 Lark CLI 安装与授权

> 日期：2026-09-04  
> **目的**：用 CLI 读取 Wiki/SOP 全文与白板，再重新梳理 SOP 流程

---

## 1. 已完成的安装

| 步骤 | 状态 | 说明 |
|---|---|---|
| `@larksuite/cli` 全局安装 | ✅ | `lark-cli version 1.0.93` |
| Cursor Agent Skills | ✅ | 28 个 skill 已复制到 `~\.agents\skills\`（含 `lark-wiki`、`lark-whiteboard`、`lark-doc`） |
| 应用配置 `config init` | 🟡 **待你完成** | 见下方授权链接 |

验证命令：

```powershell
lark-cli --version
```

---

## 2. 请你现在完成：应用配置（约 2 分钟）

在浏览器打开（或扫二维码 `lark-cli-auth-qrcode.png`）：

**https://open.feishu.cn/page/cli?user_code=SZLU-JP4T&lpv=1.0.93&ocv=1.0.93&from=cli**

按页面提示创建/绑定飞书应用并完成授权。终端里会显示「等待配置应用…」，完成后自动继续。

> 若链接过期，在终端重新运行：  
> `lark-cli config init --new --lang zh`

---

## 3. 配置完成后：用户 OAuth 登录

应用配置成功后，再执行（需浏览器二次授权，读取你的 Wiki 文档）：

```powershell
lark-cli auth login --recommend --as user
```

检查状态：

```powershell
lark-cli auth status
lark-cli config show
```

---

## 4. 配置完成后我们将读取的文档

| 文档 | URL / Token |
|---|---|
| 营销协作系统流程问题档案 | `https://didatravel.feishu.cn/wiki/MLwxwT1nViDDvpk94YlcVVD8n4d` |
| 网站活动营销 SOP（侧边栏） | 待 CLI 列出知识库节点后定位 |
| 画板 | blockToken `BftawFL9thBCDVbA6awcgg27nbd`（用 `lark-whiteboard` skill） |

---

## 5. 与项目集成的关系

- 项目 `config/integrations.yaml` 中 `feishu.app_id` / `app_secret` 仍为空  
- **CLI 授权**与**系统后端集成**可共用同一飞书应用，配置完成后可将 App ID/Secret 填入 `integrations.yaml`（勿提交密钥到 git）  
- SOP 梳理顺序：**先 CLI 读全量 → 更新 `docs/SOP_*.md` → 你再签字 → 再开发**

---

## 6. 常用命令速查

```powershell
# Wiki 节点详情（用户身份）
lark-cli wiki +node-get --node-token "https://didatravel.feishu.cn/wiki/MLwxwT1nViDDvpk94YlcVVD8n4d" --as user --format json

# 列出知识空间
lark-cli wiki +space-list --as user --format json

# 帮助
lark-cli wiki --help
lark-cli doc --help
```
