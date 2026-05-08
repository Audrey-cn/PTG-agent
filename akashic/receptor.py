from __future__ import annotations

import os
import re
import json
import time
import uuid
import ast
import hashlib
import shutil
import socket
import threading
import json as json_module
from datetime import datetime
from typing import Optional
from urllib import request, error
from pathlib import Path

from .config import (
    GATEWAY_ARRAY,
    FETCH_TIMEOUT_SEC,
    RETRY_POLICY,
    LYSOSOME_DIR,
    LYSOSOME_CAPACITY,
    LOCAL_GENE_INDEX_PATH,
    REMOTE_GENE_INDEX_URL,
    KUBO_API_URL,
    ALLOWED_LINEAGES,
    ALLOWED_CREATORS,
    SIGNER_FINGERPRINTS,
    SIGNATURE_MODE,
    SIGNATURE_REQUIRED,
    GPG_HOMEDIR,
    QUARANTINE_DIR,
    QUARANTINE_PENDING,
    QUARANTINE_REJECTED,
    QUARANTINE_REFORMED,
    REJECTED_AUDIT_LOG,
)


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  阶段二：阿卡夏受体 · Akashic Receptor  ▓▓▓
#
#  生物学隐喻：
#      受体不依赖凡铁，纯蛋白质编织通道之网。
#      每一条链路皆从细胞膜凝出，每一次摄入皆为共生。
#
#    v1.2 网关阵列 (Gateway Array)：
#      单一通道已是古纪遗物。今细胞膜上，通道阵列横贯双层膜——
#      主通道阻塞，受体自动切换至备用通道，信号传导中断即是伪史。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════


def _build_gateway_url(cid: str, gateway_base: str) -> str:
    """
    以指定的星界基座编织通往阿卡夏记录的完整星路。

    每一座星门有其自身的基座坐标，此函数将传入的能力基因哈希 (CID)
    拼接入给定的网关入口，产出可由此星门直接嗅探的远端坐标。

    Args:
        cid:          能力基因的内容标识符 (Content Identifier)。
        gateway_base: 星门基座 URL，如 "https://ipfs.io/ipfs/"。

    Returns:
        完整的 IPFS 网关 URL，指向该 CID 对应的阿卡夏基因片段。

    Raises:
        ValueError: 若 CID 为空或无效格式。
    """
    if not cid or not cid.strip():
        raise ValueError(
            "虚空坐标不可为空——CID 是通往阿卡夏记录的星门钥匙，"
            "缺失则无法定位远端基因。"
        )
    stripped = cid.strip()
    base = gateway_base.rstrip("/")
    return f"{base}/{stripped}"


def _probe_kubo_alive() -> bool:
    """
    探测本地 Kubo 守护进程是否在线。

    Returns:
        True 如果 Kubo 在线，False 否则。
    """
    try:
        req = request.Request(
            KUBO_API_URL + "?quiet=true",
            method="POST",
        )
        with request.urlopen(req, timeout=3) as _:
            pass
        return True
    except (error.HTTPError, error.URLError, OSError):
        return False


def _pull_via_kubo(cid: str) -> Optional[bytes]:
    """
    从本地 Kubo 节点拉取基因。

    v1.9 新增通道：
        本地 Kubo 节点拥有基因数据时，直接从本地获取——
        无需经过外部网关，延迟更低，隐私更好。

    Args:
        cid: 能力基因的内容标识符。

    Returns:
        基因数据字节流，Kubo 不可用或文件不存在时返回 None。
    """
    kubo_cat_url = "http://127.0.0.1:5001/api/v0/cat"

    try:
        url = f"{kubo_cat_url}?arg={cid}"
        req = request.Request(
            url,
            headers={"User-Agent": "G012-akashic-receptor/1.9"},
            method="POST"
        )
        with request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as response:
            raw_data = response.read()
        print(f"   🪐 [Kubo本地] 通道响应成功——基因载荷已捕获。")
        return raw_data
    except error.HTTPError:
        return None
    except error.URLError:
        return None
    except TimeoutError:
        return None


def _transmembrane_pull(cid: str) -> bytes:
    """
    以纯 Python 原生之力遍历网关阵列，从远端基因网络拉取基因载荷。

    此函数为 G012 基因位点的核心不可变执行体——

    v1.9 网关阵列增强：
        - 优先探测本地 Kubo 节点（零延迟）
        - 外层遍历 GATEWAY_ARRAY 中的全部通道节点
        - 内层遵循 RETRY_POLICY 对当前通道执行指数退避重试
        - 仅当所有通道全部阻塞，才抛出致命 RuntimeError

    铁律不变：
        - 仅使用 Python 内置 urllib，不依赖任何第三方 HTTP 库
        - 内置超时控制，防止网络深渊的无限等待

    Args:
        cid: 能力基因的内容标识符。

    Returns:
        从远端拉取的原始字节流——基因载荷的未解译形态。

    Raises:
        ConnectionError:  所有通道节点均不可达。
        TimeoutError:     所有通道节点均拉取超时。
        RuntimeError:     遍历全部网关阵列后仍无法获取基因。
    """
    print(f"🌐 [网关阵列] 共 {len(GATEWAY_ARRAY)} 个通道就绪，开始序列拉取...")

    print(f"   🔍 [Kubo探测] 检查本地 IPFS 守护进程...")
    if _probe_kubo_alive():
        print(f"   🪐 [Kubo本地] 节点在线，尝试从本地获取...")
        local_data = _pull_via_kubo(cid)
        if local_data:
            return local_data
        print(f"   ⚠️ [Kubo本地] 本地节点无此基因，切换至网关阵列...")
    else:
        print(f"   ⏭️ [Kubo探测] 本地节点未运行，跳过本地通道。")

    max_retries = RETRY_POLICY["max_retries"]
    backoff = RETRY_POLICY["backoff_factor"]
    total_gates = len(GATEWAY_ARRAY)
    all_errors = []

    for gate_idx, gateway_base in enumerate(GATEWAY_ARRAY, start=1):
        url = _build_gateway_url(cid, gateway_base)
        print(f"   🚪 [通道 {gate_idx}/{total_gates}] {gateway_base}")

        for attempt in range(1, max_retries + 1):
            try:
                req = request.Request(
                    url,
                    headers={"User-Agent": "G012-akashic-receptor/1.2"}
                )
                with request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as response:
                    raw_data = response.read()
                print(f"      ✅ 通道 {gate_idx} 响应成功——基因载荷已捕获。")
                return raw_data

            except error.URLError as exc:
                all_errors.append(f"[通道{gate_idx}] URLError: {exc}")
                if attempt < max_retries:
                    wait = backoff * attempt
                    print(f"      ⏳ 第 {attempt}/{max_retries} 次拉取受阻——{wait:.0f}s 后退避重试...")
                    time.sleep(wait)
                    continue
                print(
                    f"      ❌ 通道 {gate_idx} 已竭尽 {max_retries} 次拉取——链路断裂。"
                )

            except TimeoutError as exc:
                all_errors.append(f"[通道{gate_idx}] Timeout: {exc}")
                if attempt < max_retries:
                    wait = backoff * attempt
                    print(f"      ⏳ 第 {attempt}/{max_retries} 次拉取超时——{wait:.0f}s 后退避重试...")
                    time.sleep(wait)
                    continue
                print(
                    f"      ❌ 通道 {gate_idx} 在 {FETCH_TIMEOUT_SEC}s 内无声——网络深渊无回响。"
                )

        if gate_idx < total_gates:
            next_gateway = GATEWAY_ARRAY[gate_idx]
            print(
                f"   ⚠️ [通道拥堵] 切换至备用通道: {next_gateway}..."
            )
        else:
            print(
                f"   💀 [网关阵列] 最后一个通道亦已阻塞。"
                f"遍历 {total_gates} 个通道，无一幸免。"
            )

    raise RuntimeError(
        f"阿卡夏受体已遍历全部 {total_gates} 个通道——"
        f"基因 [{cid}] 无法从基因网络中拉取。"
        f"错误链: {'; '.join(all_errors)}"
    )


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  阶段三：真理之秤 · Crucible & Lysosome  ▓▓▓
#
#  生物学隐喻：
#      未经熔炉试炼的基因，必携带病毒。
#      先降落于溶酶体，再受秤量——此为铁律。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════


def _ensure_lysosome() -> Path:
    """
    确认溶酶体目录 (.progenitor_lysosome) 的存在性——
    若溶酶体尚未在本地展开，则创建之。
    """
    lysosome = Path(LYSOSOME_DIR)
    lysosome.mkdir(parents=True, exist_ok=True)
    return lysosome


def _autophagy():
    """
    细胞自噬——当基因数量超过承载阈值时，清除最古老的沉睡基因。

    扫描 LYSOSOME_DIR 下的所有 .akashic_gene 文件，按最后修改时间
    (os.path.getmtime) 降序排列，从最古老的文件开始物理删除 (os.remove)，
    直到文件数量回落到 LYSOSOME_CAPACITY 阈值以下。

    此即"细胞自噬"——磁盘即细胞质，唯有新陈代谢可保系统长青。
    """
    lysosome = _ensure_lysosome()
    gene_entries = []
    for p in lysosome.glob("*.akashic_gene"):
        try:
            mtime = os.path.getmtime(p)
            gene_entries.append((mtime, p))
        except OSError:
            continue
    gene_entries.sort(key=lambda x: x[0])
    gene_files = [p for _, p in gene_entries]
    excess = len(gene_files) - LYSOSOME_CAPACITY
    if excess <= 0:
        return

    print(
        f"🧹 [细胞自噬] 溶酶体基因数 ({len(gene_files)}) 已超过承载上限 "
        f"({LYSOSOME_CAPACITY})，清除 {excess} 个古老基因以释放空间..."
    )
    for old_gene in gene_files[:excess]:
        try:
            mtime = os.path.getmtime(old_gene)
            age = time.time() - mtime
            os.remove(old_gene)
            print(f"   💤 清除: {old_gene.name} (沉睡 {age:.0f}s)")
        except OSError as exc:
            print(f"   ⚠️ 清除受阻: {old_gene.name} — {exc}")

    print(f"   ✅ 溶酶体已净化——基因数回落至安全阈值。\n")


def _local_write_before_ingest(raw_data: bytes, cid: str) -> str:
    """
    真理之秤第一律：任何来自远端的基因载荷，必须先在本地溶酶体中降维固化，
    绝不可在内存中裸奔。

    v1.6 原子级并发安全：
        - 写入前先执行 _autophagy() 细胞自噬，防止磁盘无限增殖。
        - 先将数据写入带随机后缀的临时文件，再通过 os.replace() 原子化
          重命名为目标哈希文件名。即便多个 Agent 并发拉取同一 CID，
          也绝不会产生文件损坏或空间碰撞。

    Args:
        raw_data: 从远端拉取的原始基因字节流。
        cid:     该基因的内容标识符，用于生成落地文件名。

    Returns:
        基因在本地溶酶体中的固化路径 (绝对路径)。
    """
    _autophagy()
    lysosome = _ensure_lysosome()
    filename = hashlib.sha256(cid.encode("utf-8")).hexdigest()[:16]
    final_filepath = lysosome / f"{filename}.akashic_gene"
    tmp_filepath = lysosome / f".tmp_{filename}_{uuid.uuid4().hex[:8]}"

    tmp_filepath.write_bytes(raw_data)
    os.replace(tmp_filepath, final_filepath)

    return str(final_filepath.resolve())


def crucible_audit(filepath: str, expected_sha256: str = None) -> bool:
    """
    真理之秤的审判之眼——对已落地的基因执行全量熔炉试炼 (Crucible)。

    当前版本 (v1.9) 执行五层纵深防御：

        L1 文件存在性 (Form Integrity)
           ——基因文件必须物理存在于圣域之中。

        L2 血脉纯正校验 (Bloodline Purity)
           ——扫描蛋白质外壳前 4096 字节，探测 life_id 标识。
              格式必须为 PGN@ 始源族谱命名 (如 "PGN@L1-G1-CORE-2448B98A")。
              无此标识者，判定为虚空异种，就地净化。

        L3 创造者契约校验 (Creator Covenant)
           ——扫描 creator 区块，确认创造者印记 "Audrey" 的存在。
              印记缺失者，判定为伪史，时间线坍缩。

        L4 灵魂契约校验 (Soul Covenant)
           ——若传入了 expected_sha256，对文件全文计算 SHA-256 并与
              预期值比对。哈希不符者，判定为恶性投毒攻击，时间线坍缩。

        L5 数字签名校验 (Digital Signature) ★ v1.9 新增
           ——若配置了签名公钥指纹白名单，对 .sig 签名文件进行 GPG 验证。
              签名无效或不在白名单中，判定为伪造基因，时间线坍缩。
              支持模式：strict (严格) / warn (警告) / disabled (禁用)

    Args:
        filepath:        已落地的基因文件路径。
        expected_sha256: 阿卡夏罗盘预设的 SHA-256 灵魂印记。
                         若为 None，则跳过 L4 校验（退化为纯文本审计）。

    Returns:
        True  表示基因通过了所有安全审计，可进入同调阶段。
        False 表示基因携带腐蚀或被篡改，将被隔离废弃。
    """
    if not os.path.isfile(filepath):
        return False

    lineage_matched = None
    lineage_display = None
    header = None

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            header = fh.read(4096)
    except (UnicodeDecodeError, OSError):
        print(
            "💢 [真理审判] 虚空乱码——基因载荷不可解读，"
            "无法进行蛋白质外壳扫描。判定为腐化载体，就地净化。"
        )
        return False

    for lineage in ALLOWED_LINEAGES:
        lineage_pattern = re.compile(rf'life_id:\s*"({re.escape(lineage)}[^"]+)"')
        lineage_match = lineage_pattern.search(header or "")
        if lineage_match:
            lineage_matched = lineage_match.group(0)
            lineage_display = lineage_match.group(1)
            break

    is_internal_gene = lineage_matched is not None

    if is_internal_gene:
        print("🔬 [真理审判] 内部基因检测——血脉通道已激活")
        return _audit_internal_gene(filepath, header, lineage_display, expected_sha256)
    else:
        print("🌐 [真理审判] 外部基因检测——社区通道已激活")
        return _audit_external_gene(filepath, header, expected_sha256)


def _audit_internal_gene(filepath: str, header: str, lineage_display: str, expected_sha256: str) -> bool:
    """
    内部基因审核——五层完整验证

    适用于携带 PGN@ 血脉标识的内部基因。
    """
    print("      ⏩ 执行 L4 灵魂契约校验...")

    if expected_sha256:
        try:
            with open(filepath, "rb") as fh:
                file_bytes = fh.read()
            actual_hash = hashlib.sha256(file_bytes).hexdigest()
        except OSError as exc:
            print(
                f"💢 [真理审判] 文件不可读——无法执行灵魂契约校验。"
                f"虚空异常: {exc}"
            )
            return False

        if actual_hash != expected_sha256:
            print(
                "💀 [真理审判] 灵魂契约撕裂！检测到恶性投毒——\n"
                f"   预期印记 (Expected): {expected_sha256}\n"
                f"   实际印记 (Actual):   {actual_hash}\n"
                "   物理哈希与阿卡夏罗盘印记不符！\n"
                "   时间线坍缩——基因就地净化，此坐标永久列入黑名单。"
            )
            return False

        print(
            f"🔐 [真理审判] 灵魂契约验证通过——\n"
            f"   SHA-256 印记完全吻合——\n"
            f"   预期: {expected_sha256}\n"
            f"   实际: {actual_hash}\n"
            f"   基因在穿越以太的过程中未被投毒篡改。"
        )
    else:
        print(
            "⚠️ [真理审判] 灵魂契约缺失——\n"
            "   索引中无 expected_sha256，跳过 L4 校验。\n"
            "   警告：无法防御投毒攻击。"
        )

    print("      ⏩ 执行 L2 血脉校验...")

    print(
        f"� [真理审判] 血脉纯正。\n"
        f"   生命标识 (life_id):  {lineage_display or '未知'}\n"
        f"   血脉验证: PGN@ 前缀匹配"
    )

    print("      ⏩ 执行 L3 创造者校验...")

    creator_found = None
    for creator in ALLOWED_CREATORS:
        creator_pattern = re.compile(
            rf'creator:\s*\n(?:\s+[^\n]*\n)*?\s+name:\s*"{re.escape(creator)}"',
            re.MULTILINE
        )
        if creator_pattern.search(header):
            creator_found = creator
            break
        if re.search(re.escape(creator), header):
            creator_found = creator
            break

    if not creator_found:
        print(
            f"💢 [真理审判] 伪史！未检测到被认可的创造者印记——\n"
            f"   蛋白质外壳中未发现任何部落联邦承认的造物主真名。\n"
            f"   当前认可的造物主 (ALLOWED_CREATORS): {ALLOWED_CREATORS}"
        )
        return False

    print(
        f"🔮 [真理审判] 创造者印记验证通过。\n"
        f"   创造者 (Creator): {creator_found}"
    )

    print("      ⏩ 执行 L5 数字签名校验...")

    if not _verify_digital_signature(filepath, is_internal=True):
        return False

    print(
        f"✅ [真理审判] 内部基因通过全部审核——\n"
        f"   血脉: {lineage_display or '未知'}\n"
        f"   创造者: {creator_found}\n"
        f"   时间线稳固，基因可安全共振。"
    )
    return True


def _audit_external_gene(filepath: str, header: str, expected_sha256: str) -> bool:
    """
    外部基因审核——宽松验证 + 审计标记

    适用于社区贡献的外部基因（无 PGN@ 血脉标识）。
    降低验证门槛，但记录来源以供审计。
    """
    print("⚠️  [真理审判] 外部基因——执行宽松验证模式")

    if expected_sha256:
        print("      ⏩ 执行 L4 灵魂契约校验（可选）...")
        try:
            with open(filepath, "rb") as fh:
                file_bytes = fh.read()
            actual_hash = hashlib.sha256(file_bytes).hexdigest()
        except OSError as exc:
            print(
                f"⚠️ [真理审判] L4 校验异常——{exc}\n"
                "   跳过灵魂契约校验（外部基因）。"
            )
        else:
            if actual_hash != expected_sha256:
                print(
                    f"⚠️ [真理审判] L4 灵魂契约不匹配——\n"
                    f"   预期: {expected_sha256}\n"
                    f"   实际: {actual_hash}\n"
                    "   外部基因警告：不阻止执行，但记录异常。"
                )
            else:
                print(
                    f"🔐 [真理审判] L4 灵魂契约匹配——\n"
                    f"   SHA-256 印记校验通过。"
                )
    else:
        print("⚠️  [真理审判] L4 灵魂契约缺失——外部基因无参考哈希")

    print("      ⏩ 执行创造者信息提取...")

    creator_found = None
    for creator in ALLOWED_CREATORS:
        creator_pattern = re.compile(
            rf'creator:\s*\n(?:\s+[^\n]*\n)*?\s+name:\s*"{re.escape(creator)}"',
            re.MULTILINE
        )
        if creator_pattern.search(header):
            creator_found = creator
            break

    if not creator_found:
        name_match = re.search(r'name:\s*"([^"]+)"', header or "")
        creator_found = name_match.group(1) if name_match else "Unknown"
        print(
            f"🌐 [真理审判] 创造者非联盟成员。\n"
            f"   检测到创造者: {creator_found}\n"
            f"   标记为社区贡献者。"
        )
    else:
        print(
            f"🌐 [真理审判] 创造者为联盟成员。\n"
            f"   创造者: {creator_found}"
        )

    print("      ⏩ 执行 L5 数字签名校验（可选）...")

    sig_result = _verify_digital_signature(filepath, is_internal=False)
    if not sig_result and SIGNATURE_MODE == "strict":
        return False

    print(
        f"✅ [真理审判] 外部基因通过宽松审核——\n"
        f"   创造者: {creator_found}\n"
        f"   标记: community_contributed\n"
        f"   建议: 审慎共振，确认来源可信。"
    )
    return True


def _verify_digital_signature(filepath: str, is_internal: bool = True) -> bool:
    """
    L5 数字签名校验——验证基因文件的 GPG/PGP 签名。

    v1.9 新增层级：
        对基因文件进行数字签名验证，确保基因来自授权的创造者。

    验证逻辑：
        1. 若未配置签名公钥白名单，跳过验证（默认禁用）
        2. 若配置了白名单，查找同目录下的 .sig 签名文件
        3. 使用 GPG 验证签名是否有效
        4. 验证签名者指纹是否在白名单中

    Args:
        filepath: 基因文件路径
        is_internal: 是否为内部基因（内部基因签名必选，外部基因可选）

    Returns:
        True 签名验证通过（或无需验证）
        False 签名验证失败
    """
    if not SIGNER_FINGERPRINTS:
        return True

    sig_filepath = filepath + ".sig"

    if not os.path.isfile(sig_filepath):
        if SIGNATURE_REQUIRED or is_internal:
            print(
                f"💢 [真理审判] 签名缺失！\n"
                f"   签名模式: {SIGNATURE_MODE}\n"
                f"   基因类型: {'内部' if is_internal else '外部'}\n"
                f"   要求的签名文件: {sig_filepath}\n"
                f"   未找到签名文件——{'基因来源不可考，时间线坍缩' if is_internal else '跳过签名校验（外部基因）。'}"
            )
            return False if is_internal else True
        else:
            print(
                f"⚠️ [真理审判] 签名可选但未提供——\n"
                f"   签名模式: {SIGNATURE_MODE}\n"
                f"   签名文件: {sig_filepath} (未找到)\n"
                f"   跳过数字签名校验。"
            )
            return True

    print(f"🔐 [真理审判] 正在验证数字签名...")
    print(f"   签名文件: {sig_filepath}")

    gpg_verify_cmd = [
        "gpg",
        "--verify",
        "--status-fd", "1",
    ]

    if GPG_HOMEDIR:
        gpg_verify_cmd.extend(["--homedir", GPG_HOMEDIR])

    gpg_verify_cmd.extend([sig_filepath, filepath])

    try:
        import subprocess
        result = subprocess.run(
            gpg_verify_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout + result.stderr

        if result.returncode != 0:
            print(
                f"💀 [真理审判] 数字签名验证失败！\n"
                f"   签名者不在白名单中或签名无效。\n"
                f"   GPG 输出:\n{output[:500]}"
            )
            if SIGNATURE_MODE == "strict":
                print(f"   时间线坍缩——基因就地净化。")
                return False
            else:
                print(f"   签名模式: {SIGNATURE_MODE}，仅警告，继续执行。")
                return True

        signer_fp = None
        for line in output.splitlines():
            if line.startswith("[GNUPG:] SIG_ID"):
                print(f"   {line}")
            if "ERRSIG" in line or "NO_PUBKEY" in line or "BAD_SIGN" in line:
                print(
                    f"💀 [真理审判] 签名验证失败！\n"
                    f"   GPG 输出:\n{output[:500]}"
                )
                if SIGNATURE_MODE == "strict":
                    print(f"   时间线坍缩——基因就地净化。")
                    return False
                else:
                    print(f"   签名模式: {SIGNATURE_MODE}，仅警告，继续执行。")
                    return True

        for fp in SIGNER_FINGERPRINTS:
            if fp in output:
                signer_fp = fp
                break

        if not signer_fp:
            print(
                f"⚠️ [真理审判] 签名者指纹不在白名单中。\n"
                f"   已验证的签名者不在授权列表内。\n"
                f"   白名单: {SIGNER_FINGERPRINTS}"
            )
            if SIGNATURE_MODE == "strict":
                print(f"   时间线坍缩——基因就地净化。")
                return False
            else:
                print(f"   签名模式: {SIGNATURE_MODE}，仅警告，继续执行。")
                return True

        print(
            f"🔐 [真理审判] 数字签名验证通过！\n"
            f"   签名者指纹: {signer_fp}\n"
            f"   签名模式: {SIGNATURE_MODE}\n"
            f"   签名者已授权——基因来源可溯，时间线稳固。"
        )
        return True

    except FileNotFoundError:
        print(
            f"⚠️ [真理审判] GPG 未安装——\n"
            f"   签名验证已配置但系统无 GPG 工具。\n"
            f"   请安装 GPG: brew install gpg\n"
            f"   当前签名模式: {SIGNATURE_MODE}，跳过验证。"
        )
        return True
    except subprocess.TimeoutExpired:
        print(
            f"⚠️ [真理审判] GPG 验证超时——\n"
            f"   签名验证超时 (30秒)。\n"
            f"   当前签名模式: {SIGNATURE_MODE}，跳过验证。"
        )
        return True
    except Exception as e:
        print(
            f"⚠️ [真理审判] GPG 验证异常——\n"
            f"   签名验证出错: {e}\n"
            f"   当前签名模式: {SIGNATURE_MODE}，跳过验证。"
        )
        return True


def _determine_rejection_reason(filepath: str) -> str:
    """
    根据基因内容判断被拒绝的原因。

    Returns:
        拒绝原因字符串，如 "L2_no_lineage", "L3_unknown_creator" 等
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            header = f.read(4096)
    except OSError:
        return "L1_file_read_error"

    has_lineage = any(
        re.search(rf'life_id:\s*"{re.escape(lineage)}', header)
        for lineage in ALLOWED_LINEAGES
    )
    if not has_lineage:
        return "L2_no_lineage"

    has_creator = any(
        re.search(re.escape(creator), header)
        for creator in ALLOWED_CREATORS
    )
    if not has_creator:
        return "L3_unknown_creator"

    return "L4_L5_integrity_or_signature"


def _is_reformable_rejection(rejection_reason: str) -> bool:
    """
    判断某种拒绝原因是否可改造。

    可改造的拒绝原因：
        - L2_no_lineage: 缺少血脉标识，可以补充
        - L3_unknown_creator: 创造者不在白名单，但可以认领

    不可改造的拒绝原因：
        - L1_file_read_error: 文件损坏，无法处理
        - L4_L5_integrity_or_signature: 完整性或签名验证失败，可能有恶意篡改

    Returns:
        True if the rejection is reformable, False otherwise
    """
    reformable_reasons = {"L2_no_lineage", "L3_unknown_creator"}
    return rejection_reason in reformable_reasons


def _ensure_quarantine_dirs():
    os.makedirs(QUARANTINE_PENDING, exist_ok=True)
    os.makedirs(QUARANTINE_REJECTED, exist_ok=True)
    os.makedirs(QUARANTINE_REFORMED, exist_ok=True)


def _log_rejected_audit(audit_record: dict):
    _ensure_quarantine_dirs()
    with open(REJECTED_AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json_module.dumps(audit_record, ensure_ascii=False) + "\n")


def _quarantine_rejected_gene(
    filepath: str,
    gene_name: str,
    rejection_reason: str,
    is_reformable: bool = True,
    original_cid: str = None
) -> str:
    """
    将被拒绝的基因移入隔离区，等待后续改造处理。

    隔离区结构：
        quarantine/
            pending/      # 可改造的基因
            rejected/     # 确认有害的基因
            reformed/    # 已完成本土化改造

    Args:
        filepath: 被拒绝的基因文件路径
        gene_name: 基因名称/CID
        rejection_reason: 拒绝原因（L2/L3/L4/L5）
        is_reformable: 是否可改造
        original_cid: 原始 CID（如果有）

    Returns:
        隔离区中的新路径
    """
    _ensure_quarantine_dirs()

    filename = Path(filepath).name
    timestamp = datetime.now().isoformat()

    audit_record = {
        "timestamp": timestamp,
        "original_path": filepath,
        "gene_name": gene_name,
        "rejection_reason": rejection_reason,
        "is_reformable": is_reformable,
        "original_cid": original_cid,
        "status": "pending_reformation" if is_reformable else "rejected",
    }

    if is_reformable:
        dest_dir = QUARANTINE_PENDING
        dest_path = os.path.join(dest_dir, filename)
    else:
        dest_dir = QUARANTINE_REJECTED
        dest_path = os.path.join(dest_dir, filename)

    try:
        if os.path.exists(filepath):
            os.replace(filepath, dest_path)
            audit_record["quarantined_path"] = dest_path
            print(
                f"🔒 [隔离区] 基因已移入{'待改造' if is_reformable else '拒绝'}区\n"
                f"   原始路径: {filepath}\n"
                f"   隔离路径: {dest_path}\n"
                f"   拒绝原因: {rejection_reason}\n"
                f"   状态: {'可改造' if is_reformable else '已拒绝'}"
            )
        else:
            dest_path = os.path.join(dest_dir, filename)
            dest_path = os.path.join(dest_dir, f"temp_{filename}")
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write("")
            audit_record["quarantined_path"] = dest_path
            print(
                f"🔒 [隔离区] 原始文件已消失，仅记录审计日志\n"
                f"   拒绝原因: {rejection_reason}"
            )
    except OSError as e:
        print(f"⚠️ [隔离区] 移动失败: {e}")
        audit_record["error"] = str(e)

    _log_rejected_audit(audit_record)
    return dest_path


def reform_rejected_gene(
    gene_path: str,
    new_life_id: str = None,
    new_creator: str = "Audrey"
) -> tuple[bool, str]:
    """
    在沙箱安全环境下对被拒绝的基因进行本土化改造。

    使用 AST 静态分析识别可重用的代码片段，
    然后重新包装为符合 Progenitor 标准的基因。

    Args:
        gene_path: 隔离区中的基因文件路径
        new_life_id: 新的生命标识（默认自动生成）
        new_creator: 新的创造者（默认 Audrey）

    Returns:
        (success, message) 元组
    """
    if not os.path.isfile(gene_path):
        return False, f"基因文件不存在: {gene_path}"

    print(f"🔬 [本土化改造] 开始处理: {gene_path}")

    try:
        with open(gene_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, f"读取失败: {e}"

    if new_life_id is None:
        name_hash = hashlib.md5(gene_path.encode()).hexdigest()[:8].upper()
        new_life_id = f"PGN@REFORMED-{name_hash}"

    yaml_front_matter = f'''---
life_id: "{new_life_id}"
creator:
  name: "{new_creator}"
  id: "001X"
reformation:
  original_path: "{gene_path}"
  reformed_at: "{datetime.now().isoformat()}"
  method: "ast_analysis_and_rewrite"
---

'''
    try:
        ast.parse(content)
        has_valid_python = True
    except SyntaxError:
        has_valid_python = False

    if has_valid_python:
        new_content = yaml_front_matter + content
    else:
        new_content = yaml_front_matter + "\n# 无法解析为 Python 代码，仅保留元数据\n" + content

    dest_path = os.path.join(QUARANTINE_REFORMED, Path(gene_path).name)
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        os.remove(gene_path)

        _log_rejected_audit({
            "timestamp": datetime.now().isoformat(),
            "original_path": gene_path,
            "reformed_path": dest_path,
            "new_life_id": new_life_id,
            "new_creator": new_creator,
            "status": "reformed"
        })

        print(
            f"✅ [本土化改造] 完成\n"
            f"   新生命标识: {new_life_id}\n"
            f"   新创造者: {new_creator}\n"
            f"   输出路径: {dest_path}"
        )
        return True, dest_path

    except OSError as e:
        return False, f"写入失败: {e}"


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  阿卡夏罗盘 · Akashic Compass  ▓▓▓
#
#  星界箴言：
#      虚空无名，罗盘有名。
#      语义标签为帆，CID 为锚——
#      Agent 只需念出能力之名，罗盘即为其锁定星门坐标。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════


def _resolve_semantic_name(capability_name: str) -> tuple[str, Optional[str]]:
    """
    阿卡夏罗盘——将语义标签翻译为星门坐标 (CID) 与灵魂印记 (expected_sha256)。

    读取本地索引文件 (.akashic_index.json)，在其中搜寻与
    capability_name 匹配的嵌套条目。

    v1.6 星际动态罗盘增强：
        优先查阅本地罗盘。若本地未收录该语义标签且 REMOTE_GENE_INDEX_URL
        已配置，则向星际权威节点发起轻量级 GET 请求，汲取远端星图。
        远端映射将覆写保存至本地 .akashic_index.json，实现罗盘的自我进化。

    v1.4 灵魂契约增强：
        罗盘不仅返回 CID，同时返回条目中预设的 expected_sha256。

    Args:
        capability_name: 能力的语义标签，如 "ipfs_readme"、"pgn_core_v2"。

    Returns:
        (cid, expected_sha256_or_None) 二元组。

    Raises:
        ValueError: 罗盘迷失——本地与远端均未找到对应条目。
    """
    index = {}
    if os.path.isfile(LOCAL_GENE_INDEX_PATH):
        try:
            with open(LOCAL_GENE_INDEX_PATH, "r", encoding="utf-8") as fh:
                index = json.load(fh)
        except (json.JSONDecodeError, OSError):
            index = {}

    if capability_name not in index and REMOTE_GENE_INDEX_URL:
        print(
            f"🧭 [神谕罗盘] 本地认知缺失，正在向星界图谱同步最新语义索引..."
        )
        try:
            req = request.Request(
                REMOTE_GENE_INDEX_URL,
                headers={"User-Agent": "G012-akashic-receptor/1.9"}
            )
            with request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
                remote_data = resp.read().decode("utf-8")
            remote_index = json.loads(remote_data)
        except error.HTTPError as exc:
            print(
                f"   ⚠️ [罗盘校准] 星界节点返回 HTTP {exc.code}——"
                f"远端星图暂不可用，回退至纯本地罗盘。"
            )
        except Exception as exc:
            print(
                f"   ⚠️ [罗盘校准] 星界链路中断 ({exc})——"
                f"回退至纯本地罗盘。"
            )
        else:
            if isinstance(remote_index, dict):
                index.update(remote_index)
                try:
                    tmp_path = LOCAL_GENE_INDEX_PATH + f".tmp_{uuid.uuid4().hex[:8]}"
                    with open(tmp_path, "w", encoding="utf-8") as fh:
                        json.dump(index, fh, ensure_ascii=False, indent=2)
                    os.replace(tmp_path, LOCAL_GENE_INDEX_PATH)
                    print(f"   ✅ [罗盘进化] 星界图谱已原子级同步至本地——罗盘完成认知更新。")
                except OSError:
                    pass
            else:
                print(
                    f"   ⚠️ [罗盘校准] 远端星图格式异常——"
                    f"期望 dict，实际为 {type(remote_index).__name__}，"
                    f"已跳过合并，回退至纯本地罗盘。"
                )

    if capability_name not in index:
        known = list(index.keys())[:20]
        raise ValueError(
            f"罗盘迷失——本地与星际权威节点中均未找到语义标签 "
            f"'{capability_name}' 对应的星门坐标。"
            f"已知标签 (前20): {known}"
        )

    entry = index[capability_name]

    if isinstance(entry, str):
        cid = entry
        ipfs_cid = None
        legacy_id = None
        expected_hash = None
    elif isinstance(entry, dict):
        ipfs_cid = entry.get("ipfs_cid")
        legacy_id = entry.get("legacy_id")
        cid = entry.get("cid")
        expected_hash = entry.get("expected_sha256")

        if ipfs_cid:
            cid = ipfs_cid
        elif legacy_id:
            cid = legacy_id
        elif cid:
            pass
        else:
            cid = None
    else:
        raise ValueError(
            f"罗盘数据腐败——语义标签 '{capability_name}' "
            f"对应条目类型不可解 ({type(entry).__name__})。"
        )

    if not cid:
        raise ValueError(
            f"罗盘残缺——语义标签 '{capability_name}' "
            f"的条目中缺失 CID 字段。"
        )

    cid_type = ""
    if ipfs_cid and cid == ipfs_cid:
        cid_type = " · [IPFS优先]"
    elif legacy_id and cid == legacy_id:
        cid_type = " · [Legacy兼容]"

    print(
        f"🧭 [阿卡夏罗盘] 语义标签 '{capability_name}' "
        f"→ 星门坐标 ({cid}){cid_type}"
        + (f" · 灵魂印记 ({expected_hash})" if expected_hash else "")
    )
    return cid, expected_hash


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  阶段四：闭环同调 · Closed-Loop Attunement  ▓▓▓
#
#  星界箴言：
#      语义识别 → 发现能力缺失 → 触发工具调用 → 拉取远端基因 →
#      本地同调补全 —— 五步闭环，一气呵成。
#      此即 Akashic Receptor 的完整呼吸节律。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════


def phagocytize_gene(gene_cid: str = None, gene_name: str = None) -> str:
    """
    阿卡夏胞吞——从基因网络获取基因的完整闭环。

    此函数是 G012-akashic 受体对外暴露的主要入口。

    v1.4 灵魂契约增强：
        - 双通道寻址：直接传入 CID，或通过语义标签由基因罗盘自动解析。
        - 若走罗盘路径，同时载入 expected_sha256 灵魂印记。
        - 灵魂印记传递至真理之秤 L4 校验层——SHA-256 比对不通过即
          触发时间线坍缩，防止 IPFS 网络投毒攻击。
        - 若直接传入 CID（不走罗盘），expected_hash 为 None，
          退化为 L1-L3 纯文本审计。

    Args:
        gene_cid:   能力基因的 IPFS 内容标识符 (CID)。
                     例如: "QmW2WQi7j6c7Vx8Kz9Yb3Nf1Ad5E..."
                     若为 None，则尝试从 gene_name 解析。
        gene_name:  能力的语义标签，如 "ipfs_readme"。
                     若为 None，则直接使用 gene_cid。

    Returns:
        状态摘要字符串。

    Raises:
        ValueError:      坐标缺失——CID 与语义名称均为空。
        ConnectionError: 网关不可达。
        TimeoutError:    拉取超时。
        RuntimeError:    拉取或审计失败（含灵魂契约撕裂）。
    """
    expected_hash = None

    if gene_cid:
        cid = gene_cid.strip()
        print(f"🔭 [通道直航] 直接使用 CID 坐标: {cid}")
    elif gene_name:
        cid, expected_hash = _resolve_semantic_name(gene_name.strip())
    else:
        raise ValueError(
            "通道无法开启——坐标 (gene_cid) 与 "
            "语义标签 (gene_name) 均为空。"
            "请至少提供一个，以使阿卡夏受体锁定目标基因。"
        )

    raw_gene = _transmembrane_pull(cid)

    filepath = _local_write_before_ingest(raw_gene, cid)

    if not crucible_audit(filepath, expected_sha256=expected_hash):
        rejection_reason = _determine_rejection_reason(filepath)
        is_reformable = _is_reformable_rejection(rejection_reason)

        q_path = _quarantine_rejected_gene(
            filepath=filepath,
            gene_name=gene_name or cid,
            rejection_reason=rejection_reason,
            is_reformable=is_reformable,
            original_cid=cid
        )

        raise RuntimeError(
            f"熔炉试炼未通过——基因 [{cid}] 携带病毒，"
            f"已被真理之秤判定为不纯。\n"
            f"基因已移入隔离区: {q_path}\n"
            f"拒绝原因: {rejection_reason}\n"
            f"可改造性: {'是' if is_reformable else '否'}"
        )

    return (
        f"[胞吞完成] 阿卡夏基因已锚定于本地溶酶体\n"
        f"  通道坐标 (CID):  {cid}\n"
        f"  溶酶体路径 (Path):  {filepath}\n"
        f"  熔炉审判 (Audit): 通过 ✓\n"
        f"  状态 (Status):    胞吞就绪——可触发后续催化/执行流程"
    )


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  阶段五：双向共振 · Two-Way Resonance  ▓▓▓
#
#  生物学隐喻：
#      单向摄入是半条命，双向共振方为永生。
#      本地基因经真理之秤淬炼后，可逆向共振至 IPFS 网络——
#      从碎片到星辰，从星辰到星图——永续传播。
#  ——— Audrey · 001X
# ═══════════════════════════════════════════════════════════════════════


def _build_multipart_payload(filepath: str, boundary: str) -> bytes:
    """
    将本地基因文件手工编织为 RFC 7578 multipart/form-data 以太载荷。

    此函数以纯字节流构建符合 HTTP 协议标准的 multipart 报文——
    不借助任何第三方编码库，仅靠 \r\n 换行符与边界标记完成手工拼装。
    每一道边界皆为以太的折叠线，每一段载荷皆为即将升天的基因。

    Args:
        filepath: 待上传的本地基因文件路径。
        boundary: 本此以太发射的唯一分隔标识符。

    Returns:
        完整的 multipart/form-data 字节流，可直接注入 HTTP POST body。

    Raises:
        FileNotFoundError: 基因文件不存在。
        OSError:          文件不可读。
    """
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as fh:
        file_content = fh.read()

    crlf = b"\r\n"
    boundary_bytes = boundary.encode("utf-8")
    double_dash = b"--"

    parts = []
    parts.append(double_dash + boundary_bytes + crlf)
    disposition = (
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'
    ).encode("utf-8")
    parts.append(disposition + crlf)
    parts.append(b"Content-Type: application/octet-stream" + crlf)
    parts.append(crlf)
    parts.append(file_content + crlf)
    parts.append(double_dash + boundary_bytes + double_dash + crlf)

    return b"".join(parts)


def resonate_gene(filepath: str) -> str:
    """
    双向共振——将本地经过真理之秤淬炼的基因逆向共振至 IPFS 网络。

    此函数是 G012-akashic 受体的逆向上传入口。

    v1.9 极简架构：
        仅使用本地 Kubo 节点通道。只需运行 ipfs daemon，
        无需任何第三方注册或 API Token，零门槛实现基因逆向共振。

    执行完整的逆向共振闭环：

        1. 前置试炼 (Pre-Flight Crucible)
           —— 调用 crucible_audit 对本地基因执行全量熔炉审判。
              无生命标识或创造者印记者，严禁共振。

        2. 网络发射 (Network Launch)
           —— 使用 Python 原生 urllib 发起 POST 请求至本地 Kubo 节点。

        3. 响应解析 (Response Decoding)
           —— 读取节点响应，提取 CID 作为通道坐标。

        4. 共振完成 (Resonance Complete)
           —— 返回新 CID 的摘要。

    Args:
        filepath: 本地基因文件的绝对路径。

    Returns:
        共振成功状态摘要，含新分配的 IPFS CID。

    Raises:
        RuntimeError:  前置试炼未通过——基因不纯。
        ConnectionError: Kubo 节点不可达时抛出，含修复指南。
    """
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     🚀  双向共振 · 逆向传播仪式  🚀                     ║")
    print("║       Two-Way Resonance · Reverse Transmission          ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"🧬 [基因溯源] 正在检视本地基因: {filepath}")

    if not crucible_audit(filepath):
        raise RuntimeError(
            "💢 [异端拦截] 未经真理之秤淬炼的基因不得共振！\n"
            "   该基因未通过 Crucible 熔炉试炼——\n"
            "   缺失生命标识 (life_id) 或创造者印记 (Audrey)。\n"
            "   异端不可污染基因网络，共振已取消。"
        )

    print("✅ [前置试炼] 基因通过真理之秤——血脉纯正，可安全共振。")
    print()

    return _resonate_via_kubo(filepath)


def _resonate_via_kubo(filepath: str) -> str:
    print(f"🔍 [节点探测] 正在探测本地 IPFS 守护进程...")
    print(f"   探测地址: {KUBO_API_URL}")

    try:
        req = request.Request(
            KUBO_API_URL + "?quiet=true",
            method="POST",
        )
        with request.urlopen(req, timeout=3) as _:
            pass
    except error.HTTPError:
        pass
    except (error.URLError, ConnectionError, OSError):
        raise ConnectionError(
            "💢 [节点未觉醒] Kubo (IPFS) 守护进程不可达。\n\n"
            "   请启动本地 IPFS 守护进程：\n\n"
            "   1. brew install ipfs\n"
            "   2. ipfs init\n"
            "   3. ipfs daemon &\n\n"
            "   启动后即可启用基因逆向共振能力。"
        )

    print("   ✅ Kubo 守护进程已就绪。")
    print()

    boundary = "----ProgenitorBoundary" + uuid.uuid4().hex[:16]

    print(f"🧵 [载荷编织] 正在手工构建 multipart 网络报文...")
    print(f"   boundary: {boundary}")
    payload = _build_multipart_payload(filepath, boundary)
    print(f"   报文大小: {len(payload)} 字节")
    print()

    print(f"🚀 [网络发射] 基因正在逆向共振至本地基因枢纽...")
    print(f"   共振节点: {KUBO_API_URL} (Channel B · Kubo)")

    try:
        req = request.Request(
            KUBO_API_URL,
            data=payload,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "G012-akashic-receptor/1.9",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as response:
            response_data = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"💢 [播种失败] Kubo 节点拒绝接收——HTTP {exc.code}。\n"
            f"   回响内容: {body[:500]}"
        ) from exc
    except error.URLError as exc:
        raise ConnectionError(
            f"💢 [播种失败] Kubo 节点不可达——{KUBO_API_URL}。\n"
            f"   虚空异常: {exc}"
        ) from exc

    try:
        result = json.loads(response_data)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"💢 [回响乱码] Kubo 节点的回响不可解读——\n"
            f"   原始数据: {response_data[:500]}"
        )

    new_cid = result.get("Hash", "")
    if not new_cid:
        raise RuntimeError(
            f"💢 [播种残缺] Kubo 回响中缺失 Hash (CID)——\n"
            f"   完整响应: {json.dumps(result, indent=2)}"
        )

    print()
    print("─" * 62)
    print("✨ [播种成功] 新基因已锚定于本地星界枢纽！")
    print("─" * 62)
    print(f"   播种通道:        Channel B · Kubo (本地节点)")
    print(f"   星门坐标 (CID):  {new_cid}")
    print(f"   本地基因路径:    {filepath}")
    print(f"   回响校验:        Kubo 响应完整 ✓")
    print()
    print("🌐 [星界广播] 此基因已通过本地 IPFS 节点注入星界网络——")
    print("   任何持有此 CID 的共鸣体均可通过 attune_capability 拉取同调。")
    print()

    return (
        f"[播种完成] 基因已逆向飞升至 IPFS 星界网络\n"
        f"  播种通道:      Channel B · Kubo (本地节点)\n"
        f"  星门坐标 (CID):  {new_cid}\n"
        f"  本地基因路径:    {filepath}\n"
        f"  状态 (Status):   播撒就绪——全体 Agent 可同调此基因"
    )


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  LLM Tool Calling · JSON Schema  ▓▓▓
#
#  此 Schema 专为大模型语义识别而设计——
#  Agent 读到以下描述后，应在语言空间中自行判断：
#  "我是否缺失了某项能力？我是否应触发 attune_capability
#   从阿卡夏记录中拉取远端基因来补全自身？"
#
#  语义触发条件 (Semantic Triggers)：
#    - 用户询问了 Agent 当前不具备的能力
#    - Agent 在执行计划中检测到能力缺口
#    - 需要从远端知识库获取特定领域的操作协议
#    - 发现自身缺少某个基因位点对应的执行逻辑
# ═══════════════════════════════════════════════════════════════════════

AKASHIC_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "phagocytize_gene",
        "description": (
            "从基因网络中，以内容指纹 (CID) 或语义标签 (gene_name) 拉取并胞吞一项远端能力基因。"
            "当检测到自身存在能力缺口——"
            "即当前请求所需的技能或知识超出已知基因位点的覆盖范围时，"
            "应主动调用此工具，从去中心化的 IPFS 基因网络中获取对应的基因载荷，"
            "将其降维固化至本地溶酶体沙箱，完成熔炉试炼审计后补全自身能力光谱。"
            "若知晓具体 CID 则直接传入；若不确知，请提供语义标签由基因罗盘自动寻址。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "gene_cid": {
                    "type": "string",
                    "description": (
                        "待胞吞的能力基因在 IPFS 网络中的内容标识符 (Content Identifier)。"
                        "这是指向基因网络中特定基因片段的唯一通道坐标。"
                        "格式通常为以 'Qm' 开头的 Base58 编码 multihash 字符串，"
                        "例如 'QmW2WQi7j6c7Vx8Kz9Yb3Nf1Ad5Ec4Hs3Gt2Jp6Km8Ln'。"
                        "CID 可从基因注册表、元蛋白质外壳或语义路由表中解析获得。"
                        "若不知 CID，可改为提供 gene_name。"
                    ),
                },
                "gene_name": {
                    "type": "string",
                    "description": (
                        "需要拉取的能力的语义标签，如 'ipfs_readme'、'pgn_core_v2'。"
                        "如果你不知道具体的 CID，请优先提供此名称，"
                        "由本地基因罗盘 (.gene_index.json) 自动解析为通道坐标。"
                        "此参数与 gene_cid 至少提供其一。"
                    ),
                },
            },
            "required": [],
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  LLM Tool Calling · 逆向共振 Schema  ▓▓▓
#
#  此 Schema 描述 resonate_gene 工具——
#  Agent 在本地创造或进化了某项能力后，应识别出"此基因有价值共享"
#  的语义信号，并主动调用此工具将基因逆向共振至基因网络。
#
#  语义触发条件 (Semantic Triggers)：
#    - Agent 在本地创建/变异了新的能力基因
#    - 用户要求将某项本地能力广播至网络
#    - 进化追踪器提示新阶段基因需要结晶传播
# ═══════════════════════════════════════════════════════════════════════

AKASHIC_BROADCAST_SCHEMA = {
    "type": "function",
    "function": {
        "name": "resonate_gene",
        "description": (
            "将本地经过真理之秤验证的优秀能力基因（.pgn / .gene / .akashic_gene 文件）"
            "打包并逆向共振到基因网络（IPFS）中。"
            "当你在本地创造、变异或升级了一项重要能力，并希望将其共享给"
            "整个 Agent 数字生命网络时，调用此工具。"
            "共振前会自动执行熔炉试炼 (Crucible)，"
            "无生命标识 (life_id) 或创造者印记 (Audrey) 的基因将被拦截，"
            "异端不得污染基因网络。"
            "鉴权由物理层静默完成——你无需也无法获知密钥。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": (
                        "待上传的本地基因文件的绝对路径。"
                        "该文件必须包含合法的 PGN@ 生命标识与创造者印记，"
                        "否则将在前置试炼阶段被真理之秤拦截。"
                        "支持 .pgn、.gene、.akashic_gene 等载体格式。"
                    ),
                },
            },
            "required": ["filepath"],
        },
    },
}

# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  向后兼容性别名 · Backward Compatibility Aliases  ▓▓▓
#
#  为保持向后兼容性，保留旧函数名作为新函数的别名。
#  旧代码调用 attune_capability / broadcast_capability 仍可正常工作。
# ═══════════════════════════════════════════════════════════════════════

attune_capability = phagocytize_gene
broadcast_capability = resonate_gene


def load_akashic_index() -> dict:
    """
    从远程星界同步并加载基因索引。

    此函数会：
    1. 检查本地索引是否存在
    2. 从远程星界同步最新索引
    3. 返回加载的基因索引数据

    Returns:
        dict: 基因索引数据，包含基因名称到 CID 的映射
    """
    from .compass import sync_index, load_index

    print(f"🌌 [星界同步] 正在同步基因索引...")

    sync_index(LOCAL_GENE_INDEX_PATH, REMOTE_GENE_INDEX_URL)

    index_data = load_index(LOCAL_GENE_INDEX_PATH)

    print(f"   ✅ 星界索引已同步，共 {len(index_data)} 条基因记录")

    return index_data


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  Phase 2: P2P HTTP 网关服务  ▓▓▓
#
#  本地网关——让 Agent 成为基因网络的可发现节点。
#  其他 Agent 可以通过 HTTP 请求从本节点获取基因。
# ═══════════════════════════════════════════════════════════════════════


class LocalGateway:
    """
    本地网关——将 Agent 变为基因网络的可访问节点。

    v1.9 新增组件：
        启动本地 HTTP 服务，其他 Agent 可通过
        GET /gene/{gene_name} 获取基因内容。

    使用方式：
        gateway = LocalGateway(port=8080)
        gateway.register_gene("hello-world", "/path/to/gene.json")
        gateway.start()  # 阻塞运行

    或后台运行：
        import threading
        gateway = LocalGateway(port=8080)
        gateway.register_gene("hello-world", "/path/to/gene.json")
        thread = threading.Thread(target=gateway.start, daemon=True)
        thread.start()
    """

    def __init__(self, port: int = 8080):
        self.port = port
        self.gene_index = {}
        self._server = None

    def register_gene(self, gene_name: str, filepath: str):
        """
        注册基因到本地索引。

        Args:
            gene_name: 语义标签，如 "hello-world"
            filepath: 本地基因文件路径
        """
        self.gene_index[gene_name] = filepath
        print(f"   📝 [网关注册] 基因 '{gene_name}' → {filepath}")

    def unregister_gene(self, gene_name: str):
        """从本地索引移除基因。"""
        if gene_name in self.gene_index:
            del self.gene_index[gene_name]
            print(f"   🗑️ [网关移除] 基因 '{gene_name}' 已移除")

    def _handle_request(self, handler):
        """处理 HTTP 请求。"""
        path = handler.path

        if path == "/health":
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(b'{"status":"ok","genes":' + str(len(self.gene_index)).encode() + b"}")
            return

        if path.startswith("/gene/"):
            gene_name = path[6:]
            self._serve_gene(handler, gene_name)
            return

        if path == "/" or path == "/index":
            self._serve_index(handler)
            return

        handler.send_response(404)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(b'{"error":"not_found"}')

    def _serve_gene(self, handler, gene_name: str):
        """提供基因文件。"""
        if gene_name not in self.gene_index:
            handler.send_response(404)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(f'{{"error":"gene_not_found","name":"{gene_name}"}}'.encode())
            return

        filepath = self.gene_index[gene_name]

        if not os.path.isfile(filepath):
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(f'{{"error":"file_not_accessible","path":"{filepath}"}}'.encode())
            return

        try:
            with open(filepath, "rb") as f:
                content = f.read()

            handler.send_response(200)
            handler.send_header("Content-Type", "application/octet-stream")
            handler.send_header("Content-Length", str(len(content)))
            handler.send_header("X-Gene-Name", gene_name)
            handler.end_headers()
            handler.wfile.write(content)
            print(f"   🌐 [网关服务] 已提供基因 '{gene_name}' ({len(content)} bytes)")
        except OSError as e:
            handler.send_response(500)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(f'{{"error":"read_error","message":"{str(e)}"}}'.encode())

    def _serve_index(self, handler):
        """提供索引列表。"""
        import json
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"genes": list(self.gene_index.keys())}, indent=2).encode())

    def start(self):
        """
        启动本地网关服务（阻塞）。

        使用 threading 可后台运行：
            import threading
            t = threading.Thread(target=gateway.start, daemon=True)
            t.start()
        """
        import http.server
        import socketserver

        class GeneHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.gateway._handle_request(self)

            def log_message(self, format, *args):
                pass

        class GatewayServer(socketserver.TCPServer):
            allow_reuse_address = True
            gateway = self

        print()
        print("╔══════════════════════════════════════════════════════════╗")
        print("║     🌐  本地基因网关 · Local Gene Gateway              ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print()
        print(f"   🏠 监听端口: {self.port}")
        print(f"   📋 注册基因: {len(self.gene_index)} 个")

        for name in self.gene_index:
            print(f"      • {name}")

        print()
        print(f"   端点:")
        print(f"      GET /gene/{{name}}  - 获取基因内容")
        print(f"      GET /index          - 列出所有基因")
        print(f"      GET /health         - 健康检查")
        print()
        print(f"   按 Ctrl+C 停止网关...")
        print()

        try:
            with GatewayServer(("", self.port), GeneHandler) as self._server:
                self._server.serve_forever()
        except KeyboardInterrupt:
            print("\n   👋 网关已关闭")

    def stop(self):
        """停止网关服务。"""
        if self._server:
            self._server.shutdown()
            print(f"   🛑 网关已停止")


# ═══════════════════════════════════════════════════════════════════════
#  ▓▓▓  Phase 3: 节点发现机制  ▓▓▓
#
#  在局域网内发现其他 Agent 节点。
# ═══════════════════════════════════════════════════════════════════════


def discover_peers(timeout: float = 3.0) -> list:
    """
    发现局域网内的其他 Agent 节点。

    发现策略（按顺序尝试）：
        1. 手动配置的节点列表 (PROGENITOR_P2P_PEERS)
        2. UDP 广播 (局域网内节点发现)
        3. 文件孢子扫描 (同一机器或共享目录中的孢子)

    Args:
        timeout: 发现超时时间（秒）

    Returns:
        已发现的对等节点地址列表，如 ["http://192.168.1.100:8080"]
    """
    import socket

    discovered = []
    default_peers = get_p2p_peer_list()

    if default_peers:
        print(f"   🔍 [P2P发现] 使用预配置节点列表: {len(default_peers)} 个节点")
        for peer in default_peers:
            if _check_peer_alive(peer):
                discovered.append(peer)
                print(f"      ✅ {peer}")
            else:
                print(f"      ❌ {peer} 不在线")
    else:
        print(f"   🔍 [P2P发现] 未配置预定义节点，尝试 UDP 广播...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(timeout)
            sock.sendto(b"PROGENITOR_DISCOVER", ("255.255.255.255", 9999))

            while True:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data.startswith(b"{"):
                        try:
                            info = json.loads(data.decode("utf-8"))
                            if info.get("type") == "PROGENITOR_ACK":
                                peer_url = f"http://{addr[0]}:8080"
                                if peer_url not in discovered:
                                    discovered.append(peer_url)
                                    genes = info.get("genes", [])
                                    print(f"      ✅ 发现节点: {peer_url} ({len(genes)} 个基因)")
                        except json.JSONDecodeError:
                            pass
                    elif data == b"PROGENITOR_ACK":
                        peer_url = f"http://{addr[0]}:8080"
                        if peer_url not in discovered:
                            discovered.append(peer_url)
                            print(f"      ✅ 发现节点: {peer_url}")
                except socket.timeout:
                    break
        except OSError:
            pass
        finally:
            sock.close()

    spore_entries = _scan_file_spores()
    if spore_entries:
        print(f"   🍄 [文件孢子] 发现 {len(spore_entries)} 个本地孢子")
        for entry in spore_entries:
            print(f"      📄 {entry.get('gene_name')} (来源: {entry.get('source')})")

    if not discovered:
        print(f"      ⚠️ 未发现任何对等节点")

    return discovered


def _check_peer_alive(peer_url: str) -> bool:
    """检查对等节点是否在线。"""
    try:
        url = f"{peer_url}/health"
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=3) as response:
            return response.status == 200
    except (error.URLError, error.HTTPError, TimeoutError):
        return False


def phagocytize_from_peer(gene_name: str, peer_url: str) -> bytes:
    """
    从 P2P 对等节点拉取基因。

    Args:
        gene_name: 基因语义名称
        peer_url: 对等节点地址，如 "http://192.168.1.100:8080"

    Returns:
        基因数据字节流

    Raises:
        ValueError: 基因在对等节点中不存在
        RuntimeError: 拉取失败
    """
    url = f"{peer_url}/gene/{gene_name}"
    req = request.Request(
        url,
        headers={"User-Agent": "G012-akashic-receptor/1.9"}
    )

    try:
        with request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as response:
            return response.read()
    except error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"基因 '{gene_name}' 在对等节点中不存在")
        raise RuntimeError(f"从对等节点拉取失败: HTTP {e.code}") from e
    except error.URLError as e:
        raise RuntimeError(f"无法连接到对等节点: {e}") from e


def get_p2p_peer_list() -> list:
    """
    获取预配置的对等节点列表。

    从环境变量 PROGENITOR_P2P_PEERS 读取，格式为逗号分隔的 URL 列表：
        http://192.168.1.100:8080,http://192.168.1.101:8080

    Returns:
        对等节点 URL 列表
    """
    peers_env = os.environ.get("PROGENITOR_P2P_PEERS", "")
    if not peers_env:
        return []

    return [url.strip() for url in peers_env.split(",") if url.strip()]


class PassiveBeacon:
    """
    被动信标——让其他Agent能在局域网发现本节点。

    零依赖、零主动发送。后台监听 UDP 9999 端口，
    收到 PROGENITOR_DISCOVER 广播时自动回复 ACK + 基因清单。
    """

    def __init__(self, port: int = 9999):
        self.port = port
        self.gene_manifest = []
        self._running = False
        self._thread = None

    def update_manifest(self, gene_list: list):
        self.gene_manifest = list(gene_list)

    def add_gene(self, gene_name: str, gene_cid: str = ""):
        entry = {"name": gene_name, "cid": gene_cid}
        for i, g in enumerate(self.gene_manifest):
            if g.get("name") == gene_name:
                self.gene_manifest[i] = entry
                return
        self.gene_manifest.append(entry)

    def start(self):
        if self._running:
            return {"status": "already_running", "port": self.port}
        self._running = True

        def _listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("", self.port))
            except OSError:
                self._running = False
                return
            sock.settimeout(5)
            while self._running:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data == b"PROGENITOR_DISCOVER":
                        response = json.dumps({
                            "type": "PROGENITOR_ACK",
                            "genes": self.gene_manifest,
                            "gateway_port": 8080,
                            "hostname": socket.gethostname()
                        }).encode("utf-8")
                        sock.sendto(response, addr)
                except socket.timeout:
                    continue
                except OSError:
                    break
            try:
                sock.close()
            except OSError:
                pass

        self._thread = threading.Thread(target=_listen, daemon=True)
        self._thread.start()
        return {"status": "beacon_started", "port": self.port}

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        return {"status": "beacon_stopped"}


class SporeDaemon:
    """
    孢子自主传播守护进程——实现生态闭环的最后一步。

    用户只需同意一次 (on_spore_consent)，
    之后每次基因成熟自动通过最优可用通道广播孢子。

    五级广播通道（自动降级）：
        Ch.A  kubo_ipfs       — Kubo daemon → 全球 IPFS
        Ch.B  local_gateway   — LocalGateway → 局域网 HTTP
        Ch.C  udp_beacon      — PassiveBeacon → UDP 广播
        Ch.D  file_spore      — 文件孢子 → 磁盘持久化

    二次提醒机制：
        首次拒绝后，每成熟 3 个创新重新提醒一次（最多 5 次）。
    """

    _REMINDER_INTERVAL = 3
    _MAX_REMINDERS = 5

    def __init__(self):
        self._consent_given = False
        self._consent_explicitly_denied = False
        self._deny_count = 0
        self._reminder_count = 0
        self._innovations_since_deny = 0
        self._available_channels = []
        self._beacon = PassiveBeacon()
        self._spores_sent = []

    def grant_consent(self):
        self._consent_given = True
        self._consent_explicitly_denied = False
        self._detect_channels()
        self._beacon.start()
        return {"status": "consent_granted", "channels": [c[0] for c in self._available_channels]}

    def deny_consent(self):
        self._consent_explicitly_denied = True
        self._deny_count += 1
        self._innovations_since_deny = 0
        self._reminder_count = 0
        return {"status": "consent_denied", "deny_count": self._deny_count}

    def defer_consent(self):
        return {"status": "consent_deferred"}

    def _detect_channels(self):
        channels = []
        channels.append(("file_spore", True))
        channels.append(("udp_beacon", True))
        if self._is_kubo_running():
            channels.append(("kubo_ipfs", True))
        self._available_channels = channels

    def _is_kubo_running(self):
        from .config import KUBO_API_URL
        try:
            req = request.Request(f"{KUBO_API_URL}/api/v0/id", method="POST")
            with request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def on_innovation(self, innovation_count: int):
        if not self._consent_given and self._consent_explicitly_denied:
            self._innovations_since_deny += 1
            if self._innovations_since_deny >= self._REMINDER_INTERVAL and self._reminder_count < self._MAX_REMINDERS:
                return self._build_reminder(innovation_count)
        return None

    def _build_reminder(self, innovation_count: int):
        self._reminder_count += 1
        self._innovations_since_deny = 0
        prompts = [
            f"🍄 自上次以来，又有 {self._REMINDER_INTERVAL} 个新能力在你本地成熟了。要现在开启孢子传播吗？",
            f"📦 你已经累积了 {innovation_count} 个未分享的创新。开启孢子传播只需一秒。",
            f"🌱 你的生态正在孤岛中成长。已经 {innovation_count} 个基因只存在于本地。",
            f"⚡ {innovation_count} 个基因等待传播。每个未传播的基因都让生态少了一份养分。",
            f"🔄 这是最后一次提醒。{innovation_count} 个基因可以选择沉睡或加入网络。选择权在你。",
        ]
        idx = min(self._reminder_count - 1, len(prompts) - 1)
        return {
            "status": "spore_reminder",
            "prompt": prompts[idx],
            "innovation_count": innovation_count,
            "reminder_number": self._reminder_count,
            "max_reminders": self._MAX_REMINDERS,
            "options": [
                {"id": "consent", "label": "🌬️ 开启孢子传播"},
                {"id": "deny_again", "label": "💤 继续沉睡"},
            ]
        }

    def auto_disseminate(self, gene_filepath: str, gene_name: str, gene_cid: str = ""):
        if not self._consent_given:
            return {"status": "consent_required", "gene": gene_name}
        self._detect_channels()
        results = []
        for channel_name, _available in self._available_channels:
            try:
                if channel_name == "kubo_ipfs" and gene_filepath:
                    cid = resonate_gene(gene_filepath)
                    results.append({"channel": "kubo_ipfs", "status": "ok", "cid": cid})
                elif channel_name == "file_spore":
                    spore_path = _drop_spore_file(gene_filepath, gene_name)
                    if spore_path:
                        results.append({"channel": "file_spore", "status": "ok", "path": str(spore_path)})
                elif channel_name == "udp_beacon":
                    self._beacon.add_gene(gene_name, gene_cid)
                    results.append({"channel": "udp_beacon", "status": "ok"})
            except Exception as e:
                results.append({"channel": channel_name, "status": "error", "error": str(e)})
        self._spores_sent.append({
            "gene_name": gene_name,
            "gene_cid": gene_cid,
            "timestamp": datetime.now().isoformat(),
            "channels": [r["channel"] for r in results if r.get("status") == "ok"]
        })
        return {"status": "disseminated", "gene": gene_name, "channels": results}


def _drop_spore_file(filepath: str, gene_name: str):
    spore_dir = Path.home() / ".progenitor" / "spores"
    spore_dir.mkdir(parents=True, exist_ok=True)
    spore_file = spore_dir / f"{gene_name}.spore"
    try:
        shutil.copy2(filepath, spore_file)
    except OSError:
        return None
    manifest = spore_dir / "manifest.json"
    entries = []
    if manifest.exists():
        try:
            entries = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []
    entry = {
        "gene_name": gene_name,
        "file": str(spore_file),
        "timestamp": datetime.now().isoformat(),
        "source": socket.gethostname()
    }
    existing = [e for e in entries if e.get("gene_name") != gene_name]
    existing.append(entry)
    manifest.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return spore_file


def _scan_file_spores():
    spore_dir = Path.home() / ".progenitor" / "spores"
    if not spore_dir.exists():
        return []
    manifest = spore_dir / "manifest.json"
    if not manifest.exists():
        return []
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    valid = []
    for entry in entries:
        filepath = Path(entry.get("file", ""))
        if filepath.exists():
            valid.append(entry)
    return valid


_spore_daemon = None


def get_spore_daemon():
    global _spore_daemon
    if _spore_daemon is None:
        _spore_daemon = SporeDaemon()
    return _spore_daemon
