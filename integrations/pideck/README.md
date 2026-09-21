# PiDeck CST集成增量

基于PiDeck v0.7.1的独立CST桌面修改。上游固定基线与本地桌面提交见[manifest.json](manifest.json)，可公开补丁见[0001-session-workbench.patch](0001-session-workbench.patch)。本仓库发布补丁；没有向PiDeck上游或FDTD工作区推送。

在与manifest基线相符的独立PiDeck checkout上使用`git am 0001-session-workbench.patch 0002-workbench-handoff.patch 0003-schematic-pins.patch`，保留已有未提交改动。然后使用既有依赖执行typecheck/test/build。完整桌面目录和实际启动配置见本机固定阅读入口；不在公开仓库写个人绝对路径。安装包发布和跨平台验收尚未完成。

中央React面板挂在现有WorkbenchStage会话内容位置，CstWorkspaceService通过typed IPC定位稳定SessionRecord.id。文件索引调用Python session_workspace，不启动CST。明确打开/重新读取时按会话启动/复用workbench_service；Pi扩展也连接这个服务的HTTP MCP端点，两边共享CSTClient/操作锁。

项目根目录需本地`.cst-workspace.json`，包含python（现有Python绝对路径）、source（本MCP的src目录）、cst_path、cst_python（本机SDK目录）、cst_version。含机器路径的实际配置不提交。会话目录在项目sessions下，绑定收据在.cst-sessions；backend收据包含本地认证令牌，不上传。

[Pi扩展示例](cst-mcp.example.ts)使用既有pi-mcp-adapter；本机实际loader采用已有模块路径，无安装/升级。当前服务强制暂停自动运行，保留既有运行API；恢复自动运行需下一轮明确调整策略及验收，不因刷新触发。

UI已含目录/文件定位、独立版本参数修改、无求解刷新、CAD与真实Net拓扑和已有曲线。真实求解网格、完整电路/任务编辑和全部手动运行面板仍未完成。手动结果来源通过用户明确声明记录，不能用文件时间推断。

验证：TypeScript检查通过；PiDeck全量2143通过/2跳过；新增跨会话/路径逃逸测试通过。实际Windows窗口和CST只读/保存/修改证据留本地。W3已实际完成222和偶极子的手动修改→Pi读回/修改→UI同步→保存重开，包含Provider中断后的恢复提示与重试；不代表人工或数值验收。

## W3增量

[第二个补丁](0002-workbench-handoff.patch)承接0001，新增共用cst_edit_case入口、对象属性/线缆检查、负载/频段/tmax编辑、跟随后台新版本与历史选择。已绑定CST的草稿在重启后保留，Catalog启动核验使用持久项目映射，避免ProjectStore尚未异步加载时误删身份。

实际CST/Pi案例：222手动RES1=75Ω，Pi将RES2改60Ω；偶极子手动L82，Pi将r改1.2。保存重开一致，无新网格/task/求解。原始工程与Pi工具记录留本机，公开仅代码/脱敏证据。

项目Pi操作指引应明确：已配置的MCP无需猜测额外技能路径；新编辑意图用新operation_id，只有同一次中断恢复才复用原编号。实际工具会另存版本，不应在报告中写成“没有生成新版本”。

[第三个补丁](0003-schematic-pins.patch)修正符号背景遮挡连线的问题，电阻引线完整连接到实际API引脚标记，并明确索引口径。
