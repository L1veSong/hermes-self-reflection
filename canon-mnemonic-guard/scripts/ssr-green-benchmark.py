"""
SSR GREEN 基准测试脚本 — 独立于 Hermes session 运行
直接调用 Ollama bge-m3 API 测试 embedding 匹配精度

用法:
    python3 scripts/ssr-green-benchmark.py
    
依赖:
    - Ollama 已启动 (http://localhost:11434)
    - bge-m3 模型已拉取 (ollama pull bge-m3)
    - SSR embeddings.json 和 a_rules.json 存在
"""
import json, re, math, time, requests, sys
from pathlib import Path

SSR_DIR = Path.home() / ".hermes" / "plugins" / "ssr"

# ── 阈值（从 config.yaml 读取或使用默认值）──
SIMILARITY_FLOOR = 0.35
CONFIDENCE_THRESHOLD = 0.40

# ── 可自定义的测试场景 ──
TESTS = [
    ("UI设计", "帮我设计一个响应式导航栏", 
     ["brainstorming", "ui-ux-pro-max", "popular-web-designs"]),
    ("代码调试", "这段 Python 代码报 KeyError 帮我看看", 
     ["diagnose", "systematic-debugging"]),
    ("ASCII艺术", "生成一个 ASCII 猫咪图", 
     ["ascii-art"]),
    ("学术写作", "帮我写论文的 Related Work 部分", 
     ["research-paper-writing", "paper-spine-research"]),
    ("金融分析", "分析贵州茅台的均线走势", 
     ["technical-analysis", "tushare-finance"]),
]

PHASE_MAP = {
    "brainstorming": "DISCOVER", "ideation": "DISCOVER", "survey": "DISCOVER",
    "deep-research": "DISCOVER", "arxiv": "DISCOVER",
    "planning-with-files": "PLAN", "plan": "PLAN", "writing-plans": "PLAN",
    "ui-ux-pro-max": "BUILD", "popular-web-designs": "BUILD", "frontend-design": "BUILD",
    "ascii-art": "BUILD", "p5js": "BUILD", "algorithmic-art": "BUILD",
    "diagnose": "VERIFY", "systematic-debugging": "VERIFY", "dogfood": "VERIFY",
    "verification-before-completion": "VERIFY", "tdd": "VERIFY",
    "research-paper-writing": "BUILD", "paper-spine-research": "DISCOVER",
    "paper-spine": "BUILD", "academic-paper": "BUILD",
    "technical-analysis": "BUILD", "tushare-finance": "BUILD",
    "finance-news-analyzer": "BUILD",
}

def infer_phase(name):
    return PHASE_MAP.get(name, "BUILD")

def embed_text(text):
    try:
        resp = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": "bge-m3", "prompt": text},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
    except Exception as e:
        print(f"  [ERROR] embedding 失败: {e}", file=sys.stderr)
    return []

def cosine_sim(a, b):
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0

def main():
    # 加载索引
    a_rules = json.loads((SSR_DIR / "a_rules.json").read_text()) if (SSR_DIR / "a_rules.json").exists() else {}
    emb_data = json.loads((SSR_DIR / "embeddings.json").read_text()) if (SSR_DIR / "embeddings.json").exists() else {}
    
    print(f"A层规则: {len(a_rules)} | Embedding索引: {len(emb_data)}")
    print(f"阈值: similarity_floor={SIMILARITY_FLOOR}, confidence_threshold={CONFIDENCE_THRESHOLD}\n")
    
    results = []
    for label, msg, expected in TESTS:
        print(f"{'='*60}")
        print(f"[{label}] {msg}")
        print(f"期望: {expected}")
        
        # A 层关键词 — regex 模式是 a_rules 的 key
        kw_hits = set()
        for rule_key, rule_data in a_rules.items():
            try:
                if re.search(rule_key, msg, re.IGNORECASE):
                    for s in rule_data.get("skills", []):
                        name = s["name"] if isinstance(s, dict) else s
                        kw_hits.add(name)
            except re.error:
                pass
        print(f"关键词命中: {list(kw_hits)}")
        
        # Embedding
        msg_vec = embed_text(msg)
        if not msg_vec:
            print("  Embedding 失败，跳过")
            continue
        
        scores = []
        for name, entry in emb_data.items():
            if "embedding" not in entry:
                continue
            sim = cosine_sim(msg_vec, entry["embedding"])
            if sim >= SIMILARITY_FLOOR:
                scores.append((sim, name))
        scores.sort(reverse=True)
        
        print(f"Embedding top-5 (≥{SIMILARITY_FLOOR}):")
        for sim, name in scores[:5]:
            marker = " ← 期望" if name in expected else ""
            print(f"  {name}: {sim:.4f}{marker}")
        
        # 合并
        seen = set()
        merged = []
        for n in kw_hits:
            if n not in seen:
                seen.add(n)
                merged.append({"name": n, "_source": "keyword"})
        for sim, name in scores[:30]:
            if name not in seen:
                seen.add(name)
                merged.append({"name": name, "_sim": sim, "_source": "embedding"})
        
        # 置信度
        emb_sims = sorted([h["_sim"] for h in merged if "_sim" in h], reverse=True)
        conf = 1.0 if not emb_sims else sum(emb_sims[:3]) / len(emb_sims[:3])
        
        # 判定
        hit = [e for e in expected if e in seen]
        score = len(hit) / len(expected) if expected else 0
        status = "PASS" if conf >= CONFIDENCE_THRESHOLD and score >= 0.5 else "FAIL"
        
        print(f"置信度: {conf:.4f} | 命中: {hit} ({score:.0%}) | {status}\n")
        
        results.append({
            "label": label, "expected": expected, "hits": list(seen)[:10],
            "confidence": round(conf, 4), "hit_score": score, "status": status,
        })
        time.sleep(0.3)
    
    # 汇总
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{'='*60}")
    print(f"GREEN 汇总: {passed}/{len(results)} 通过")
    for r in results:
        print(f"  {r['status']:4s} | {r['label']:8s} | conf={r['confidence']:.4f} | hit={r['hit_score']:.0%}")

if __name__ == "__main__":
    main()
