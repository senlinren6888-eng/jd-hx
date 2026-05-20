#!/usr/bin/env python3
"""京东联盟自动化优惠券站 — 快速刷新（跳过图片下载，使用远端URL）"""
import hashlib, json, time, urllib.request, urllib.parse, socket, os, sys
socket.setdefaulttimeout(15)

AK = "4435f5032650fbfdcae8f3e6e9cc2e06"
AS = "c3e7d8cf24dd4bf48d78a86a094d69f0"
PROJECT_DIR = os.path.expanduser("~/jd-hx")
os.makedirs(PROJECT_DIR, exist_ok=True)

def jd_call(method, biz):
    biz_json = json.dumps(biz, ensure_ascii=False, separators=(",", ":"))
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    params = {"method": method, "app_key": AK, "timestamp": ts,
              "format": "json", "v": "1.0", "sign_method": "md5",
              "360buy_param_json": biz_json}
    params["sign"] = hashlib.md5(
        (AS + "".join(f"{k}{params[k]}" for k in sorted(params.keys())) + AS
    ).encode()).hexdigest().upper()
    req = urllib.request.Request("https://api.jd.com/routerjson",
                                  data=urllib.parse.urlencode(params).encode())
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def extract(r):
    for k in r:
        qr = r[k].get("queryResult", r[k].get("result", "{}"))
        data = json.loads(qr) if isinstance(qr, str) else qr
        return data.get("data", [])

# Pull products
channels = [(1, "hot"), (4, "highcomm"), (25, "sports"), (29, "home"), (22, "baby")]
all_products = []
for cid, cname in channels:
    try:
        goods = extract(jd_call("jd.union.open.goods.jingfen.query",
                     {"goodsReq": {"eliteId": cid, "pageIndex": 1, "pageSize": 10}}))
        for g in goods:
            name = g.get("skuName", "")[:60]
            pi = g.get("priceInfo", {})
            ci = g.get("commissionInfo", {})
            im = g.get("imageInfo", {})
            itemId = g.get("itemId", "")
            all_products.append({
                "name": name,
                "price": pi.get("lowestCouponPrice", pi.get("price", 0)),
                "commission": ci.get("commission", 0),
                "rate": ci.get("commissionShare", 0),
                "sales": g.get("inOrderCount30Days", 0),
                "goodRate": g.get("goodCommentsShare", 0),
                "image": (im.get("imageList", [{}])[0].get("url", "") if im.get("imageList") else ""),
                "materialUrl": f"https://jingfen.jd.com/detail/{itemId}.html" if itemId else "",
                "spuid": g.get("spuid", ""),
            })
        print(f"  ✅ 频道{cid}({cname}) 拉取成功", flush=True)
    except Exception as e:
        print(f"  ⚠️ 频道{cid}({cname})失败: {e}", flush=True)

# Dedup, sort, filter
seen = set()
products = []
for p in sorted(all_products, key=lambda x: x["commission"], reverse=True):
    if p["spuid"] not in seen and len(products) < 8 and p["image"]:
        seen.add(p["spuid"])
        products.append(p)

total_commission = sum(p["commission"] for p in products)
print(f"\n✅ 拉取 {len(products)} 个商品, 佣金总额: ¥{total_commission:.2f}", flush=True)

# Self-check: validate links only
errors = []
for i, p in enumerate(products):
    if "/detail/" not in p["materialUrl"] or not p["materialUrl"].endswith(".html"):
        errors.append(f"链接{i+1}格式错误: {p['materialUrl'][:60]}")
    if not p["image"].startswith("http"):
        errors.append(f"图片{i+1}URL无效: {p['image'][:60]}")

if errors:
    print("❌ 自检失败:")
    for e in errors:
        print(f"   {e}")
    sys.exit(1)

print("✅ 自检通过: 链接格式正确，图片URL有效", flush=True)

# Product summary
print("\n📊 选品清单:")
for i, p in enumerate(products):
    print(f"  {i+1}. [{p['rate']}%佣] {p['name'][:40]} — ¥{p['price']} | 佣¥{p['commission']:.2f} | 月销{int(p['sales'])}")

# Generate HTML (use remote URLs, no base64)
cards = ""
for p in products:
    badge = ""
    if p["rate"] >= 30:
        badge = '<span class="badge-hot">超高佣</span>'
    elif p["sales"] >= 2000:
        badge = '<span class="badge-hot">爆款</span>'
    
    cards += f'''        <div class="card">
            <img class="card-img" src="{p["image"]}" loading="lazy" referrerpolicy="no-referrer" onerror="this.style.display='none'">
            <div class="card-body">
                <div class="card-title">{p["name"][:50]}{badge}</div>
                <div class="price-row">
                    <span class="price-now">{int(p["price"])}</span>
                    <span class="coupon-badge">{p["rate"]}%佣</span>
                </div>
                <div class="meta">
                    <span>📦 月销{int(p["sales"])}+</span>
                    <span>⭐ {int(p["goodRate"])}%好评</span>
                </div>
                <div class="commission">{p["commission"]:.2f}</div>
                <a class="btn" href="{p["materialUrl"]}" target="_blank" rel="nofollow">去京东购买 →</a>
            </div>
        </div>
'''

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>今日好物精选 | 京东高佣优选</title>
<meta name="description" content="每日精选京东高佣金好物，AI自动更新比价，{", ".join(p["name"][:15] for p in products[:4])}等热销爆款">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f5;color:#333}}
.header{{background:linear-gradient(135deg,#e4393c,#c1272d);color:#fff;padding:24px 20px;text-align:center}}
.header h1{{font-size:24px;margin-bottom:4px}}
.header p{{font-size:13px;opacity:.85}}
.container{{max-width:1100px;margin:0 auto;padding:15px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:15px}}
.card{{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);transition:transform .2s}}
.card:hover{{transform:translateY(-3px);box-shadow:0 4px 16px rgba(0,0,0,.12)}}
.card-img{{width:100%;height:220px;object-fit:cover;background:#f9f9f9}}
.card-body{{padding:15px}}
.card-title{{font-size:14px;font-weight:600;line-height:1.5;margin-bottom:8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.price-row{{display:flex;align-items:baseline;gap:8px;margin-bottom:6px}}
.price-now{{font-size:24px;color:#e4393c;font-weight:700}}
.price-now::before{{content:"¥";font-size:14px}}
.coupon-badge{{background:#fff3f3;color:#e4393c;border:1px solid #ffd5d5;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}}
.meta{{display:flex;gap:15px;font-size:12px;color:#999;margin-bottom:10px}}
.commission{{font-size:14px;color:#ff6600;font-weight:600;margin-bottom:12px}}
.commission::before{{content:"💰 预估佣金 ¥";font-weight:400}}
.btn{{display:block;width:100%;padding:12px;background:linear-gradient(135deg,#e4393c,#c1272d);color:#fff;text-align:center;border-radius:8px;text-decoration:none;font-size:15px;font-weight:600;transition:opacity .2s}}
.btn:hover{{opacity:.9}}
.badge-hot{{background:#ff6600;color:#fff;padding:2px 6px;border-radius:3px;font-size:11px;margin-left:6px;vertical-align:middle}}
.footer{{text-align:center;padding:30px;color:#999;font-size:12px;line-height:1.8}}
@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.header h1{{font-size:20px}}}}
</style>
</head>
<body>
<div class="header">
    <h1>🔥 今日好物精选</h1>
    <p>京东联盟高佣优选 · AI自动更新 · 实时比价</p>
</div>
<div class="container">
    <div class="grid">
{cards}    </div>
</div>
<div class="footer">
    <p>🤖 本页面由 Hermes AI 自动生成 | 数据来源：京东联盟京粉API</p>
    <p>更新时间：{time.strftime("%Y-%m-%d %H:%M")} | 通过本页面链接购买，我们获得佣金</p>
</div>
</body>
</html>'''

with open(os.path.join(PROJECT_DIR, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)

# Also generate data.json for dashboard
import json as j
data_json = {
    "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    "product_count": len(products),
    "total_commission": round(total_commission, 2),
    "avg_rate": round(sum(p["rate"] for p in products[:8]) / min(len(products), 8), 1),
    "top5": [{"name": p["name"][:30], "price": int(p["price"]), "commission": round(p["commission"], 2), "rate": p["rate"]} for p in products[:5]]
}
with open(os.path.join(PROJECT_DIR, "data.json"), "w") as f:
    j.dump(data_json, f, ensure_ascii=False)

print(f"\n🎉 京东惠选已刷新: index.html ({len(html):,} 字符)", flush=True)
print(f"📊 商品数: {len(products)} | 佣金总额: ¥{total_commission:.2f}", flush=True)
print(f"🌐 https://jd-hx.pages.dev/", flush=True)
