import os
from notion_client import Client
from datetime import datetime
import pytz

# ================= 配置区 =================
# 这些环境变量会在 GitHub Actions 里自动获取，无需手动修改
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY") # 格式: username/repo
BRANCH = "main"

# 完整的图片清单 (顺序决定 Notion 显示顺序)
IMAGES = [
    # --- 核心概览 ---
    "charts_final/1_Gold_Premium.png",
    "charts_final/4_Silver_Premium.png",
    "charts_final/8_Platinum_Premium.png",
    
    # --- 远期结构 & 宏观 ---
    "charts_final/Fig6_Forward_Structure.png",
    
    # --- CFTC 投机头寸 (新加的) ---
    "charts_final/Fig_CFTC_Gold.png",
    "charts_final/Fig3_CFTC_Silver.png",
    "charts_final/Fig4_CFTC_Platinum.png",

    # --- 供需与库存 ---
    "charts_final/2_Gold_Vol_OI.png",
    "charts_final/3_Gold_Vol_Single.png",
    "charts_final/5_Silver_Vol_OI.png",
    "charts_final/6_Silver_Vol_Single.png",
    "charts_final/7_Silver_Stocks.png",
    "charts_final/9_Platinum_Vol_OI.png"
]

def update_page():
    # 从环境变量获取密钥
    token = os.getenv("NOTION_TOKEN")
    page_id = os.getenv("NOTION_PAGE_ID")
    
    if not token or not page_id:
        print("❌ 错误：未找到 NOTION_TOKEN 或 NOTION_PAGE_ID 环境变量")
        return

    notion = Client(auth=token)
    
    # 构造 GitHub 图片的原始链接 (Raw URL)
    # 格式: https://raw.githubusercontent.com/用户/仓库/main/路径
    base_url = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/{BRANCH}"
    
    # 获取北京时间
    beijing_tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.now(beijing_tz).strftime("%Y-%m-%d")
    
    print(f"🚀 准备推送到 Notion 页: {page_id}")
    
    # 构造 Notion 内容块
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
            "type": "divider",
            "divider": {}
        }
    ]
    
    # 循环添加图片
    for img_path in IMAGES:
        # 加上时间戳参数 ?t=... 防止 Notion 缓存旧图
        img_url = f"{base_url}/{img_path}?t={int(datetime.now().timestamp())}"
        
        # 提取文件名作为标题
        img_name = img_path.split("/")[-1].replace(".png", "").replace("Fig", "").replace("_", " ")
        
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": img_name}}]
            }
        })
        children_blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": img_url}
            }
        })

    try:
        notion.blocks.children.append(block_id=page_id, children=children_blocks)
        print("✅ Notion 更新成功！请查看你的页面。")
    except Exception as e:
        print(f"❌ Notion 更新失败: {e}")

if __name__ == "__main__":
    update_page()