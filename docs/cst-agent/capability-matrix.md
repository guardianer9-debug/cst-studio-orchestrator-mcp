# CST Agent 功能覆盖与验收矩阵

> **W2（2026-09-21，当前优先级）**：先交付222原始工程、实际修改过程和稳定会话目录。本轮暂停新的自动网格、task和求解，不提高222预算重试。正常路径为“建模/修改 → 实际读回 → 保存完整工程 → 人工检查/运行”。运行能力保留；需要求解的验收仍待验证。本条覆盖下方历史轮次继续自动运行的要求。


版本：0.4.0 / D1；日期：2026-09-20；状态：**实际开发进行中；新增离线与真实 CST 证据，完整 Agent/人工验收未通过**。

当前以222孔缝腔体线缆耦合及官方偶极子等已选案例完整复现为交付终点。P1A/P1B仅为内部技术检查点；砖/RLC不是产品终点。下表阶段标签表示实施依赖，不表示每到一个标签就暂停等用户继续。CAP-305/306/309中222所需子集提升为本批P0，通用扩展仍按P1处理。

本文件是[整体方案](architecture-and-delivery-plan.md)的范围与验收索引，不是“全部已支持”清单。R1保留R0的56个CAP编号及全部工具栏转录项；本次工作树和审查输入没有截图原件，因此只核对转录的内部完整性，原图对照仍待补。下拉菜单和其他标签细项不猜测。

## D1–D3 增量状态（优先于下方 R1 历史基线）

| 能力 | 当前证据 | 未完成 |
|---|---|---|
| 实例/工程归属与源保护 | Mock 回归；222 独立副本实读、源哈希不变 | 关闭 RPC 偶发阻塞已记录，需复测稳定性 |
| 参数/3D/原理图/task 读回 | 222 实际表达式、bbox/材料、Net/Block、Tran1；属性签名修正 | 全字段读回复测、拓扑裁剪后一致性 |
| 3D/DS运行与停止 | 偶极子原生及受控worker新求解成功；官方AC任务执行中停止，通过归属核验后终止自有进程树 | 原生DS停止仍未证明；完整222、独立数值验证待完成 |
| 曲线/显示 | 真实MCP已导出新S11和两个方向图切面；四实体CAD逐一验证，实际PiDeck webview显示 | DS新V/I、完整Agent终态与数值独立验证 |
| 实际 Pi/PiDeck | 偶极子参数修改/读回/新求解/模型曲线发布已有实际Agent证据；包含开发者修复重试，最终报告另遇Provider错误 | 人工验收与独立数值验证待确认 |
| 222 新耦合 V/I | 原条件真实Tran1达到25.4GiB，因24GiB调试护栏停止；模型/网络/75→50Ω修改已通过 | 新完整V/I未取得；48GiB/6小时下一次预算等待负责人答复 |

证据索引：[测试与案例进度](delivery-evidence.md)，[踩坑记录](pitfalls.md)。以上均不是人工验收或论文数值对比结论。

## 1. 状态填写方式

每个能力后续至少登记六个独立维度：API 依据、实际读取、实际写入、实机自动化、PiDeck 可用、物理/数值验证。各维度取 `unknown / code_only / pass / fail / partial / unsupported / not_applicable` 等明确值，并附证据。

以下原有表中的“源码线索”以远端提交 `14b7f89d28a15b8c64af5c511d95bce1307a60ea` 为基线。R1详细核验表覆盖P0/直接相关P1；未列入详细表的维度均为 **unknown**，非unsupported。全部CST-PiDeck和独立数值维度目前unknown；既有FDTD证据不能跨后端计分。

证据简写：`R`=上述远端；`L1`=本地未提交增强；`H1/H2/H3`=CST2025本机Python/原理图/后台运行帮助；`E1–E4`=已读历史原始证据；`P1/P2`=本机版本与参考UI源码。完整定位见[主方案§18.4](architecture-and-delivery-plan.md#184-r1-本地只读核验登记)。`code_only`表示存在生成/调用代码，包含MsgBox等尚不能交付结构化读取的路径，不能读作“已可用”。

### 1.1 P0/P1 实际覆盖与验收落点

| 能力ID | 源码/本地增强与官方依据 | 读取 | 写入/执行 | 既有CST自动化证据 | PiDeck / 数值 | 最小验收与实施包 |
|---|---|---|---|---|---|---|
| CAP-001、102、312 | R `CSTClient.connect/new_project/open_project/save_project/disconnect`；H1；L1未解决绑定 | code_only：状态/路径；无完整快照 | code_only | partial E1：仅历史连接，未证明目标正确 | unknown / unknown | P1A明确PID/工程/归属、工厂不回退、detach不关闭；保存重开/双工程拒错 |
| CAP-002、006 | P2会话、模型/参数/结果面板；没有CST业务桥接 | unknown（CST） | unknown（CST） | unknown | unknown / not_applicable | CST-2同一可见Pi两轮修改/当前值追问；参数依据不靠聊天记忆 |
| CAP-003、303 | R `tools/import_export.py`导入/导出生成器、`project._build_export_vba`；文档解析并非本包已有管线 | code_only（文件接口）；对象映射unknown | code_only | unknown；工程文件存在不计运行 | unknown / unknown | 小CAD单位/部件/外部依赖读回；CST-2先本地可读文件，复杂STEP放CST-4 |
| CAP-004 | R `vba._load_vba_reference`为仓库JSON；schematic成员枚举；H1/H2/H3本机帮助 | code_only；官方段落本轮人工核验 | not_applicable | unknown | unknown / not_applicable | P1A按需本机章节；缺API或许可不编造；不建向量库 |
| CAP-005、115、219 | R `vba._handle_execute_vba`、`CSTClient.execute_vba/schematic_call`；H1/H2 | code_only（调用返回） | code_only（VBA/RemoteObject）；托管Python unknown | unknown | unknown / unknown | P1A显式域、部分失败不换域重放；原始Python后续可信模式，不以正则称沙箱 |
| CAP-007、104、311 | R `server.run_server`启动即connect；simulation共用启动路径；H1/H3 | code_only；错误可能当False | code_only；真异步/取消unknown | E2历史真实失败；E3示例缓存不计 | unknown / unknown | P1A先no-connect与收据；P1B逐域停止验证；不得借协议测试启动CST |
| CAP-101、109、112、113 | R `parameters.py`存储/重建，get为MsgBox/list为Debug.Print；CSTClient.status；H1 | code_only但不满足结构化表达式/值契约 | code_only | unknown | unknown / not_applicable | P1A真实单位、表达式/值、bbox/材料读回；默认不调用rebuild-and-solve组合 |
| CAP-103、302 | R `solvers.py/ports.py/boundaries.py`；L1用户信号；H1 | code_only/部分字段unknown | code_only | unknown | unknown / unknown | P1B/CST-3区分配置与启动；端口模式/方向、波形文件依赖和结果元数据 |
| CAP-107、108 | R `mesh.py`已有基础设置；L1增加全局/局部属性；实际网格导出未核 | code_only（信息生成器）；真实节点unknown | code_only（设置） | unknown | unknown / unknown | P1A不生成Mesh；后续比较设置与实际网格，三角面片不能代替；不是全CST网格通用导出器 |
| CAP-110 | R `model3d.add_to_history`；本地官方宏参考 | code_only（记录/导航）；完整历史读回unknown | code_only | 示例/宏文件仅参考 | unknown / not_applicable | 区分3D History、原理图操作日志及非History命令；不拿History当完整恢复日志 |
| CAP-114 | 参考PiDeck按需报告/下载；CST原生Report API未核 | unknown（CST报告） | unknown | unknown | unknown / not_applicable | CST-2/3生成版本绑定报告；下载/读取不调用模型或启动求解 |
| CAP-201、207、214、304 | R `schematic_create_rlc/external_port`及Block属性；H2 | code_only：当前list未含完整属性/本地单位 | code_only | unknown | unknown / not_applicable | P1A补实际R/L/C值、单位、端口阻抗和引脚读回，不重做创建器 |
| CAP-208 | 通用schematic/本地配方有Ground block思路；H2待核具体类型/签名 | unknown（参考节点语义） | code_only（配方），无专用已验封装 | unknown | unknown / not_applicable | P1A真实参考节点与网络连通；未取得读回时C0-SCH阻塞，不以图标替代 |
| CAP-210、211、212、220 | R `schematic_connect/list`的Net.GetComponentPorts；H2；布局/剪贴待核 | code_only（block/net）；布局unknown | code_only（连接）；断开/布局unknown | unknown | unknown / not_applicable | P1A引脚级连接表；CST-2派生简图，真实布局/拖放后移，不把布局变化当拓扑变化 |
| CAP-202、216 | L1 `schematic_create_transient_task`；H2 SimulationTask.Update执行含子任务、ValidateSetup只核设置 | code_only（返回所设值）；实际task属性读回unknown | code_only；原生DS取消unknown | E2是另一派生工程失败，不能代替用户222基准 | unknown / unknown | 当前案例必须创建/设置/读回task；Update走获准运行控制门，不能当普通刷新；不以“只做RLC”为由遗漏 |
| CAP-209 | H2 circuitprobeobject；本地脚本有CircuitProbe配方 | unknown（完整观测契约） | code_only（配方） | unknown | unknown / unknown | P1B/CST-3先建网络再探针，核参考节点/正方向/实际DS结果 |
| CAP-205、215、217 | R通用schematic可访问候选对象；完整依赖恢复未做 | unknown（全依赖） | unknown | unknown | unknown / unknown | P1A只自包含副本；CST-4显式依赖清单/缺失阻断，不声称一个.cst即全部 |
| CAP-301 | R geometry/boolean/transforms/materials生成器 | code_only/对象级查询缺口 | code_only | 原生示例可参考，非MCP新验收 | unknown / unknown | C0-3D从零和重开副本，实物bbox/材料/关系与修订对应 |
| CAP-305、306 | R CS/DS factory+VBA通道；L1联合前提诊断/任务；本地CableStudio配方 | partial code_only；全链映射unknown | code_only/配方 | E2是派生失败；222用户确认成功及较早原始记录与当前容器版本须分开核准 | unknown / unknown | 222所需能力本批优先，逐段核线缆—终端—电阻接地/探针—任务；不推迟至CST-4，不从零写已有通道 |
| CAP-307、308、309 | R `get_result`为get_3d+str；ASCII/Touchstone/远场导出；DS数值链未核 | code_only；结构化DS unknown | code_only（导出会覆盖/删除旧路径） | E3缓存和空摘要不可计本机PASS | unknown / unknown | CST-3逐run新目录；复数/轴/单位/参考面/方向/任务身份齐全，不以非空通过 |

P0按本批真实案例的必要能力逐步落实；按[主方案§14.1](architecture-and-delivery-plan.md#141-首批交付范围222耦合与官方算例完整复现)连续推进到模型、任务、运行、结果和产品交互验收，不以内部P1A/P1B通过关闭整批目标。

### 1.2 未提交增强清单与版本

静态声明计数：远端177、本地183；本地新增：

- `cst_automation_guardrails`、`cst_cable_cosimulation_status`：`tools/diagnostics.py`。
- `cst_set_mesh_properties`、`cst_set_local_mesh_properties`：`tools/mesh.py`。
- `cst_schematic_create_transient_task`：`tools/schematic.py`及`cst_client.py`。
- `cst_define_user_excitation_signal`：`tools/solvers.py`及`.usf`写入。

以上全部为L1，尚未合入本分支。原理图创建RLC、ExternalPort、Net连接及通用调用原本就已在R中。测试差异与业务差异分开，不因有新增测试就填通过。

本机帮助版本2025；历史失败日志为2025.2，示例缓存含2025 Beta；**当前运行build/许可证额度unknown**。CLI包0.85.1、参考Host SDK0.80.10、静态环境MCP SDK1.28.1分别记录；活动服务和窗口加载组合unknown。适配器2.34.0只核源码，实际安装/接入unknown。

长期目标与本批优先级分开：P0基础与当前案例所需闭环，P1更广的线缆/场路扩展，P2广度扩展。P2不是删除需求；222所需能力不能因旧类别为P1而推迟。

## 2. 基础与 Agent

| ID | 用户操作/能力 | 来源 | 优先级 | 源码线索/待核验 | 最小验收 |
|---|---|---|---|---|---|
| CAP-001 | 连接、新建、打开、保存、重开、分离工程 | 需求+源码 | P0 | project.py / CSTClient；实例选择需审查 | 双实例不误绑；重开状态一致；detach 不误关 |
| CAP-002 | 自然语言输入、补问、解释与同任务修改 | 用户需求 | P0 | Pi/PiDeck 复用点待本地审查 | 同会话建模、两轮修改、当前值追问 |
| CAP-003 | PDF/图片/CAD/CST 文件输入 | 用户需求 | P0分步 | 解析与资产管线待核验 | 标出读到/未读到的内容和文件身份 |
| CAP-004 | 官方帮助、对象查询、示例复用 | 用户需求+源码 | P0 | vba.py 为参考 JSON；schematic 成员枚举 | 文档版本/参数与真实最小例对应 |
| CAP-005 | Python/VBA 托管执行 | 截图+用户需求 | P0 | 原始 VBA 有代码；通用 Python Runner 待设计 | 明确模块与权限；代码留档；执行读回 |
| CAP-006 | 可视化选择、参数依据与报告 | 用户需求 | P0分步 | Host/UI 集成待审 | 选中真实对象；来源和实际值绑定 |
| CAP-007 | 授权、预算、日志、故障恢复 | 设计必要项 | P0 | 现有实现不等于完整后端 | 过期修改/重复请求/断连不重复副作用 |

## 3. 3D Home 工具栏

| ID | 截图可见功能/操作 | 优先级 | 源码线索/待核验 | 最小验收 |
|---|---|---|---|---|
| CAP-101 | Units | P0 | 工程单位接口 | 设置再读回；几何/频率单位不混用 |
| CAP-102 | Simulation Project | P0 | project.py / 工程类型 | 不猜下拉项；逐类检查项目创建和绑定 |
| CAP-103 | Setup Solver / Problem Type | P0/P1 | solvers.py；实际任务/求解器类型 | 配置读回；不支持类型明确阻断 |
| CAP-104 | Start Simulation / Logfile | P0 | simulation.py 与 CSTClient 路径需统一 | 真作业、日志、完成/失败与产物一致 |
| CAP-105 | Optimizer | P2 | optimization.py / parameters.py | 参数范围、目标、次数预算、每次结果可追溯 |
| CAP-106 | Par. Sweep | P2 | parameters.py / 任务扫参 | 每个点的输入/结果身份独立，无陈旧复用 |
| CAP-107 | Mesh View | P0分步 | mesh.py / 导出待核验 | 展示真实求解网格或明确缺失，不冒充渲染面片 |
| CAP-108 | Global Properties | P0/P1 | 待查其当前模式的完整设置项 | 记录具体属性及读写方法，不只核对按钮名 |
| CAP-109 | Edit Properties | P0 | 对象属性入口 | 改目标属性；未指定属性保持不变 |
| CAP-110 | History List | P0 | model3d.add_to_history | 建模步骤/代码可查；不将其等同完整运行历史 |
| CAP-111 | Calculator | P2 | 参数表达式/求值接口待核验 | 表达式、结果、单位与依赖一致 |
| CAP-112 | Parametric Update / Parameters | P0/P2 | parameters.py / 重建路径 | 参数修改实际驱动几何；潜在求解按权限管理 |
| CAP-113 | Information | P0 | 工程信息/诊断 | 版本、对象和求解信息来源明确 |
| CAP-114 | Open Report | P0分步/P2 | 本项目报告与原生报告须分开 | 能辨别报告类型、版本；不隐式再求解 |
| CAP-115 | Python / VBA Macros | P0/P2 | vba.py；Python 入口待设计 | 同 CAP-005；文件宏的权限与来源验证 |
| CAP-116 | Copy / Paste / Delete / Copy View | P2 | 编辑/视图接口待核验 | 区分对象复制删除和图像复制；删除可恢复 |

## 4. 原理图 Home 工具栏

| ID | 截图可见功能/操作 | 优先级 | 源码线索/待核验 | 最小验收 |
|---|---|---|---|---|
| CAP-201 | Units / Simulation Project | P0 | schematic 工程与单位 | 电阻/电容等数值单位读写；不沿用几何单位假设 |
| CAP-202 | Tasks / Update | P0/P1 | SimulationTask 候选对象；本地增强待审 | 任务类型/依赖/结果正确；Update 副作用有授权 |
| CAP-203 | Optimizer / Par. Sweep / Tune | P2 | Optimizer/任务接口候选 | 功能逐项核验，不能以 3D 扫参通过代替 |
| CAP-204 | Filter Design | P2 | 官方接口待查 | 找到实际设计操作与读回，范围未验证 |
| CAP-205 | 3D Component Library | P1/P2 | 库/引用接口待查 | 引用、版本、端口映射和依赖可恢复 |
| CAP-206 | Device Model Library | P2 | 器件模型接口待查 | 模型类型、参数、引脚、依赖对应 |
| CAP-207 | External Port | P0 | schematic_create_external_port | 编号、阻抗、位置与网络读回 |
| CAP-208 | Ground | P0 | 参考节点入口待核验 | 真实参考电气节点正确，非仅画接地符号 |
| CAP-209 | Probe | P0/P1 | 原理图探针方法待查 | 观测量、参考、方向和结果绑定 |
| CAP-210 | Connection Editor | P0/P1 | Net + 网络编辑方法 | 引脚级连通与断开准确，保存重开一致 |
| CAP-211 | Connection Label | P2 | 网络标记方法 | 标签/网络身份不混淆 |
| CAP-212 | Reroute Connectors | P2 | 布局方法待查 | 只改布局不改电气拓扑 |
| CAP-213 | Auto Connection | P2 | 自动连接规则待查 | 生成网络读回；防止近邻错误连接 |
| CAP-214 | Edit Properties | P0 | Block 属性/元件配置 | 值、表达式、单位、引脚与前后差异 |
| CAP-215 | Assembly | P1/P2 | 系统装配接口待查 | 子工程、端口映射、更新与结果对应 |
| CAP-216 | Parametric Update | P1/P2 | 工程参数联动待查 | 更新影响范围可读回；不隐式越权求解 |
| CAP-217 | Project Dependencies | P1/P2 | 子工程依赖待查 | 缺失/版本错误依赖可识别并阻断 |
| CAP-218 | Calculator | P2 | 求值机制待核验 | 与电路参数表达式一致 |
| CAP-219 | Open Report / Python / VBA Macros | P0分步/P2 | 报告/执行入口 | 分别核验原理图上下文，不走错 3D History |
| CAP-220 | Copy / Paste / Cut / Copy View | P2 | 剪贴/布局功能待核验 | 元件/网络复制语义正确；视图副本不是模型 |

## 5. 其他标签及领域功能

用户截图还显示 Modeling、Cables、Simulation、Post-Processing、View 等标签，但未展示其全部内容。下表是根据用户工作流补充的类别，并非从截图读取出的完整按钮清单。

| ID | 能力类别 | 优先级 | 最小验收 |
|---|---|---|---|
| CAP-301 | 3D 几何、布尔、变换、材料 | P0 | 从空工程建立、修改、读回对象与关系 |
| CAP-302 | 端口、激励、边界、监视器 | P0 | API 值、物理方向和几何位置均核验 |
| CAP-303 | CAD/STEP 导入导出 | P1 | 单位、坐标、部件、映射与文件依赖正确 |
| CAP-304 | 原理图元件与网络整体 | P0 | R/L/C/端口/参考节点/网络从零创建并读回 |
| CAP-305 | 线缆截面/导体/路径/终端 | P0本例/P1扩展 | 222所需结构、材料、回流、路径与终端对应 |
| CAP-306 | Cable—电路—3D 联合任务 | P0本例/P1扩展 | 222依赖、端口映射、电阻接地/探针、任务执行与结果链闭合 |
| CAP-307 | S 参数、阻抗与派生曲线 | P0 | 复数、轴、端口、参考阻抗及 run 身份 |
| CAP-308 | 方向图与辐射指标 | P0 | 频率、角度、极化、坐标与指标定义明确 |
| CAP-309 | 线缆电压、电流与串扰 | P0本例/P1扩展 | 当前222及已选官方例的导线/节点/探针/方向与结果定义明确 |
| CAP-310 | 场切片、动画和其他后处理 | P2 | 实际数据、单位、时频坐标；不伪造缺失场 |
| CAP-311 | 隐藏窗口/后台执行 | P0分步 | 特定版本实例真实测试；未知弹窗可检测 |
| CAP-312 | 多项目恢复、依赖与外部修改 | P0基础/P2扩展 | 不覆盖人工修改；重启重新绑定与同步 |
| CAP-313 | 多求解器、周期/其他激励及远期模块 | P2 | 逐模块定义受支持范围，不外推全套能力 |

## 6. 每项能力的后续记录模板

```text
capability_id:
user_operation:
source: screenshot / user_requirement / code / proposed_extension
cst_version_and_build:
project_type_and_solver:
api_doc_ref_and_version:
existing_code_ref: commit + path + symbol
local_delta: absent / present / unknown
read_status:
write_status:
real_automation_status:
pideck_status:
numerical_status:
preconditions_and_units:
allowed_side_effects_and_permission:
readback_postconditions:
example_or_test_id:
evidence_ref:
known_gaps:
next_action:
```

## 7. 计分与维护规则

一次成功脚本仅给相应版本/模块/参数范围增加证据，不自动提升整类功能。原理图 Task 与 3D Solver、仿真网格与显示网格、报告生成与原生报告、原始代码可调用与正常 Agent 可交付都分开记。

报告范围覆盖率时同时报告分母版本和未验证数量。某功能尚未找到 API，应写“未找到/待核验”，只有充分证据才写“不支持”；必要人工介入可保留，但不计全自动通过。

R1已细化P0和直接相关P1，保留全部56项及P2范围。原截图未取得，所以“截图无遗漏”仍unknown；其他标签细项要取得对应界面或官方目录后补齐。本轮只做文档结构与来源核对，L0业务测试、L1服务协议、L2真实接口、L3Agent/桌面、L4数值均未新执行。

## W2优先状态（覆盖旧表当前列，保留CAP编号）

| 范围 | 已完成增量 | 仍未通过 |
|---|---|---|
| 会话工程归属 | 稳定SessionRecord.id绑定、会话文件夹按钮、完整原生副本/哈希与历史索引 | 外部依赖只能按实际证据登记，不能宣称全部任意工程无依赖 |
| 工程修改/保存 | 参数修改前实际读回、原生Save As新版本；L80→82实际点击/保存/读回 | 所有建模工具的细粒度revision语义尚未穷尽 |
| 刷新/结果归属 | reload/view/results与运行分离；工程SHA及结果目录变化检测；manual/agent/import/unknown口径 | 原生外部手改并手动求解的完整交接；模型/旧结果数值对应 |
| 正式工作区 | React中央分栏、当前会话工程选择、3D CAD/线缆中心线、Net/引脚表、参数任务与已有曲线 | 真实网格几何、完整原理图属性/连线编辑、任务编辑与运行面板 |
| 实际Agent | 共享后端HTTP MCP与手动入口复用同一CSTClient/锁 | 三次Pi测试受Provider错误影响，本轮交接未验收 |
| 222 | 裁剪与75/50Ω历史版本、检查副本、原生部分结果及日志完整可定位 | 本轮暂停新求解，未取得新完整V/I |
