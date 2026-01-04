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

# 图片列表
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

# 标题字典
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

# ================= 🤖 自动分析引擎 =================

def get_forward_status(symbol_root, near, far):
    """计算远期结构状态"""
    try:
        df_near = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{near}")
        df_far = ak.futures_zh_daily_sina(symbol=f"{symbol_root}{far}")
        if df_near.empty or df_far.empty: return None
        
        p_near = df_near['close'].iloc[-1]
        p_far = df_far['close'].iloc[-1]
        spread_pct = (p_far / p_near - 1) * 100
        return spread_pct
    except:
        return None

def get_cftc_trend(code):
    """计算 CFTC 资金流向 (简单版)"""
    try:
        year = datetime.now().year
        # 尝试下载当前年份数据 (若年初无数据则回退的逻辑在复杂版里，这里做简化)
        # 为保证速度，直接尝试当年，失败则忽略
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return "数据暂缺"

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            with z.open(z.namelist()[0]) as f:
                df = pd.read_csv(f, low_memory=False)
                # 寻找列 (兼容性处理)
                col_code = [c for c in df.columns if "Code" in str(c) or "CODE" in str(c)][0]
                col_long = [c for c in df.columns if "Non" in str(c) and "Long" in str(c)][0]
                col_short = [c for c in df.columns if "Non" in str(c) and "Short" in str(c)][0]
                
                # 筛选
                df['Code_Str'] = df[col_code].astype(str).str.strip().str.zfill(6)
                data = df[df['Code_Str'] == code].copy()
                if data.empty: return "无数据"
                
                # 计算最后两周变化
                data['Net'] = pd.to_numeric(data[col_long], errors='coerce') - pd.to_numeric(data[col_short], errors='coerce')
                last_2 = data['Net'].tail(2).values
                if len(last_2) < 2: return "数据不足"
                
                change = last_2[-1] - last_2[-2]
                return "资金流入 🟢" if change > 0 else "资金流出 🔴"
    except:
        return "获取失败"

def generate_analysis_text():
    print("🧠 正在生成 AI 分析报告...")
    
    # 1. 分析远期结构 (假设当前主力合约月份，需根据实际情况微调)
    # 这里写死 2606 vs 2612，实际应用可动态化，但在 Actions 里写死最稳
    gold_spread = get_forward_status("au", "2606", "2612")
    silver_spread = get_forward_status("ag", "2606", "2612")
    
    # 2. 分析 CFTC
    gold_cftc = get_cftc_trend("088691")
    silver_cftc = get_cftc_trend("084691")
    
    # 3. 撰写文案
    lines = []
    lines.append("🤖 **自动量化点评**")
    
    # --- 黄金板块 ---
    lines.append("\n🥇 **黄金 (Gold):**")
    if gold_spread is not None:
        status = "Contango (正常结构)" if gold_spread > 0 else "Backwardation (供应紧张)"
        icon = "🟢" if gold_spread > 0 else "🔴"
        lines.append(f"• 供需结构: {status} {icon} (价差 {gold_spread:.2f}%)")
    else:
        lines.append("• 供需结构: 数据获取中...")
    lines.append(f"• 资金流向: {gold_cftc}")
    
    # --- 白银板块 ---
    lines.append("\n🥈 **白银 (Silver):**")
    if silver_spread is not None:
        status = "Contango (正常)" if silver_spread > 0 else "Backwardation (逼空预警!)"
        icon = "🟢" if silver_spread > 0 else "🚨"
        lines.append(f"• 供需结构: {status} {icon} (价差 {silver_spread:.2f}%)")
    else:
        lines.append("• 供需结构: 数据获取中...")
    lines.append(f"• 资金流向: {silver_cftc}")

    # --- 策略建议 (规则引擎) ---
    lines.append("\n🚀 **策略雷达:**")
    if silver_spread is not None and silver_spread < 0:
        lines.append("⚠️ **重点关注白银！** 现货贴水显示极度缺货，波动率可能放大，注意逼空风险。")
    elif gold_cftc == "资金流入 🟢":
        lines.append("📈 黄金多头趋势稳健，建议持仓跟随。")
    else:
        lines.append("⚖️ 市场进入震荡观察期，建议控制仓位。")
        
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
    
    # 生成时间和标题
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    report_title = f"📅 Daily Metal Report: {today_str}"
    
    # >>> 关键步骤：生成分析文本 <<<
    try:
        analysis_comment = generate_analysis_text()
    except Exception as e:
        print(f"⚠️ 分析生成失败: {e}")
        analysis_comment = "🤖 分析生成暂时不可用"

    # 构造图片内容块
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Generated at {time_str}\n{analysis_comment}"}}],
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

    # 创建页面
    print(f"🚀 创建页面: {report_title} ...")
    try:
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": report_title}}]},
                "Date": {"date": {"start": today_str}},
                # >>> 这里填入 Comments 格子 <<<
                "Comments": {
                    "rich_text": [
                        {"text": {"content": analysis_comment}}
                    ]
                }
            },
            children=children_blocks
        )
        print("✅ 成功！分析已填入 Comments，图表已上传。")
    except Exception as e:
        print(f"❌ Notion API 报错: {e}")
        print("💡 请检查数据库列名是否为 'Comments' (Text类型)")

if __name__ == "__main__":
    update_page()
