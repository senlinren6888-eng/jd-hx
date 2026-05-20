#!/usr/bin/env python3
"""数据接口: 为仪表台提供实时京东联盟数据"""
import hashlib, json, time, urllib.request, urllib.parse, socket, os
socket.setdefaulttimeout(15)

AK = "4435f5032650fbfdcae8f3e6e9cc2e06"
AS = "c3e7d8cf24dd4bf48d78a86a094d69f0"

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
        return (json.loads(qr) if isinstance(qr, str) else qr).get("data", [])

# Pull products
channels = [(1, "hot"), (4, "highcomm"), (25, "sports"), (29, "home"), (17, "beauty")]
products = []
for cid, cname in channels:
    try:
        goods = extract(jd_call("jd.union.open.goods.jingfen.query",
                     {"goodsReq": {"eliteId": cid, "pageIndex": 1, "pageSize": 20}}))
        for g in goods:
            pi = g.get("priceInfo", {})
            ci = g.get("commissionInfo", {})
            im = g.get("imageInfo", {})
            products.append({
                "name": (g.get("skuName") or "")[:50],
                "spuid": g.get("spuid", ""),
                "price": pi.get("lowestCouponPrice", pi.get("price", 0)),
                "commission": ci.get("commission", 0),
                "rate": ci.get("commissionShare", 0),
                "sales": g.get("inOrderCount30Days", 0),
                "goodRate": g.get("goodCommentsShare", 0),
                "image": (im.get("imageList", [{}])[0].get("url", "") if im.get("imageList") else ""),
            })
    except:
        pass

# Dedup by spuid, sort by commission
seen = set()
unique = []
for p in sorted(products, key=lambda x: x["commission"], reverse=True):
    if p["spuid"] not in seen:
        seen.add(p["spuid"])
        unique.append(p)

# Calculate stats
total_commission = sum(p["commission"] for p in unique[:8])
avg_rate = sum(p["rate"] for p in unique[:8]) / max(len(unique[:8]), 1)

result = {
    "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    "total_products": len(unique),
    "top_products": unique[:8],
    "stats": {
        "total_commission": round(total_commission, 2),
        "avg_rate": round(avg_rate, 1),
        "top_product": unique[0]["name"][:30] if unique else "",
        "top_commission": round(unique[0]["commission"], 2) if unique else 0,
    }
}

print(json.dumps(result, ensure_ascii=False))
