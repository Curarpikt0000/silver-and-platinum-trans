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

# 1. 定义图片列表 (顺序决定 Notion 显示顺序)
IMAGES_LIST = [
    # --- A. 宏观对比 (新) ---
    "charts_final/Fig_Compare_Gold.png",
    "charts_final/Fig_Compare_Silver.png",

    # --- B. 核心价差 ---
    "charts_final/1_Gold_Premium.png",
    "charts_final/4_Silver_Premium.png",
    "charts_final/8_Platinum_Premium.png",
    
    # --- C. 供需结构 ---
    "charts_final/Fig6_Forward_Structure.png",
    
    # --- D. 资金流向 (CFTC - COMEX) ---
    "charts_final/Fig_CFTC_Gold.png",
    "charts_final/Fig_COMEX_Gold_OI.png",       # 新增
    "charts_final/Fig3_CFTC_Silver.png",
    "charts_final/Fig_COMEX_Silver_OI.png",     # 新增
    "charts_final/Fig4_CFTC_Platinum.png",
    "charts_final/Fig_COMEX_Platinum_OI.png",   # 新增

    # --- E. 市场热度 (SHFE) ---
    "charts_final/2_Gold_Vol_OI.png",
    "charts_final/5_Silver_Vol_OI.png",
    "charts_final/9_Platinum_Vol_OI.png",
    "charts_final/7_Silver_Stocks.png",
    "charts_final/3_Gold_Vol_Single.png",
    "charts_final/6_Silver_Vol_Single.png"
]

# 2. 标题美化字典
TITLES = {
    # 对比
    "Fig_Compare_Gold.png": "⚔️ 黄金：中美走势强弱对比 (SHFE vs COMEX)",
    "Fig_Compare_Silver.png": "⚔️ 白银：中美走势强弱对比 (SHFE vs COMEX)",
    
    # 溢价
    "1_Gold_Premium.png": "🥇 黄金：国内外盘溢价 (Gold Premium)",
    "4_Silver_Premium.png": "🥈 白银：国内外盘溢价 (Silver Premium)",
    "8_Platinum_Premium.png": "⚙️ 铂金：广期所 vs 现货溢价",
    
    # 结构
    "Fig6_Forward_Structure.png": "📈 远期曲线结构 (Forward Curve)",
    
    # CFTC
    "Fig_CFTC_Gold.png": "🇺🇸 CFTC 黄金投机净头寸 (Net Specs)",
    "Fig_COMEX_Gold_OI.png": "🇺🇸 COMEX 黄金总持仓 (Total OI)",
    "Fig3_CFTC_Silver.png": "🇺🇸 CFTC 白银投机净头寸 (Net Specs)",
    "Fig_COMEX_Silver_OI.png": "🇺🇸 COMEX 白银总持仓 (Total OI)",
    "Fig4_CFTC_Platinum.png": "🇺🇸 CFTC 铂金投机净头寸 (Net Specs)",
    "Fig_COMEX_Platinum_OI.png": "🇺🇸 COMEX 铂金总持仓 (Total OI)",

    # SHFE 量仓
    "2_Gold_Vol_OI.png": "📊 黄金(SHFE)：成交量 vs 持仓量",
    "5_Silver_Vol_OI.png": "📊 白银(SHFE)：成交量 vs 持仓量",
    "9_Platinum_Vol_OI.png": "📊 铂金(SHFE)：成交量 vs 持仓量",
    "7_Silver_Stocks.png": "📦 白银：上期所库存 (Warehouse Receipts)",
    "3_Gold_Vol_Single.png": "📉 黄金：成交量趋势 (Volume)",
    "6_Silver_Vol_Single.png": "📉 白银：成交量趋势 (Volume)"
}

# ================= 🧠 V3.0 超级分析引擎 =================

def safe_float(val):
    try: return float(val)
    except: return 0.0

def get_trend_health(symbol_code):
    """
    分析趋势健康度 (OI Change vs Price Change)
    返回: (状态描述, 信号强度emoji)
    """
    try:
        # 获取最近5天数据来判断趋势
        df = ak.futures_zh_daily_sina(symbol=symbol_code)
        if df.empty or len(df) < 5: return ("数据不足", "")
        
        # 提取最近两天的持仓和价格
        last_oi = df['hold'].iloc[-1]
        prev_oi = df['hold'].iloc[-2]
        oi_change = last_oi - prev_oi
        
        last_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        price_change = last_close - prev_close
        
        # 逻辑判断
        if price_change > 0 and oi_change > 0:
            return ("量价齐升 (新多入场)", "🟢")
        elif price_change > 0 and oi_change < 0:
            return ("缩量上涨 (空头回补)", "⚠️")
        elif price_change < 0 and oi_change > 0:
            return ("增仓下跌 (新空入场)", "🔴")
        elif price_change < 0 and oi_change < 0:
            return ("缩量下跌 (多头止损)", "⚪️")
        else:
            return ("震荡整理", "➖")
    except:
        return ("分析失败", "")

def get_market_metrics(symbol_root, main_code):
    try:
        df = ak.futures_zh_daily_sina(symbol=main_code)
        if df.empty: return None
        last = df.iloc[-1]
        vol = safe_float(last['volume'])
        oi = safe_float(last['hold'])
        ratio = vol / oi if oi > 0 else 0
        return {"vol": vol, "oi": oi, "ratio": ratio}
    except: return None

def get_forward_spread(symbol_root, near, far):
    try:
        df_n = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{near}")
        df_f = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{far}")
        if df_n.empty or df_f.empty: return None
        p1 = df_n['close'].iloc[-1]
        p2 = df_f['close'].iloc[-1]
        return (p2 / p1 - 1) * 100
    except: return None

def get_cftc_status(code):
    """获取 CFTC 资金流向 (实时下载分析)"""
    try:
        year = datetime.now().year
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
    print("🧠 正在进行 V3.0 全维度量化分析...")
    
    # 1. 黄金 Au (假设主力合约，可按需修改)
    au_spread = get_forward_spread("au", "2606", "2612")
    au_metrics = get_market_metrics("au", "au2606")
    au_health, au_icon = get_trend_health("au2606")
    au_cftc = get_cftc_status("088691")
    
    # 2. 白银 Ag
    ag_spread = get_forward_spread("ag", "2606", "2612")
    ag_metrics = get_market_metrics("ag", "ag2606")
    ag_health, ag_icon = get_trend_health("ag2606")
    ag_cftc = get_cftc_status("084691")
    
    # 3. 铂金 Pt (主力通常是 pt2605 或 pt2609)
    # 为了稳健，我们分析 pt2605
    pt_health, pt_icon = get_trend_health("pt2605") 
    pt_metrics = get_market_metrics("pt", "pt2605")
    pt_cftc = get_cftc_status("076651")

    lines = []
    lines.append("🤖 **AI 量化深度解析 (V3.0)**\n")
    
    # --- 黄金 ---
    lines.append("🥇 **黄金 (Gold):**")
    lines.append(f"• **趋势状态 (SHFE):** {au_health} {au_icon}")
    if au_spread:
        lines.append(f"• **期限结构:** {'Contango (正常)' if au_spread>0 else 'Backwardation'} (价差 {au_spread:.2f}%)")
    lines.append(f"• **美盘资金 (CFTC):** {au_cftc}")
    
    # --- 白银 ---
    lines.append("\n🥈 **白银 (Silver): 焦点战场**")
    lines.append(f"• **趋势状态 (SHFE):** {ag_health} {ag_icon}")
    
    if ag_spread is not None:
        if ag_spread < 0:
            lines.append(f"• 🚨 **逼空信号:** 现货贴水 {ag_spread:.2f}% (Backwardation)！现货极度缺货。")
        else:
            lines.append(f"• **期限结构:** Contango (价差 {ag_spread:.2f}%)")
            
    if ag_metrics and ag_metrics['ratio'] > 3:
        lines.append(f"• 🔥 **投机热度:** 极度过热！换手率 {ag_metrics['ratio']:.1f}x，日内博弈剧烈。")
        
    lines.append(f"• **美盘资金 (CFTC):** {ag_cftc}")

    # --- 铂金 ---
    lines.append("\n⚙️ **铂金 (Platinum): 底部异动**")
    lines.append(f"• **趋势状态 (SHFE):** {pt_health} {pt_icon}")
    lines.append(f"• **美盘资金 (CFTC):** {pt_cftc}")
    
    if pt_metrics and pt_metrics['oi'] > 20000: 
        lines.append(f"• 📢 **吸筹确认:** 持仓量 {int(pt_metrics['oi']):,} 手。如果价格低位+持仓激增，通常是主力底部建仓信号。")

    # --- 总结 ---
    lines.append("\n💡 **Insight:**")
    lines.append("1. **铂金**若出现“量价齐升”或“增仓不跌”，是极佳的左侧关注点。")
    lines.append("2. **白银**若维持高换手+贴水，注意短期波动率爆发风险。")
    
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
    
    # 1. 生成 AI 分析
    try:
        analysis_comment = generate_full_report()
    except Exception as e:
        print(f"⚠️ 分析生成失败: {e}")
        import traceback
        traceback.print_exc()
        analysis_comment = "🤖 分析生成暂时不可用"

    # 2. 构造 Notion 内容块
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Generated at {time_str} (Beijing Time)\n\n{analysis_comment}"}}],
                "icon": {"emoji": "🤖"}
            }
        },
        {"object": "block", "type": "divider", "divider": {}}
    ]
    
    count = 0
    # 3. 循环添加图片
    for img_path in IMAGES_LIST:
        # 智能跳过不存在的图片 (防裂图)
        if not os.path.exists(img_path): 
            # print(f"跳过缺失图片: {img_path}")
            continue
        
        img_url = f"{base_url}/{img_path}?t={int(now.timestamp())}"
        file_name = img_path.split("/")[-1]
        display_title = TITLES.get(file_name, file_name)
        
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

    # 4. 推送到数据库
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
