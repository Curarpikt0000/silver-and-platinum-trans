import os
from notion_client import Client
from datetime import datetime
import pytz

# ================= 配置区 =================
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY")
BRANCH = "main"

# 1. 定义图片列表 (文件路径)
# 注意：这里列出所有想展示的图片
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

# 2. 定义美化标题 (文件名 -> 研报标题)
# 如果不想显示英文文件名，就在这里改
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
    page_id = os.getenv("NOTION_PAGE_ID")
    
    if not token or not page_id:
        print("❌ 错误：未找到 NOTION_TOKEN 或 NOTION_PAGE_ID")
        return

    notion = Client(auth=token)
    base_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{BRANCH}"
    
    # 北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.now(beijing_tz).strftime("%Y-%m-%d")
    time_str = datetime.now(beijing_tz).strftime("%H:%M")
    
    print(f"🚀 准备推送日报 ({today_str})...")
    
    # --- 构造 Notion 内容 ---
    children_blocks = [
        {
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": f"📅 Daily Metal Report: {today_str}"}}]
            }
        },
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Update Time: {time_str} (Beijing Time)\nData Source: Akshare & CFTC.gov"}}],
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
    # --- 循环处理图片 ---
    for img_path in IMAGES_LIST:
        # 【关键修复】检查本地文件是否存在
        # 如果 main.py 没生成这张图（比如库存数据挂了），这里就会跳过，防止Notion出现裂图
        if not os.path.exists(img_path):
            print(f"⚠️ 文件未生成，跳过: {img_path}")
            continue
            
        # 构造 URL (加时间戳防缓存)
        img_url = f"{base_url}/{img_path}?t={int(datetime.now().timestamp())}"
        
        # 获取美化标题
        file_name = img_path.split("/")[-1]
        display_title = TITLES.get(file_name, file_name) # 找不到就用文件名
        
        # 添加标题块
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": display_title}}]
            }
        })
        # 添加图片块
        children_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": img_url}
            }
        })
        count += 1

    # 发送请求
    try:
        if count > 0:
            notion.blocks.children.append(block_id=page_id, children=children_blocks)
            print(f"✅ 成功推送 {count} 张图表到 Notion！")
        else:
            print("⚠️ 没有图片生成，取消推送。")
    except Exception as e:
        print(f"❌ Notion API 报错: {e}")

if __name__ == "__main__":
    update_page()
