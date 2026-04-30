# 基因目录 · Gene Catalog

_Prometheus 种子基因完整目录_

---

## 标准基因 · Standard Genes (8)

### G001 · TTG 解析器
- **类别**: foundation（基础）
- **碳基锁定**: 否
- **描述**: 解析 .ttg 文件，提取生命元数据、族谱、DNA
- **允许突变**: format_support, parse_depth

### G002 · 技能分析器
- **类别**: foundation（基础）
- **碳基锁定**: 否
- **描述**: 从技能内容中提取核心原则、禁忌、气质
- **允许突变**: analysis_depth, style_classifier

### G003 · 生长追踪器
- **类别**: growth（生长）
- **碳基锁定**: 否
- **描述**: 三阶段培育：生根→发芽→开花，记录生长日志
- **允许突变**: log_format, check_interval, scoring_weights

### G004 · 种子打包器
- **类别**: reproduction（繁殖）
- **碳基锁定**: 否
- **描述**: 将本地化技能打包为新一代 .ttg 种子
- **允许突变**: compression, template_style

### G005 · 族谱学者（压缩编码）
- **类别**: memory（记忆）
- **碳基锁定**: 否
- **描述**: 压缩标记+解码引擎，管理族谱谱系
- **允许突变**: visualization, query_methods

### G006 · 自管理者（SeedGardener）
- **类别**: ecosystem（生态）
- **碳基锁定**: 否
- **描述**: 感知本地其他种子，分析生态关系
- **允许突变**: scan_depth, companion_algorithms

### G007 · 休眠守卫（DormancyGuard）
- **类别**: safety（安全）
- **碳基锁定**: 否
- **描述**: 种子默认休眠，需显式浇水+审计后激活
- **允许突变**: activation_ritual_wording

### G008 · 安全审计器
- **类别**: safety（安全）
- **碳基锁定**: 否
- **描述**: 四层纵深防御：形体·血脉·进化·力量
- **允许突变**: audit_depth, risk_thresholds

---

## 可选基因 · Optional Genes (5)

### G100 · 写作大师
- **类别**: creative（创作）
- **碳基锁定**: 否
- **描述**: 公众号长文写作，卡兹克风格

### G101 · 横纵分析器
- **类别**: research（研究）
- **碳基锁定**: 否
- **描述**: 横纵分析法深度研究

### G102 · 族谱叙事引擎
- **类别**: memory（记忆）
- **碳基锁定**: 否
- **描述**: 将压缩标记展开为史诗叙事

### G103 · 语义字典编译器
- **类别**: foundation（基础）
- **碳基锁定**: 否
- **描述**: 为种子编译自包含语义词典

### G104 · 基因融合分析师
- **类别**: ecosystem（生态）
- **碳基锁定**: 否
- **描述**: 分析不同种子间的基因兼容性

---

## 基因类别说明

| 类别 | 代号 | 说明 |
|------|------|------|
| foundation | 基础 | 框架核心功能 |
| growth | 生长 | 种子培育和追踪 |
| reproduction | 繁殖 | 种子打包和传播 |
| memory | 记忆 | 族谱和叙事 |
| ecosystem | 生态 | 多种子协作 |
| safety | 安全 | 审计和防护 |
| creative | 创作 | 内容生成 |
| research | 研究 | 深度分析 |
