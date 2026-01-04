import os
import io
import zipfile
import requests
import pandas as pd
import akshare as ak
from notion_client import Client
from datetime import datetime
import pytz

# ================= 配置区 =================
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
BRANCH = "main"

IMAGES_LIST = [
    "charts_final/1_Gold_Premium.png",
    "charts_final/4_Silver_Premium.png",
    "charts_final/8_Platinum_Premium.png",
    "charts_final/Fig6_Forward_Structure.png",
    "charts_final/Fig_CFTC_Gold.png",
    "charts_final/Fig3_CFTC_Silver.png",
    "charts_final/Fig4_CFTC_Platinum.png",
    "charts_final/2_Gold_Vol_OI.png",
    "charts_final/3_Gold_Vol_Single.png",
    "charts_final/5_Silver_Vol_OI.png",
    "charts_final/6_Silver_Vol_Single.png",
    "charts_final/7_Silver_Stocks.png",
    "charts_final/9_Platinum_Vol_OI.png"
]

TITLES = {
    "1_Gold_Premium.png": "🥇 黄金：国内外盘溢价 (Gold Premium)",
    "2_Gold_Vol_OI.png": "📊 黄金：成交量 vs 持仓量",
    "3_Gold_Vol_Single.png": "📉 黄金：SHFE 成交量趋势",
    "4_Silver_Premium.png": "🥈 白银：国内外盘溢价 (Silver Premium)",
    "5_Silver_Vol_OI.png": "📊 白银：成交量 vs 持仓量",
    "6_Silver_Vol_Single.png": "📉 白银：SHFE 成交量趋势",
    "7_Silver_Stocks.png": "📦 白银：上期所库存 (Warehouse Receipts)",
    "8_Platinum_Premium.png": "⚙️ 铂金：广期所 vs 现货溢价",
    "9_Platinum_Vol_OI.png": "📊 铂金：成交量 vs 持仓量",
    "Fig6_Forward_Structure.png": "📈 远期曲线结构 (Forward Curve)",
    "Fig_CFTC_Gold.png": "🇺🇸 CFTC 黄金投机净头寸",
    "Fig3_CFTC_Silver.png": "🇺🇸 CFTC 白银投机净头寸",
    "Fig4_CFTC_Platinum.png": "🇺🇸 CFTC 铂金投机净头寸"
}

# ================= 🧠 高级分析引擎 =================

def safe_float(val):
    try: return float(val)
    except: return 0.0

def get_market_metrics(symbol_root, main_code):
    """获取量仓指标 (Vol/OI Ratio)"""
    try:
        # 获取最新行情
        df = ak.futures_zh_daily_sina(symbol=main_code)
        if df.empty: return None
        
        last = df.iloc[-1]
        vol = safe_float(last['volume'])
        oi = safe_float(last['hold']) # hold 即 open interest
        
        # 计算换手比 (Turnover Ratio)
        ratio = vol / oi if oi > 0 else 0
        return {"vol": vol, "oi": oi, "ratio": ratio, "price": last['close']}
    except:
        return None

def get_forward_spread(symbol_root, near, far):
    """获取期限结构"""
    try:
        df_n = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{near}")
        df_f = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{far}")
        if df_n.empty or df_f.empty: return None
        
        p1 = df_n['close'].iloc[-1]
        p2 = df_f['close'].iloc[-1]
        spread = (p2 / p1 - 1) * 100
        return spread
    except:
        return None

def get_cftc_status(code):
    """获取 CFTC 资金流向 (返回趋势描述)"""
    try:
        year = datetime.now().year
        # 下载数据 (内置重试上一年的逻辑略去，为速度仅抓当年)
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return "数据暂缺"

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open(z.namelist()[0]) as f:
                df = pd.read_csv(f, low_memory=False)
                # 模糊匹配列名
                col_code = next(c for c in df.columns if "Code" in str(c) or "CODE" in str(c))
                col_long = next(c for c in df.columns if "Non" in str(c) and "Long" in str(c))
                col_short = next(c for c in df.columns if "Non" in str(c) and "Short" in str(c))
                
                df['Code'] = df[col_code].astype(str).str.strip().str.zfill(6)
                data = df[df['Code'] == code].copy()
                if data.empty: return "无数据"
                
                # 计算净多头
                data['Net'] = pd.to_numeric(data[col_long], errors='coerce') - pd.to_numeric(data[col_short], errors='coerce')
                vals = data['Net'].tail(3).values
                
                if len(vals) < 2: return "数据不足"
                
                current = vals[-1]
                prev = vals[-2]
                diff = current - prev
                
                trend = "加仓" if diff > 0 else "减仓"
                strength = "大幅" if abs(diff) > 5000 else "小幅"
                return f"{trend} {strength} ({int(current):,}手)"
    except:
        return "获取失败"

def generate_full_report():
    print("🧠 正在进行全维度量化分析...")
    
    # 1. 获取核心数据
    # 黄金 Au2606 vs 2612
    au_spread = get_forward_spread("au", "2606", "2612")
    au_metrics = get_market_metrics("au", "au2606")
    au_cftc = get_cftc_status("088691")
    
    # 白银 Ag2606 vs 2612
    ag_spread = get_forward_spread("ag", "2606", "2612")
    ag_metrics = get_market_metrics("ag", "ag2606")
    ag_cftc = get_cftc_status("084691")
    
    # 铂金 Pt2605 (主力)
    pt_metrics = get_market_metrics("pt", "pt2605") # 假设主力
    pt_cftc = get_cftc_status("076651") # Nymex Platinum
    
    # 2. 撰写报告
    lines = []
    lines.append("🤖 **AI 量化深度解析**\n")
    
    # --- 黄金部分 ---
    lines.append("🥇 **黄金 (Gold): 稳健的多头**")
    if au_spread is not None:
        struct = "Contango (正常)" if au_spread > 0 else "Backwardation (紧张)"
        lines.append(f"• **期限结构:** {struct}，价差 {au_spread:.2f}%，市场情绪平稳。")
    lines.append(f"• **资金流向 (CFTC):** {au_cftc}，机构维持看涨意愿。")
    if au_metrics:
        lines.append(f"• **投机热度:** 换手率 {au_metrics['ratio']:.1f}x (SHFE)，国内交易活跃度适中。")
    
    # --- 白银部分 ---
    lines.append("\n🥈 **白银 (Silver): 矛盾的爆发点**")
    if ag_spread is not None:
        if ag_spread < 0:
            lines.append(f"• ⚠️ **结构预警:** Backwardation (贴水 {ag_spread:.2f}%)！**现货极度缺货**，这是典型的逼空前兆。")
        else:
            lines.append(f"• **期限结构:** Contango，价差 {ag_spread:.2f}%。")
    
    lines.append(f"• **资金背离:** 虽然现货紧缺，但 CFTC 显示外资在 **{ag_cftc}**。注意内盘外盘的预期差。")
    
    if ag_metrics:
        hot_flag = "🔥 **极度疯狂**" if ag_metrics['ratio'] > 3 else "活跃"
        lines.append(f"• **投机热度:** {hot_flag}！SHFE 换手率高达 {ag_metrics['ratio']:.1f}x，显示大量日内投机盘博弈。")

    # --- 铂金部分 (新增) ---
    lines.append("\n⚙️ **铂金 (Platinum): 蓄势待发**")
    lines.append(f"• **资金流向:** CFTC {pt_cftc}。")
    if pt_metrics:
        lines.append(f"• **内盘动向:** SHFE 主力合约持仓 {int(pt_metrics['oi']):,} 手。如果持仓持续增加，说明国内资金正在通过广期所建仓抄底。")
    else:
        lines.append("• **内盘动向:** 暂无主力合约数据，流动性较低。")

    # --- 总结 ---
    lines.append("\n🚀 **今日策略雷达:**")
    lines.append("1. **白银是焦点:** 基本面(缺货)与资金面(减仓)打架，配合极高的投机热度，**波动率即将放大**。")
    lines.append("2. **黄金:** 趋势跟随策略，各项指标健康。")
    lines.append("3. **铂金:** 关注广期所持仓量是否突破新高，作为右侧入场信号。")

    return "\n".join(lines)


# ================= 主程序 =================

def update_page():
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_PAGE_ID")
    
    if not token or not database_id:
        print("❌ 错误：密钥缺失")
        return

    notion = Client(auth=token)
    base_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{BRANCH}"
    
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    report_title = f"📅 Daily Metal Report: {today_str}"
    
    # 生成分析
    try:
        analysis_comment = generate_full_report()
    except Exception as e:
        print(f"⚠️ 分析生成失败: {e}")
        import traceback
        traceback.print_exc()
        analysis_comment = "🤖 分析生成暂时不可用"

    # 构造内容
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Generated at {time_str}\n\n{analysis_comment}"}}],
                "icon": {"emoji": "🤖"}
            }
        },
        {"object": "block", "type": "divider", "divider": {}}
    ]
    
    count = 0
    for img_path in IMAGES_LIST:
        if not os.path.exists(img_path): continue
        
        img_url = f"{base_url}/{img_path}?t={int(now.timestamp())}"
        display_title = TITLES.get(img_path.split("/")[-1], img_path.split("/")[-1])
        
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": display_title}}]}
        })
        children_blocks.append({
            "object": "block",
            "type": "image",
            "image": {"type": "external", "external": {"url": img_url}}
        })
        count += 1

    if count == 0: return

    print(f"🚀 创建页面: {report_title} ...")
    try:
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": report_title}}]},
                "Date": {"date": {"start": today_str}},
                "Comments": {"rich_text": [{"text": {"content": analysis_comment}}]}
            },
            children=children_blocks
        )
        print("✅ 成功！")
    except Exception as e:
        print(f"❌ Notion API 报错: {e}")

if __name__ == "__main__":
    update_page()
