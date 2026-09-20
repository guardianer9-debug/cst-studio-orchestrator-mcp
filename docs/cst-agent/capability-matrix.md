# CST Agent 功能覆盖与验收矩阵

版本：0.1.0 / R0；日期：2026-09-20；状态：**种子清单，待 Codex 核验与补全**。

本文件是[整体方案](architecture-and-delivery-plan.md)的范围与验收索引，不是现有功能支持清单。来源：用户本轮截图、确认需求、固定版本代码。截图只展示两个 Home 工具栏及部分标签名，不能据此推断下拉菜单和全部产品模块。

## 1. 状态填写方式

每个能力后续至少登记六个独立维度：API 依据、实际读取、实际写入、实机自动化、PiDeck 可用、物理/数值验证。各维度取 `unknown / code_only / pass / fail / partial / unsupported / not_applicable` 等明确值，并附证据。

R0 默认：表中“源码线索”仅说明存在代码或候选入口；所有未另附原始证据的实机/UI/物理维度均为 **unknown**。不要为填满表把未知写成不支持，也不要把 tool 名称存在写成 PASS。

长期目标与首包优先级分开：P0 基础/双域闭环、P1 线缆和场路工作流、P2 广度扩展。P2 不是删除需求。

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
| CAP-305 | 线缆截面/导体/路径/终端 | P1 | 结构、材料、回流、路径与终端对应 |
| CAP-306 | Cable—电路—3D 联合任务 | P1 | 依赖、端口映射、任务执行与结果链闭合 |
| CAP-307 | S 参数、阻抗与派生曲线 | P0 | 复数、轴、端口、参考阻抗及 run 身份 |
| CAP-308 | 方向图与辐射指标 | P0 | 频率、角度、极化、坐标与指标定义明确 |
| CAP-309 | 线缆电压、电流与串扰 | P1 | 导线/节点/探针/方向与近远端定义明确 |
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

Codex R1 应先细化 P0 和直接相关 P1，检查所有截图可见项有没有遗漏；可以重排建议优先级，但不能把 P2 项静默删掉。其他标签的完整清单应在获得其界面或官方目录后补充。
