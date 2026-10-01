# 官方帮助与材料接口：W5交付

保留Pi/PiDeck/MCP框架和既有工具名。`cst_vba_help`现在从配置的`CST_PATH/Online Help/mergedProjects`读取本机官方HTML。`official_help_index.json`只保存对象、域、类别及相对路径；旧`vba_reference.json`及自动拼接伪示例已移除。没有官方源时返回unavailable，未索引对象/未找到方法返回not_found，同名不同域返回ambiguous。不把这些状态称为查询成功或接口已验证。

## 使用

Pi适配器通常把服务器前缀加到工具名前，例如`cst_cst_vba_help`。先connect，使用实际返回的完整名称describe/call。内部MCP名仍是`cst_vba_help`。

- `object_name=Solid, method_name=ChangeMaterial`：查询确切方法。
- `object_name=Solid, method_name=SetMaterial`：该官方页未找到，返回not_found。
- `object_name=Units, domain=3d`或`domain=schematic`：明确接口域，不自动混用。
- `object_name=Cylinder, section=example`：读取原文示例，不生成新的代码。
- 长内容按`next_offset`续读；默认每页10000字符，max_chars支持256–24000。
- `cst_list_vba_objects`：查看当前索引和本机文件是否存在；不代表完整CST API目录。

每个查询提供原文路径、起始行、文档SHA-256、配置的CST版本、官方文档标题。配置版本并非独立鉴定手册发行版。`runtime_verified=false`表示这次查询没有执行验证；不能因为读到官方方法就授予模型/求解验收。

经验继续由`cst_automation_guardrails`单独提供。本次新增材料修改规则，标明project_observation、官方出处和实测范围；不改写为官方断言。帮助解析仅读取HTML，不执行其中脚本或加载远端资源。查询帮助不会连接CST，并可在模型外部变化或任务占用时独立查询。

## 当前覆盖

31个对象/域条目：3D几何Solid/Brick/Cylinder/Component；Material；Units、Background、Boundary、Solver、Mesh；DiscretePort、PlaneWave、TimeSignal、Monitor、Probe。原理图Block/Net/CircuitProbe/ExternalPort/SimulationTask/Units。线缆CableBundleDefine/CableBundleFromCurve/CableBundleFromStartAndEndNode、NodeDefine/NodeSetGrounded、SegmentDefine、SingleWireDefine、TLMNodeSettings、CurrentMonitorDefine、ConnectorDefine。

31条本机官方文件全部存在且能提取方法。范围之外的接口仍需扩展索引或人工查证，不能推断为CST不支持。其它安装版本尚未实机验证。

## 修复及验证

`cst_assign_material`由错误的Solid.SetMaterial改为官方ChangeMaterial，执行后读取GetMaterialNameForShape；读回缺失/不匹配返回error并保留可能已部分执行的说明。材料修改纳入会话修改前读回/独立版本保护。显式保存结束编辑阶段，下一次修改再分支，避免保存后的模型被当作原编辑阶段继续修改。自动弹窗接受仍禁用，工具说明已改为unsupported；不再宣称可自动处理。

- 离线/Mock：618项通过。覆盖文档来源、无旧参考回退、同名域、原文示例、分页、源文件改变后hash更新、路径边界、HTML标题变体、共享参数说明、材料错误读回、保存后版本边界。
- 真实官方文件读取：31/31；Solid.ChangeMaterial成功、Solid.SetMaterial未找到；3D与原理图方法均从实际文件返回。
- 真实CST 2025.2接口：独立砖块Vacuum→PEC，实际读回正确、包围盒不变、修改另存独立版本、源文件SHA未变、保存关闭重开一致。网格单元保持0，未运行求解。
- 实际Pi：Grok/grok-4.7、medium，通过正式PiDeck会话和项目MCP查询上述两个Solid方法及SimulationTask.SetProperty，并使用分页。最终区分官方说明与实机验证。一次describe使用未加适配器前缀的名字无匹配，后用实际名称恢复；8次Pi工具调用，不包含建模/求解。
- 人工验收、数值精度、全体材料及其余MCP接口：本轮不声称通过。

## 失败与复测

先加入回归断言，旧代码3失败。第一次官方文件扫描只有16/31通过，原因为3D使用VBA-Heading-Object段落而DES使用h1；支持两种结构后31/31通过。第一次实机材料读回已成功，但版本隔离断言失败：显式save没有结束_edit_branch。保存失败现场为独立文件，修复后用v002新尝试重测通过，没有覆盖失败日志。新增保存测试初次因Mock工作目录与临时文件不一致被路径保护拒绝，修正fixture后通过。首次Pi测试在侧栏分页定位草稿超时，尚未发送请求；随后按稳定sessionId发送，实际Pi完成。原始记录、脚本、工程、调用收据和官方摘录均在本地固定入口下，不上传官方正文或原始会话。

## 使用现有会话

新后端加载新代码；本轮核对的两个旧手动偶极子会话，其原后端进程均已不存在，下次启动会加载新版。未强停用户的CST工程、后台任务或其它Pi会话。对其它正在运行的旧后端，应先保存和释放，再正常重连；不做带未保存状态的强制热更。项目AGENTS已加入官方来源和完整工具名指引。

这次交付补齐知识来源和一个材料修改闭环，不代表偶极子/222全案例自动验收器已经完成，也没有重做用户那两次建模。
