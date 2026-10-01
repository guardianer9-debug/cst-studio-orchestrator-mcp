# PiDeck CST集成增量

基于PiDeck v0.7.1的独立CST桌面修改。上游固定基线与本地桌面提交见[manifest.json](manifest.json)，可公开补丁见[0001-session-workbench.patch](0001-session-workbench.patch)。本仓库发布补丁；没有向PiDeck上游或FDTD工作区推送。

在与manifest基线相符的独立PiDeck checkout上使用`git am 0001-session-workbench.patch 0002-workbench-handoff.patch 0003-schematic-pins.patch 0004-desktop-isolation.patch`，保留已有未提交改动。然后使用既有依赖执行typecheck/test/build。完整桌面目录和实际启动配置见本机固定阅读入口；不在公开仓库写个人绝对路径。安装包发布和跨平台验收尚未完成。

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

## W4 桌面启动隔离（2026-10-01）

第四个补丁 `0004-desktop-isolation.patch` 在0003之后应用。删除启动时对共享Pi扩展目录的清理；内置扩展继续从本应用resources经显式参数加载。同步生命周期日志写入profile/logs，关闭请求、正常退出、渲染/子进程异常与启动身份可追溯；外部启动器另存退出码。强制终止不保证有内部日志，也不能仅凭退出码判定是谁终止进程。

[start-cst-pideck.ps1](start-cst-pideck.ps1) 使用PowerShell 7，传入AppRoot、RuntimeExe、Profile三个绝对路径，DebugPort可选。先在专属CST profile中启用singleInstance。启动器复用PiDeck原有按profile/version隔离的锁及聚焦通信，重复点击恢复原窗口，不实现另一套锁，也不结束其它实例。后台监护进程仅等待退出并记录，不自动重启、不启动CST求解。

本机复制既有Electron 38.8.6完整dist到CST专属目录，75个文件逐一SHA-256一致（339856627字节）。没有使用本地另一份43.4.0，也没有联网安装或升级。保留现有profile、项目Pi loader及会话目录；Pi CLI、凭据/模型配置和部分全局设置仍沿用，不能称为全部环境完全隔离。FDTD生产目录仅作为运行文件的只读复制来源。

验证：typecheck及build通过；全量2145通过、2跳过。新增生命周期同步落盘/写入失败容错测试，保留移除启动清理的回归断言。首轮5项失败：4项因编辑引入CRLF导致源码匹配断言失败，恢复LF后通过；1项既有遥测测试把UTC时间写成当地日期，改用明确当地日期fixture后通过，未改产品遥测行为。真实Windows双开、CST正常退出重开、托盘恢复及重复启动复用通过；全局9个扩展内容未变，FDTD主进程与Agent进程的PID/创建时间未变。首次Playwright常规截图超时，后用CDP非surface截图成功并检查。未调用产品Provider、未启动新网格/task/求解，长期并行Agent与双求解压力测试待验证。

## W5知识工具更新

本增量在共享MCP后端，桌面补丁无需变化。`cst_vba_help`现在查询本机官方HTML，保留原名称；Pi适配器中的完整名称通常为`cst_cst_vba_help`，以connect返回为准。项目指引应要求来源、域、分页和读回验证。[正式接口与验证说明](../../docs/cst-agent/official-help.md)。现有活跃后端需保存、释放后正常重连加载新代码，不对未保存工程强制热更。
