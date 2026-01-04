import os
from notion_client import Client
from datetime import datetime
import pytz

# ================= 配置区 =================
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
BRANCH = "main"

# 1. 定义图片列表
IMAGES_LIST = [
    # --- 核心概览 ---
    "charts_final/1_Gold_Premium.png",
    "charts_final/4_Silver_Premium.png",
    "charts_final/8_Platinum_Premium.png",
    
    # --- 宏观结构 ---
    "charts_final/Fig6_Forward_Structure.png",
    
    # --- 资金流向 (CFTC) ---
    "charts_final/Fig_CFTC_Gold.png",
    "charts_final/Fig3_CFTC_Silver.png",
    "charts_final/Fig4_CFTC_Platinum.png",

    # --- 供需量仓 ---
    "charts_final/2_Gold_Vol_OI.png",
    "charts_final/3_Gold_Vol_Single.png",
    "charts_final/5_Silver_Vol_OI.png",
    "charts_final/6_Silver_Vol_Single.png",
    "charts_final/7_Silver_Stocks.png",
    "charts_final/9_Platinum_Vol_OI.png"
]

# 2. 标题美化字典
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

def update_page():
    token = os.getenv("NOTION_TOKEN")
    # 注意：这里实际上是 DATABASE ID
    database_id = os.getenv("NOTION_PAGE_ID") 
    
    if not token or not database_id:
        print("❌ 错误：未找到密钥")
        return

    notion = Client(auth=token)
    base_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{BRANCH}"
    
    # 时间设置
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    today_str = now.strftime("%Y-%m-%d") # 用于 Date 字段
    time_str = now.strftime("%H:%M")
    
    report_title = f"📅 Daily Metal Report: {today_str}"
    
    print(f"🚀 准备在数据库中创建新页面: {report_title}...")
    
    # --- 构造正文块 (Children Blocks) ---
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Generated at {time_str} (Beijing Time)\nSource: Akshare & CFTC"}}],
                "icon": {"emoji": "🤖"}
            }
        },
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        }
    ]
    
    count = 0
    for img_path in IMAGES_LIST:
        # 本地检查文件是否存在 (防裂图)
        if not os.path.exists(img_path):
            continue
            
        img_url = f"{base_url}/{img_path}?t={int(now.timestamp())}"
        file_name = img_path.split("/")[-1]
        display_title = TITLES.get(file_name, file_name)
        
        # 标题
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": display_title}}]
            }
        })
        # 图片
        children_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": img_url}
            }
        })
        count += 1

    if count == 0:
        print("⚠️ 没有生成图片，取消创建页面。")
        return

    # --- 发送请求：创建数据库页面 (Create Page in Database) ---
    try:
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                # 1. 对应 Notion 里的 "Name" 列 (Title 类型)
                "Name": {
                    "title": [
                        {"text": {"content": report_title}}
                    ]
                },
                # 2. 对应 Notion 里的 "Date" 列 (Date 类型)
                "Date": {
                    "date": {"start": today_str}
                }
            },
            # 3. 页面里的内容
            children=children_blocks
        )
        print(f"✅ 成功在数据库中创建页面！包含 {count} 张图表。")
    except Exception as e:
        print(f"❌ Notion API 报错: {e}")
        print("💡 提示: 请检查 Notion 数据库的列名是否真的是 'Name' 和 'Date' (区分大小写)")

if __name__ == "__main__":
    update_page()
