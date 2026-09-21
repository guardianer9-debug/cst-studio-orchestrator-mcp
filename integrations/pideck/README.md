# PiDeck CST集成增量

基于PiDeck v0.7.1的独立CST桌面修改。上游固定基线与本地桌面提交见[manifest.json](manifest.json)，可公开补丁见[0001-session-workbench.patch](0001-session-workbench.patch)。本仓库发布补丁；没有向PiDeck上游或FDTD工作区推送。

在与manifest基线相符的独立PiDeck checkout上使用`git am 0001-session-workbench.patch`，保留已有未提交改动。然后使用既有依赖执行typecheck/test/build。完整桌面目录和实际启动配置见本机固定阅读入口；不在公开仓库写个人绝对路径。安装包发布和跨平台验收尚未完成。

中央React面板挂在现有WorkbenchStage会话内容位置，CstWorkspaceService通过typed IPC定位稳定SessionRecord.id。文件索引调用Python session_workspace，不启动CST。明确打开/重新读取时按会话启动/复用workbench_service；Pi扩展也连接这个服务的HTTP MCP端点，两边共享CSTClient/操作锁。

项目根目录需本地`.cst-workspace.json`，包含python（现有Python绝对路径）、source（本MCP的src目录）、cst_path、cst_python（本机SDK目录）、cst_version。含机器路径的实际配置不提交。会话目录在项目sessions下，绑定收据在.cst-sessions；backend收据包含本地认证令牌，不上传。

[Pi扩展示例](cst-mcp.example.ts)使用既有pi-mcp-adapter；本机实际loader采用已有模块路径，无安装/升级。当前服务强制暂停自动运行，保留既有运行API；恢复自动运行需下一轮明确调整策略及验收，不因刷新触发。

UI已含目录/文件定位、独立版本参数修改、无求解刷新、CAD与真实Net拓扑和已有曲线。真实求解网格、完整电路/任务编辑和全部手动运行面板仍未完成。手动结果来源通过用户明确声明记录，不能用文件时间推断。

验证：TypeScript检查通过；PiDeck全量2138通过/2跳过；新增跨会话/路径逃逸测试通过。实际Windows窗口和CST只读/保存/修改证据留本地。实际Pi共享后端读回受Provider故障影响，未标为通过。
