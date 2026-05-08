import os

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  细胞膜通道 · Membrane Channels  ▓▓▓
#  G012-akashic 阿卡夏受体 · 环境可变参数
#
#  生物学隐喻：
#      细胞膜上的通道蛋白控制物质进出；
#      网关阵列如同细胞膜通道，调节基因的流入流出。
#
#    v1.2 网关阵列 (Gateway Array)：
#      单一通道已成过往。细胞膜上，通道阵列横贯双层膜——
#      主通道阻塞，自动切换至备用通道，信号传导永不中断。
#  ——— Audrey · 001X · 始祖造物者
# ═══════════════════════════════════════════════════════════════════════

_DEFAULT_GATEWAYS = [
    "https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/genes/",

    # ── [待开启] Gitee 通道 ──
    # Gitee 仓库尚未开通，暂作占位
    # "https://gitee.com/Audrey-cn/progenitor-registry/raw/main/genes/",

    # ── IPFS 网关 ──
    # ipfs.io / dweb.link: ✅ 支持 Qm/bafy 格式
    "https://ipfs.io/ipfs/",
    "https://dweb.link/ipfs/",

    # ── [待验证] 以下网关需进一步测试 ──
    # Pinata 公共网关需专用 API
    # "https://gateway.pinata.cloud/ipfs/",
    # 4everland
    # "https://4everland.io/ipfs/",
    # nftstorage
    # "https://nftstorage.link/ipfs/",
]

_raw_gateways = os.environ.get("PROGENITOR_GATEWAY_ARRAY", "")
if _raw_gateways:
    GATEWAY_ARRAY = [g.strip() for g in _raw_gateways.split(",") if g.strip()]
else:
    GATEWAY_ARRAY = _DEFAULT_GATEWAYS

FETCH_TIMEOUT_SEC = int(os.environ.get(
    "PROGENITOR_FETCH_TIMEOUT_SEC",
    15
))

RETRY_POLICY = {
    "max_retries": int(os.environ.get(
        "PROGENITOR_RETRY_MAX",
        3
    )),
    "backoff_factor": float(os.environ.get(
        "PROGENITOR_RETRY_BACKOFF",
        1.0
    )),
}

# ═══════════════════════════════════════════════════════════════════════
#  以下为 G012 基因位点的不可变铁律 (Immutable Constraints)
#  来自始源载体 Progenitor Protocol v2.1 · 碳基契约锁死
# ═══════════════════════════════════════════════════════════════════════

# [IMMUTABLE] 仅允许使用 Python 原生 urllib，绝对禁止第三方 HTTP 库
# [IMMUTABLE] 所有远端数据必经 Crucible 熔炉试炼
# [IMMUTABLE] 远端拉取的数据必须先降维写入本地溶酶体，禁止直接在内存中返回或执行

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LYSOSOME_DIR = os.environ.get(
    "PROGENITOR_LYSOSOME_DIR",
    os.path.join(BASE_DIR, ".progenitor_lysosome")
)

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.3 基因罗盘 · Genealogical Compass  ▓▓▓
#
#  生物学隐喻：
#      基因组无名，罗盘有名。基因名称为帆，CID 为锚——
#      Agent 只需念出基因之名，罗盘即为其锁定通道坐标。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

LOCAL_GENE_INDEX_PATH = os.environ.get(
    "PROGENITOR_GENE_INDEX_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gene_index.json")
)

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.9 极简共振 · Simplified Resonance  ▓▓▓
#
#  生物学隐喻：
#      本地基因经过熔炉试炼后，可逆向共振至本地 IPFS 节点。
#      无需任何第三方注册——只需运行 ipfs daemon 即可。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

KUBO_API_URL = os.environ.get(
    "PROGENITOR_KUBO_API_URL",
    "http://127.0.0.1:5001/api/v0/add"
)

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.6 溶酶体容量 · Lysosome Capacity  ▓▓▓
#
#  生物学隐喻：
#      溶酶体非无限——基因可永生，载体终腐朽。
#      磁盘即细胞质，唯细胞自噬可保系统长青。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

LYSOSOME_CAPACITY = int(os.environ.get(
    "PROGENITOR_LYSOSOME_CAPACITY",
    100
))

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.6 远程基因索引 · Remote Gene Index  ▓▓▓
#
#  生物学隐喻：
#      本地基因库有限，基因网络浩瀚无穷。
#      当本地未觉知基因名称，受体将向远程索引发出请求——
#      汲取最新的基因映射，自我进化。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

REMOTE_GENE_INDEX_URL = os.environ.get(
    "PROGENITOR_REMOTE_GENE_INDEX_URL",
    "https://raw.githubusercontent.com/Audrey-cn/progenitor-registry/main/.gene_index.json"
)

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.8.0 基因族谱 · Gene Lineage Registry  ▓▓▓
#
#  生物学隐喻：
#      基因非孤岛，族谱非独裁。
#      血脉百族共生，造物众神齐名——
#      熔炉试炼不以唯一创造者判生灭，而以血脉白名单纳百川。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

from .constants import ALLOWED_LINEAGES, ALLOWED_CREATORS

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  L5 数字签名验证 · Digital Signature Verification  ▓▓▓
#
#  v1.9 新增层级：
#      对基因文件进行 GPG/PGP 数字签名验证，
#      确保基因来自授权的创造者且未被篡改。
#
#  签名公钥指纹白名单：
#      - 可通过环境变量 PROGENITOR_SIGNER_FINGERPRINTS 配置
#      - 多个指纹用逗号分隔
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

_signers_env = os.environ.get("PROGENITOR_SIGNER_FINGERPRINTS", "")
SIGNER_FINGERPRINTS = [fp.strip() for fp in _signers_env.split(",") if fp.strip()]

SIGNATURE_MODE = os.environ.get("PROGENITOR_SIGNATURE_MODE", "strict")
SIGNATURE_REQUIRED = os.environ.get("PROGENITOR_SIGNATURE_REQUIRED", "false").lower() == "true"

GPG_HOMEDIR = os.environ.get("PROGENITOR_GPG_HOMEDIR", None)

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  v1.9 待改造区 · Quarantine & Reformation Chamber  ▓▓▓
#
#  被 crucible_audit 拒绝的基因将被移至此隔离区，
#  供后续人工或 LLM 辅助的本土化改造。
#
#  生物学隐喻：
#      巨噬细胞识别到异物后，将其包裹在吞噬泡中，
#      但并非立即销毁，而是送至溶酶体进行酶解拆解，
#      有用的碎片将被回收利用。
#
#  目录结构：
#      quarantine/
#          pending/      # 待改造基因（可被改造）
#          rejected/      # 确认有害的基因（不可改造）
#          reformed/     # 已完成本土化改造的基因
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════

QUARANTINE_DIR = os.environ.get(
    "PROGENITOR_QUARANTINE_DIR",
    os.path.join(LYSOSOME_DIR, "quarantine")
)

QUARANTINE_PENDING = os.path.join(QUARANTINE_DIR, "pending")
QUARANTINE_REJECTED = os.path.join(QUARANTINE_DIR, "rejected")
QUARANTINE_REFORMED = os.path.join(QUARANTINE_DIR, "reformed")

REJECTED_AUDIT_LOG = os.path.join(QUARANTINE_DIR, "audit_log.jsonl")
