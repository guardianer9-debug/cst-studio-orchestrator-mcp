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
