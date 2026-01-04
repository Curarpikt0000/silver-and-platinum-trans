import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import platform
import os

# ==========================================
# 1. 配置
# ==========================================
print("🚀 [Forward Curve] 开始构建远期结构分析...")

system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = "charts_final"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================
# 2. 核心函数: 获取价差
# ==========================================
def get_term_structure(symbol_root, near_suffix, far_suffix, label_name):
    """
    计算期限结构: (远月 - 近月) / 近月 * 100
    Example: symbol_root='au', near='2606', far='2612'
    """
    near_code = f"{symbol_root}{near_suffix}"
    far_code = f"{symbol_root}{far_suffix}"
    
    print(f"   🔍 分析 {label_name}: {near_code} vs {far_code} ...")
    
    try:
        # 1. 获取近月
        df_near = ak.futures_zh_daily_sina(symbol=near_code)
        if df_near.empty:
            print(f"      ❌ 近月合约 {near_code} 无数据")
            return None
        df_near['date'] = pd.to_datetime(df_near['date'])
        df_near.set_index('date', inplace=True)
        
        # 2. 获取远月
        df_far = ak.futures_zh_daily_sina(symbol=far_code)
        if df_far.empty:
            print(f"      ❌ 远月合约 {far_code} 无数据")
            return None
        df_far['date'] = pd.to_datetime(df_far['date'])
        df_far.set_index('date', inplace=True)
        
        # 3. 对齐数据
        # 截取最近半年 (假设当前是2026-01)
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=180)
        
        df = pd.DataFrame({'Near': df_near['close']})
        df = df.join(df_far['close'].rename('Far'), how='inner')
        df = df[df.index > start_date]
        
        if df.empty:
            print("      ⚠️ 日期对齐后无数据")
            return None
            
        # 4. 计算 Spread % (Implied Yield / Roll Yield Proxy)
        # 简单算法: (Far / Near - 1) * 100
        # 负值 = Backwardation (Tightness)
        df['Spread_Pct'] = (df['Far'] / df['Near'] - 1) * 100
        
        print(f"      ✅ 成功 (最新价差: {df['Spread_Pct'].iloc[-1]:.2f}%)")
        return df['Spread_Pct']
        
    except Exception as e:
        print(f"      ❌ 出错: {e}")
        return None

# ==========================================
# 3. 主程序
# ==========================================
def run_forward_analysis():
    plt.figure(figsize=(12, 6))
    
    # -------------------------------------------------
    # 设定合约对 (假设当前是 2026年1月)
    # -------------------------------------------------
    # 黄金: 6月 vs 12月
    s_gold = get_term_structure("au", "2606", "2612", "Gold")
    if s_gold is not None:
        plt.plot(s_gold.index, s_gold, color='#d62728', linewidth=2, label='Gold (au2606-2612)')

    # 白银: 6月 vs 12月 (白银波动大，容易出现backwardation)
    s_silver = get_term_structure("ag", "2606", "2612", "Silver")
    if s_silver is not None:
        plt.plot(s_silver.index, s_silver, color='#1f77b4', linewidth=2, label='Silver (ag2606-2612)')
        
    # 铂金: 6月 vs 9月 (铂金合约比较少，尝试季月)
    s_plat = get_term_structure("pt", "2606", "2609", "Platinum")
    # 如果 2609 没数据，脚本会自动跳过
    if s_plat is not None:
        plt.plot(s_plat.index, s_plat, color='#2ca02c', linewidth=2, label='Platinum (pt2606-2609)')
        
    # -------------------------------------------------
    # 绘图装饰
    # -------------------------------------------------
    plt.axhline(0, color='black', linestyle='--', linewidth=1.5)
    plt.title('Forward Curve Structure (Implied Roll Yield)', fontsize=14)
    plt.ylabel('Spread % (Far Month vs Near Month)\nNegative = Backwardation (Tightness)', fontweight='bold')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    
    # 标注区域意义
    ylim = plt.gca().get_ylim()
    plt.fill_between(plt.gca().get_xlim(), 0, ylim[1], color='green', alpha=0.05) # Contango
    plt.fill_between(plt.gca().get_xlim(), ylim[0], 0, color='red', alpha=0.05)   # Backwardation
    plt.text(s_gold.index[0], ylim[1]*0.8, " Contango (Normal)", color='green', fontsize=10)
    plt.text(s_gold.index[0], ylim[0]*0.8, " Backwardation (Tight)", color='red', fontsize=10)

    # 保存
    path = f"{OUTPUT_DIR}/Fig6_Forward_Structure.png"
    plt.savefig(path, dpi=300)
    print(f"\n🎉 远期结构图已生成: {path}")
    print("💡 说明: 曲线若在 0 轴下方，代表市场供应紧张 (现货比期货贵)。")

if __name__ == "__main__":
    try:
        run_forward_analysis()
    except Exception as e:
        print(f"❌ 程序崩溃: {e}")