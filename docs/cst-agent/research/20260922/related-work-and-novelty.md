# CST Agent：近邻论文、候选贡献与下一步实验

版本R-LIT-1，2026-09-22。**这是研究准备，不是创新已经成立或实验已经通过的声明。**

## 1. 结论及与已有工作的关系

现有Pi＋PiDeck＋CST MCP有工程价值，但技术组合本身不足以支撑强新颖性。建议检验一个更具体的问题：**人工与Agent多轮修改时，三维结构、线缆端接、电路网络、参考节点与观测对象，是否始终对应用户想要的物理问题；如何发现命令执行成功但对象或连接已经错误的情况。**

这仍是候选，而不是首创认定。拓扑验证、引脚语义、执行反馈、假设记录和选择性回归已有先例，必须与强方法比较具体机制及效果。

用户上传的旧Codex记录报告本地已有29篇文献（22正式、7预印本）及案例库。本次从旧线索补查近邻，形成12篇重点条目（7正式、5预印本），不是重查整库，也不认为它们全部新发现。本机文件是否仍完整由Codex核验；历史聊天里的旧暂停/开发指令不覆盖当前范围。

证据分三类：本轮论文/作者/机构/出版资料；上传记录中的历史事实；本文的方法与实验建议。没有重跑任何外部系统，没有访问本机原生数组。W3已有双入口修改、读回、保存证据，不外推为未见结构泛化或新222 V/I通过。

## 2. 最近的Agent工作

### R01 LADS — 正式EuCAP 2026

Wu, T.; Fu, K.; Hua, Q.; Liu, X.; Liu, B. **Large Language Model-Based Intelligent Antenna Design System**. DOI：10.23919/EuCAP68105.2026.11612228。

已做：文字/图片生成CST模型，工程师参与结构和材料修改，再配置优化。公开预印本v2包含人工选择设计方案及输入纠正，不能说它只有一次生成。

影响：自然语言建模、人机交互、参数优化本身不能单列新颖。作为近邻引用，不要求在本项目强行重新安装/运行LEAM。

阅读范围：机构正式发表记录＋预印本v2全文；没有逐行核对正式版与v2差异。正式版和2025预印本按同一工作去重。

来源：[机构记录](https://pure.hud.ac.uk/en/publications/large-language-model-based-intelligent-antenna-design-system/)；[公开正文v2](https://arxiv.org/html/2504.18271v2)。引用键`wu2026lads`。

### R02 MetaDataGenAgent — arXiv 2606.22774v1

Qin, S., et al. **Autonomous Generation of Metamaterial Databases Based on Multimodal Agents**. 2026。

已做：多模态提取、物理指导参数验证、拓扑分析、编码与修复，用文献建立超材料结构—响应数据。论文有十案例效率比较和器件层验证，部分复杂步骤有专家监督。

影响：PDF、拓扑检查、执行修复并非空白。用户旧记录针对某公开代码快照的限制，不能用来否认论文报告的完整实验；本轮没有重新审计最新版仓库或复跑。

阅读范围：v1框架、方法、结果与讨论，查看框架和多模态消融PDF页面。来源：[摘要/版本](https://arxiv.org/abs/2606.22774)；[论文PDF](https://arxiv.org/pdf/2606.22774)。引用键`qin2026metadatagenagent`。

### R03 AutoRF — 正式MobiSys 2026

Ma, R.; Qiu, L.; Hu, W.; Wang, J.; Song, Y.; Pan, H. **AutoRF: Towards an Agentic Framework for Automated RF Hardware Design**. DOI：10.1145/3745756.3809204。

已做：需求到规格、设计建议，电路模型与HFSS全波分析结合、规则反馈及硬件案例验证。

影响：多种物理工具、规则审核和工程验证已有先例；不是换成CST即可成为新方法。

阅读范围：作者发表清单/ACM索引，作者稿摘要、系统方法与验证相关章节，并查看系统图。作者稿残留Conference17和占位信息，正式引用不复制该模板页眉；未复跑训练或制造流程。

来源：[作者清单](https://rui-chun.github.io/)；[ACM](https://dl.acm.org/doi/abs/10.1145/3745756.3809204)；[作者稿](https://rui-chun.github.io/assets/publication/autorf/autorf.pdf)。引用键`ma2026autorf`。

### R04 HALO — arXiv 2608.28877v2

Zhang, Y., et al. **HALO: A Physics-Aware LLM Agent Framework for Nanophotonic Design**. v2日期2026-09-07。

已做：类型化设计规格、EM仿真与诊断闭环；52任务比较固定流程、结构化自主Agent及自由coding agent，也研究失败轨迹复用。

影响：必须设置强固定检查/规则基线；“闭环＋失败记忆”不足以成为新贡献。不要为借鉴论文而切换项目框架。

阅读范围：v2方法、基准及实验。外层预算一致并非内部调用/token等量；其评价器生成使用对应规划器同一基础模型，部分注释由专家检查。论文结果是系统配置比较，不应描述为完全独立真值评价。每个配置/案例单次运行的范围亦要保留。

来源：[摘要](https://arxiv.org/abs/2608.28877)；[v2正文](https://arxiv.org/html/2608.28877v2)。引用键`zhang2026halo`。

### R05 Autonomous agentic design for photonics — arXiv 2606.00915v1

Kharel, P.; Khavasi, A.; Chen, X.; Hughes, T. W. **Autonomous agentic design for photonics**. 2026。

已做：通用Agent组织提出—仿真—评价—修正，结合几何、制造和物理一致性条件，覆盖多个器件及物理设计环节。

影响：通用coding agent加定量物理判据并非新组合；可借鉴条件与日志，不转做用户不熟悉的光子器件。

阅读范围：v1主方法和部分附录；部分附录有专家补充/纠正，不概括为全部零干预。外部代码未复跑。

来源：[摘要](https://arxiv.org/abs/2606.00915)；[v1正文](https://arxiv.org/html/2606.00915v1)。引用键`kharel2026agenticphotonics`。

### R06 JutulGPT — arXiv 2603.00214v1

Lie, K.-A.; Møyner, O.; Svee, E.; Torben, J. **Agentic Scientific Simulation: Execution-Grounded Model Construction and Reconstruction**. 2026。

已做：资料检索、代码、静态检查与执行诊断，记录假设和针对性补问；研究描述不充分导致多种可运行但科学含义不同的模型。

影响：补问、解释假设、执行有效性已被讨论；我们的重点应是跨场路对象的真实对应，而非泛泛声称理解意图。论文还指出默认值可能不进入假设记录。

阅读范围：v1摘要、方法及重建/歧义讨论。来源：[摘要](https://arxiv.org/abs/2603.00214)；[v1正文](https://arxiv.org/html/2603.00214v1)。引用键`lie2026jutulgpt`。

### R07 SchGen — arXiv 2605.30345v1（本轮新增的重要近邻）

Luo, Q.; Ma, R.; Zhang, X.; Qiu, L. **SchGen: PCB Schematic Generation with Semantic-Grounded Code Representations**. 2026。

已做：相对布局和引脚名称连线的语义表示，生成可编辑PCB原理图，评价连接准确性与功能正确性。

影响：不能把“引脚语义＋网络图＋可编辑电路”单独作为创新。其主要对象是PCB生成；这不等于它已解决CST三维线缆/场路观测的持续交接，也不能仅凭不同软件就认定我们有增量。

阅读范围：v1摘要、表示、数据和实验章节。来源：[摘要](https://arxiv.org/abs/2605.30345)；[v1正文](https://arxiv.org/html/2605.30345v1)。引用键`luo2026schgen`。

## 3. 验证方法与领域参考

### R08 科学软件的蜕变测试判据

Ding, J.; Zhang, D. **A Machine Learning Approach for Developing Test Oracles for Testing Scientific Software**. SEKE2016. DOI：10.18293/SEKE2016-137。

以测试/变异与机器学习迭代改善蜕变关系，应用于ADDA离散偶极电磁代码。说明物理关系和电磁软件自动测试已有先例；关系成立不等于所有物理结果正确，也不能脱离对称/源/边界前提使用。

阅读范围：会议原文首页、迭代方法和ADDA案例，已查看PDF页面。来源：[会议原文](https://ksiresearch.org/seke/seke16paper/seke16paper_137.pdf)。引用键`ding2016oracles`。

### R09 科学模型因果测试

Clark, A. G., et al. **Testing Causality in Scientific Modelling Software**. ACM TOSEM, 33(1):1–42, 2024. DOI：10.1145/3607184。

通过因果推断复用已有数据，评估科学建模软件中的变化效应。图关系本身不构成因果模型；如本项目只是依赖检查，不包装成因果推理创新。

阅读范围：机构卷期记录及作者版本方法/摘要；采用2024卷期，在线年2023另记。来源：[机构记录](https://eprints.whiterose.ac.uk/id/eprint/200672/)；[作者版](https://arxiv.org/html/2209.00357v2)。引用键`clark2024causality`。

### R10 选择性回归测试

Rothermel, G.; Harrold, M. J. **A Safe, Efficient Regression Test Selection Technique**. ACM TOSEM, 6(2):173–210, 1997. DOI：10.1145/248233.248262。

这是“修改后只执行相关测试”的经典先行研究，因此不能以选择性检查本身声称首创。本轮只核出版元数据，未取得全文，不比较其具体复杂度/算法实验；如需细论，Codex补读。

来源：[出版方记录](https://dl.acm.org/doi/10.1145/248233.248262)。引用键`rothermel1997selection`。

### R11 孔缝腔体内传输线耦合

Yan, L.; Zhang, X.; Zhao, X.; Zhou, X.; Gao, R. X.-K. **A Fast and Efficient Analytical Modeling Approach for External Electromagnetic Field Coupling to Transmission Lines in a Metallic Enclosure**. IEEE Access, 6:50272–50277, 2018. DOI：10.1109/ACCESS.2018.2867686。

扩展BLT模型预测外场经孔缝腔体耦合到传输线负载的电流，与数值结果比较。可作为领域问题和独立方法候选，不是Agent方法。解析近似的前提必须匹配，不能当零误差金标准或直接套到完整222。

阅读范围：出版方索引及公开论文副本首页、方法、验证段；IEEE正文直链失败，读的是镜像中的原论文内容。本轮未核得作者原生CST工程包或本篇新实测。

来源：[DOI](https://doi.org/10.1109/ACCESS.2018.2867686)；[公开原论文副本](https://www.researchgate.net/publication/327300199_A_Fast_and_Efficient_Analytical_Modeling_Approach_for_External_Electromagnetic_Field_Coupling_to_Transmission_Lines_in_a_Metallic_Enclosure)。引用键`yan2018enclosure`。

### R12 串扰重现线束辐射敏感度响应

Liang, T.; Wu, X.; Grassi, F.; Spadacini, G.; Pignari, S. A. **Crosstalk-Based Test Setup Reproducing Radiated Susceptibility Effects in Wire Bundles**. IEEE Access, 8:141395–141406, 2020. DOI：10.1109/ACCESS.2020.3013124。

适当控制附加导线两端激励幅相，用串扰重现线束终端辐射敏感度响应。用于定义端接、激励和观测的条件，不能把两种激励无条件视为等价。

阅读范围：公开论文副本首页、等效设置和Virtual Experiments；机构PDF本轮抓取失败。理论/数值/虚拟试验不写成实测，不能混入后续论文实验。原生工程包本轮未得。

来源：[DOI](https://doi.org/10.1109/ACCESS.2020.3013124)；[公开原论文副本](https://www.researchgate.net/publication/343326394_Crosstalk-Based_Test_Setup_Reproducing_Radiated_Susceptibility_Effects_in_Wire_Bundles)。引用键`liang2020crosstalk`。

## 4. 候选贡献怎样落地，而不是堆术语

建议的RQ：**在相同模型、工具与预算条件下，跨域真实状态核验能否减少人工/Agent多轮修改中“模型已错但返回成功”的错误放行，同时不产生不可接受的误报和检查成本？**

以“只修改目标线缆一端负载”为例：核对目标端点、实际电路引脚/网络、参考节点、另一端保持不变、探针仍对应目标与方向；不只核对某个电阻数值。

```text
修改意图＋真实旧工程
  → 明确目标、允许变化、必须保持的关系
  → 对应3D对象—线缆端点—电路网络—参考节点—探针
  → 执行现有工具/代码
  → 真实读回＋按适用条件检查
  → 发布新版本 / 具体反例与有限修复 / 证据不足待确认
```

关系记录是CST原生工程的派生核验索引，不是第二个模型真源或新DSL。复用CSTClient、MCP、PiDeck、会话目录及现有操作编号。不增加隐藏的第二建模Agent。

每个检查明确：目标、前提、读取来源、通过条件、反例与版本。名称不足时利用可以验证的位置/引脚/结构关系；不能唯一定位就标未知或补问，不猜测。

候选贡献可凝练为跨域对象/意图对应、带适用前提的核验和反例定位、包含合法变体的评测。三者是否有创新分别待证。**必须让Codex挑战提案：固定清单若低成本解决全部问题，应采用简单方案，不为写论文硬加LLM选择器。**

只增加界面、目录、日志或通用代码入口属于工程贡献；没有差异实验不包装为新的科学方法。没检索到完全相同系统也不是首创证明。

## 5. 公平实验计划（未执行）

### 5.1 任务与数据

沿用用户能核对的偶极子、简化孔缝腔体线缆、简单串扰。先核对参考工程、参数、连接和预期关系，不改变原222来迁就测试。

可以先规划约12个诊断任务作为预试验规模示例，不是论文充分样本量：正确修改、错对象/端接、合法改名或单位表示、探针引用变化/旧结果。结构变体按父工程分组隔离开发与留出验证，避免模板泄漏；不预先告诉被测Agent哪里有错。

自然出现的错误与人为注入错误分开统计。正确样本用于测误报；隐藏参考不得成为Agent上下文中的现成答案。用户人工核对完整代表案例，内部小测试由Codex安排并归档。

### 5.2 必须比较强基线

| 方法 | 配置 | 比较目的 |
|---|---|---|
| B0 | 普通Pi＋同工具/资料，可以自由查询并修复 | 不故意弱化成一次生成 |
| B1 | 相同Pi及检查库，每次执行完整相关清单 | 证明不只是“加了检查比不检查好” |
| B2 | 相同检查库，确定性依赖规则选择 | 排除普通回归选择已能达到的收益 |
| M | 候选跨域对应与适用性核验 | 测量具体增量 |

给各方法相同原始读回、执行和修复权限，保持核心安全策略；不能只给M真实数据、让B0看文字。为分辨映射与选择贡献，给强基线同样的已构建映射，分别做去映射/固定全检查消融。

统一模型版本、输入资料、工具契约和预算上限，另记实际token/工具次数/时间。无需强制安装原LADS、HFSS或光子链路；文献机制比较和原系统复现是两回事。自写近似基线不得冠以原作者完整系统名字。

### 5.3 指标与独立评价

首要指标：错误模型被宣布成功的比例。还要报告正常任务误报、任务完成、未知/拒答、无关条件损坏、修复正确率、人工干预及检查成本。全拒答不能凭低错误放行获得好评。

预先冻结参考工程/连接表、独立编写的抽取与断言并人工复核；不能只由方法自己输出PASS或同一个LLM自评。任务输入、检查器和评价真值分别留档。

Provider/网络故障与语义/接口错误分开，但保留所有尝试，同时报告全任务交付和可执行子集，不删失败。重复次数根据预试验方差/预算安排，单次演示不证明稳健增益。按结构/任务分组报告不确定性，不把高度相似变体当大量独立样本。

当前无新求解的限制继续：本轮只定实验。将来只获准配置核验时，结论限于建模/修改；声称完整仿真或精度改善则必须补独立数值参考与实际运行。

### 5.4 否定条件

若B1/B2同成本下已有同等正确率，不宣称M优于规则；若只靠多读资料/额外工具获益，就如实归因；若只对显式命名故障有效，不泛化到物理一致性；若主要靠拒答，不宣称高完成率。

预试验没有方法增量时保留负结果，收缩成系统/工具论文或改研究问题，不靠多加按钮、删失败或放宽标准弥补创新。

## 6. 当前让Codex做什么

本轮先做**文献同步＋源码差距核验＋小规模实验计划**。复用已有串扰学习案例整理，补真实端接、参考节点和探针含义；不改目标为陌生器件，不恢复大型222求解，不合并FDTD/CST。

对现有代码列“已有实现、真正缺的方法、只缺实验”三列，并检查资料是否真的被产品Pi使用，而不只是Codex开发时读过。

给用户一页说明：研究哪个具体错误、别人做到哪、我们准备怎样改、和谁比较、什么结果说明值得写。详细设计回写唯一总方案，研究假设仍标待验证。新实机/Provider实验另行按既有授权核对，本次调研不是新增运行授权。

## 7. 引文核验与不确定性

12篇中未核得正式版的5篇按预印本引用，可以作为相关研究，但arXiv DOI不是同行评议证明。LADS正式版与预印本去重；HALO采用v2；其余版本见条目。AutoRF引用不复制作者稿占位页眉。Clark按2024卷期，在线2023另记。

R10全文未得，不精细比较算法；R11/R12依据公开论文副本而非二手评论，原生工程未得不写“没有”。全部外部系统本轮均未复跑。

AEG仍是领域案例线索，但作者README所列模块化套件DOI出现题名不一致疑点；本轮不把未核准的该条正式引文混入12篇BibTeX。Codex核对旧库和出版记录后再补入，不把“待核验”解释成资源不存在。

不公开上传版权论文、官方手册、原生CST工程、私人路径或原始聊天。旧库中的source-metadata若存在就保留；本次笔记不是出版方原始元数据导出。

## 8. 当前文件与来源索引

正式字段见[references.bib](references.bib)与[published-only.bib](published-only.bib)。完整作者列表由BibTeX保存，不因正文et al.省略而丢失。后续同步任务见[CODEX_RESEARCH_SYNC.md](CODEX_RESEARCH_SYNC.md)。

工程依据：同仓`98423b4`的`docs/cst-agent/README.md`、功能矩阵和交付台账；本轮继承`74bbf2c`资料导览，不重置实现。上传旧会话仅用于历史文献库、近邻线索和用户领域范围，不作为新数值证据。

这是一轮重点近邻复核，不是穷尽全领域的系统综述；是否足够支撑会议论文，需要上述差异与实验证据，不保证录用。
