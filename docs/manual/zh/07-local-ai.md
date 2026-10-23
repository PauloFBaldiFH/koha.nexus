# 7. 本地 AI

[目录](README.md)

## 配置与资源

按 a 打开 **AI**。提供者配置、Ollama、MARC Replace 和 staff 助手在同一页面，但设置提供者不会自动安装所有工具。先阅读 CPU/RAM 警告，避免拖慢 Koha。

在 **Ollama on this server** 使用 **Check Ollama**，需要时 **Install Ollama**，再选择并 **Download**。下载需网络和磁盘。选择 **Local Ollama**，核对默认 `http://127.0.0.1:11434`。用 **Use for chat** 或 **Use for cataloguing** 指定用途；图片需要视觉能力，纯文本选择不能读图。**Test connection** 或 F5 测试，**Save** 或 Ctrl+S 保存；填好表不等于保存。

聊天选择为空时按配置使用视觉选择。**Load models** 查询提供者列表，失败时内置候选列表不代表已安装。下载占磁盘，加载回答占 RAM。**Free memory** 卸载内存但不删下载，下次请求可以重新加载。即使选择远端提供者，Ollama 控件仍可显示；务必核对已保存的提供者与 URL，不能因已安装就认定请求留在本地。

## MARC Replace 与图片编目

安装或更新工具，检查编译和 staff 快捷链接，再开 **MARC Replace**。每次处理一条：选择 `.mrc`、`.xml` 或粘贴文本，填正确 `biblionumber`。留空表示新增，可能造成重复。**Preview** 比较现有记录与建议，核对题名身份后才确认。

替换保留现有册，排除输入文件的册字段。旧版可下载 MARCXML，按页面提示以相同 `biblionumber` 再提交以恢复；不能替代完整 backup。

**AI cataloguing** 接受清晰封面、题名页及背面照片，格式 JPEG、PNG、WebP，至少一张。选择框架或要替换的记录，按 **Read the photos** 等待草稿。逐项核对题名、责任者、出版、ISBN、分类及缺漏，修正 MARC 后再写入。ISBN 校验位正确不证明版本相同；分类须按本馆采用的表审核。草稿不保存册字段。

## 助手与隐私

**Install, update or remove the assistant** 管理 staff 首页助手，占用原新闻块位置，不影响 OPAC 新闻。它通过 Koha 检索及预定义读取查询工作，不执行 AI 任意编写的 SQL。

建议不等于已修改。核对目标、现值、提议及后果后才 **Approve & Execute**；操作遵守馆员权限，记录已变可能拒绝旧建议。可查看已确认的变更。清聊天或移除助手不会撤销执行过的动作；移除删除保存的对话，但保留确认变更记录。

监测 CPU、RAM 和 Koha 响应，变慢时不要重复启动大任务。不同硬件所需内存、磁盘和响应时间待确认。远端提供者收到请求数据，先核对本馆隐私政策，不用真实读者资料测试。界面费用标签不保证服务免费。

## 已核对的源码

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
