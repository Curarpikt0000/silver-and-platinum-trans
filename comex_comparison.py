import pandas as pd
import matplotlib.pyplot as plt
import akshare as ak
import yfinance as yf
import datetime
import os
import platform

# --- 设置字体与路径 ---
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = "charts_final"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def get_data(symbol_shfe, symbol_comex, start_date):
    print(f"   🔍 获取数据对比: SHFE({symbol_shfe}) vs COMEX({symbol_comex})...")
    
    # 1. 获取 SHFE 数据 (Akshare)
    try:
        df_shfe = ak.futures_zh_daily_sina(symbol=symbol_shfe)
        df_shfe['date'] = pd.to_datetime(df_shfe['date'])
        df_shfe.set_index('date', inplace=True)
        # 过滤日期
        df_shfe = df_shfe[df_shfe.index >= pd.to_datetime(start_date)]
    except Exception as e:
        print(f"      ❌ SHFE 获取失败: {e}")
        return pd.DataFrame()

    # 2. 获取 COMEX 数据 (Yfinance)
    # 黄金: GC=F, 白银: SI=F
    try:
        df_comex = yf.download(symbol_comex, start=start_date, progress=False)
        if df_comex.empty:
            print("      ❌ COMEX 数据为空")
            return pd.DataFrame()
        # yfinance 返回的 index 就是 datetime
    except Exception as e:
        print(f"      ❌ COMEX 获取失败: {e}")
        return pd.DataFrame()

    # 3. 合并数据
    # 注意时区差异，这里简单对齐日期
    combined = pd.DataFrame()
    combined['SHFE_Close'] = df_shfe['close']
    combined['COMEX_Close'] = df_comex['Close']
    
    # 删除空值 (因为中美假期不同)
    combined.dropna(inplace=True)
    return combined

def plot_comparison(df, metal_name, file_path):
    if df.empty: return

    # --- 归一化处理 (Normalize) ---
    # 让两者都从 100 开始，方便看涨跌幅度的差异
    df['SHFE_Norm'] = df['SHFE_Close'] / df['SHFE_Close'].iloc[0] * 100
    df['COMEX_Norm'] = df['COMEX_Close'] / df['COMEX_Close'].iloc[0] * 100

    plt.figure(figsize=(10, 6))
    
    # 绘图
    plt.plot(df.index, df['SHFE_Norm'], label=f'SHFE {metal_name} (Shanghai)', color='#d62728', linewidth=2)
    plt.plot(df.index, df['COMEX_Norm'], label=f'COMEX {metal_name} (New York)', color='#1f77b4', linewidth=2, linestyle='--')
    
    plt.title(f'{metal_name} Price Strength Comparison (Normalized)', fontsize=14)
    plt.ylabel('Relative Performance (Start=100)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 标注最新价差逻辑
    last_diff = df['SHFE_Norm'].iloc[-1] - df['COMEX_Norm'].iloc[-1]
    status = "Stronger" if last_diff > 0 else "Weaker"
    plt.figtext(0.15, 0.82, f"SHFE is {abs(last_diff):.2f}% {status} than COMEX", 
                bbox=dict(facecolor='white', alpha=0.8), fontsize=10)

    plt.savefig(file_path, dpi=300)
    print(f"      ✅ 生成对比图: {file_path}")

if __name__ == "__main__":
    # 设定开始时间 (最近半年)
    start_date = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d")
    
    # 1. 黄金对比 (au0 vs GC=F)
    data_gold = get_data("au0", "GC=F", start_date)
    plot_comparison(data_gold, "Gold", "charts_final/Fig_Compare_Gold.png")
    
    # 2. 白银对比 (ag0 vs SI=F)
    data_silver = get_data("ag0", "SI=F", start_date)
    plot_comparison(data_silver, "Silver", "charts_final/Fig_Compare_Silver.png")
