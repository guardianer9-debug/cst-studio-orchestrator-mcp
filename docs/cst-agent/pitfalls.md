# 问题—原因—修复—复测

| 编号/问题 | 原因与证据 | 修复/当前路线 | 复测 | 适用条件 |
|---|---|---|---|---|
| QD-01 工具计数错误 | 继承网格增强后实际 183；测试仍 181 | 严格更新清单，并断言两项网格工具 | OFFLINE-04 pass；后加工具继续更新 | 本地增强整合 |
| QD-02 可能绑定用户第一实例 | 原 connect 自动取首 PID/首工程 | 默认自有新实例；attach 要明确 PID；非自有 detach 不关闭 | Mock pass；自有副本实测 | 全部连接 |
| QD-03 参数“查询”只弹窗 | MsgBox/Debug.Print 不返回真实结构 | 原生参数表达式/求值索引读取 | 222/偶极子实读 | CST 2025.2 |
| QD-04 读回签名不符 | GetGeometryUnit 不存在；GetUnit 不接受 Geometry；GetNextProperty 返回 tuple | Length/Frequency/Time；解包 name/type/value | 偶极子单位/属性通过；222 全字段待复测 | 本机官方 SDK |
| QD-05 自动接受弹窗/跨域重放 | 全局 watcher 可影响其他实例；AttributeError 后可能重复写入 | 禁止自动全局点选；3D 与 schematic 显式路径，报告部分执行风险 | OFFLINE-04 pass | 需业务方显式处理异常 |
| QD-06 关闭等待未返回 | LIVE-REFERENCE-03 自有 CST 进程已消失，Python close 仍阻塞；根因未定 | 保留现场；只终止该探测 Python，不碰用户会话 | 稳定性待复测 | 不能把清理完成推断为 SDK close 成功 |
| QD-07 偶极子旧副本不可求解 | 零实体，无端口；以前只保留宏设置历史 | 从同源官方宏恢复 4 实体和馈电，保留旧失败 | LIVE-DIPOLE-02 真求解 SUCCESS | 标记参考修复，不称完整从零重建 |
| QD-08 结果接口不符 | get_tree_item 不存在，旧代码把数据转字符串 | get_result_item，分 3D/DS，保留复数数组/轴标签 | 本机新 S11 数据读取成功；MCP 回归进行中 | 0D/1D；不能替代完整远场/场量适配 |
| QD-09 PiDeck 锁文件缺项 | upstream v0.7.1 npm ci 缺两项 emnapi 依赖 | 仅独立桌面执行 npm install 生成锁；不升级全局组件 | build:fast pass | 安装差异与日志本机留存 |

新问题追加，不覆盖旧失败。遇到相同症状先检索本表及对应原始日志。未知根因保持未知，不追认当时未记录的信息。

| QD-10 MCP 握手失败 | 原 server 在进入协议前启动 CST，长启动无法及时握手；实际 Pi 首次失败 | 服务先提供元数据；显式创建/打开时才连接 CST | PROTOCOL-01、PI222-02 元数据/状态通过 | 后续真实打开单独记录，不把离线状态当连接成功 |


## D2 新增排查

| 编号 | 问题—原因 | 修复 | 复测与条件 |
|---|---|---|---|
| QD-11 | hide-only 新实例未注册接口，Python环境清理未解决 | 启动时同时quiet，不能等连接后再quiet | STARTUP-QUIET-03及后续多个副本；只确认对本机有效，不推断具体弹窗内容 |
| QD-12 | 离散端口删除提示错误，块删除又依赖隐式选中对象 | 3D使用已实测 Port.Delete(number)；Block.Delete必须显式target_name；查询后不依赖当前选择 | PI222-03B、Mock target/副作用测试 |
| QD-13 | 原端口查询MsgBox阻塞隐藏窗口 | cst_list_ports改为结构化树编号与属性查询，实时VBA禁止MsgBox/InputBox | READ-FIXES-02；未点击其他实例对话框 |
| QD-14 | get_mesh_info/get_mesh_quality调用Mesh.Update，读写混淆 | 纯getter，未取得指标明确列为unavailable，不生成网格 | READ-FIXES-02历史/网格均不变 |
| QD-15 | 直接调用GetXPos对本机探针报坐标系错误 | 读坐标系及GetPosition1/2/3，保留表达式，不擅自转换坐标 | 222三处场探针实际读回成功 |
| QD-16 | 只复制.cst并不保证包含全部旧数值结果 | 默认只把它当建模参考；求解生成新数据，旧外部结果留原处，不用缺失结果伪称新运行 | DIPOLE-VIEW-01为负例，后续完整新运行另记 |
| QD-17 | Farfield Cuts并非CalculatePoint的3D输入 | 选择Farfields根下一层3D结果，配置方向性与线性标度后读取 | FARFIELD-READ-05、PROTOCOL-LIVE-02 |
| QD-18 | 结果库interactive提示污染MCP stdout | 库诊断重定向stderr；显式选择3D/DS结果域，避免MWS不存在的DS模块 | 真实stdio读曲线通过；提示保留stderr |
| QD-19 | 参数修改作为History命令会混入固定赋值 | 原生StoreParameter+RebuildOnParametricChange，再读取表达式和值 | L82/L80几何边界及新求解已实测 |
| QD-20 | Agent上游服务错误打断调用 | 原错误与请求保留，独立短会话重试，不归因CST、不捏造已执行工具 | 实际Pi会话记录；后续终态另记 |

CAD导出与远场绘图配置当前使用本机已探测的私有 model3d._execute_vba_code，仅固定内部配方、不作为任意脚本接口。精确build门控、历史不变和CAD边界核对必须保留；新CST版本需要重新验证。


| QD-21 | 旧结果摘要/导出写入History后，实际远场报No HEX mesh found | 后处理拒绝进入History；使用固定无历史读回/导出，失败工程保留，新副本重跑 | 实际Agent agent-dipole-03工具链与工件核验通过 |
| QD-22 | 单点远场RPC约0.5秒/点，181点及并发调用可能超时 | 官方CalculateList批处理，一次GetList取回；每实例工具串行锁 | 181点约1.70秒，实际Agent两个181点切面成功 |
| QD-23 | DeleteResults返回被后续禁用对话框状态覆盖 | 删除结果独立返回真实成功/异常，不执行对话框动作 | 离线回归及后续实际Agent继续运行 |
| QD-24 | 222实际原条件超过24GiB调试保护值 | 保留已保存工程和部分数值文件，仅停止已核实归属进程；不改物理模型 | 25.4GiB触发memory_limit，无残留目标进程；48GiB/6h待预算答复 |
| QD-25 | 默认MCP脚本编排没有setTimeout | 不把编排报错当CST失败；后续状态查询与最终结果分开记录 | 偶极子求解本身已成功，编排失败保留 |
