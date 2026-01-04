import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import platform
import os

# ==========================================
# 1. 全局配置
# ==========================================
print("🚀 [最终版] 系统启动...")

# 字体设置
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 输出目录
OUTPUT_DIR = "charts_final"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================
# 2. 工具函数
# ==========================================
def get_real_fx(start_date, end_date):
    """获取真实汇率"""
    try:
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")
        # 尝试获取中国银行汇率
        fx_df = ak.currency_boc_sina(symbol="美元", start_date=start_str, end_date=end_str)
        fx_df['date'] = pd.to_datetime(fx_df['日期'])
        fx_df.set_index('date', inplace=True)
        # 排序并清洗
        fx_df.sort_index(inplace=True)
        fx_rate = fx_df['中行折算价'].astype(float) / 100
        return fx_rate.resample('D').ffill()
    except Exception as e:
        print(f"   ⚠️ 汇率获取微瑕 ({e})，启用备用固定汇率 7.25")
        return pd.Series(7.25, index=pd.date_range(start=start_date, end=end_date))

def plot_dual_axis(df, col1, col2, title, filename, label1='Left', label2='Right'):
    """双轴绘图通用函数"""
    # 检查列是否存在
    if col1 not in df.columns or col2 not in df.columns:
        print(f"   ⚠️ 跳过 {filename}: 缺少数据列 {col1} 或 {col2}")
        return

    fig, ax1 = plt.subplots(figsize=(10, 5))
    
    color1 = 'tab:gray'
    ax1.bar(df.index, df[col1], color=color1, alpha=0.6, label=label1)
    ax1.set_ylabel(label1, color=color1, weight='bold')
    ax1.tick_params(axis='y', labelcolor=color1)
    
    ax2 = ax1.twinx()
    color2 = '#ff7f0e'
    ax2.plot(df.index, df[col2], color=color2, linewidth=2, label=label2)
    ax2.set_ylabel(label2, color=color2, weight='bold')
    ax2.tick_params(axis='y', labelcolor=color2)
    
    plt.title(title, fontsize=12)
    plt.grid(True, axis='x', linestyle='--', alpha=0.3)
    plt.savefig(f"{OUTPUT_DIR}/{filename}", dpi=300)
    print(f"   ✅ 生成: {filename}")

# ==========================================
# 3. 业务逻辑
# ==========================================

def run_gold_task():
    print("\n🌟 [任务 1] 黄金 (Gold)...")
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=180)
    
    try:
        # SHFE
        shfe = ak.futures_main_sina(symbol="au0", start_date=start.strftime("%Y%m%d"))
        shfe['日期'] = pd.to_datetime(shfe['日期'])
        shfe.set_index('日期', inplace=True)
        
        # COMEX (仅价格)
        comex = ak.futures_foreign_hist(symbol="GC")
        comex['date'] = pd.to_datetime(comex['date'])
        comex.set_index('date', inplace=True)
        comex = comex[comex.index > start]
        
        # 汇率
        fx = get_real_fx(start, end)
    except Exception as e:
        print(f"   ❌ 黄金数据中断: {e}")
        return

    # [1] 溢价图
    df = pd.DataFrame({'SHFE': shfe['收盘价']})
    df = df.join(comex['close'], how='inner').rename(columns={'close':'COMEX'})
    df = df.join(fx.rename('fx'), how='left').ffill().fillna(7.25)
    
    # 公式: (SHFE / (COMEX * FX / 31.1035)) - 1
    df['Implied'] = (df['COMEX'] * df['fx']) / 31.1035
    df['Premium'] = (df['SHFE'] / df['Implied'] - 1) * 100
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['Premium'], color='#d62728')
    ax.axhline(0, color='black', linestyle='--')
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']>=0), facecolor='red', alpha=0.1)
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']<0), facecolor='green', alpha=0.1)
    plt.title(f'Gold Premium: {df["Premium"].iloc[-1]:.2f}%', fontsize=12)
    plt.savefig(f"{OUTPUT_DIR}/1_Gold_Premium.png", dpi=300)
    print(f"   ✅ 生成: 1_Gold_Premium.png")
    
    # [2] 成交量 vs 持仓量
    plot_dual_axis(shfe, '成交量', '持仓量', 'Gold (SHFE): Vol vs Open Interest', '2_Gold_Vol_OI.png')
    
    # [3] 单边成交量 (替代对比图)
    plt.figure(figsize=(10, 5))
    plt.plot(shfe.index, shfe['成交量'], color='green', label='SHFE Vol')
    plt.title('Gold Volume (SHFE Only)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{OUTPUT_DIR}/3_Gold_Vol_Single.png", dpi=300)
    print(f"   ✅ 生成: 3_Gold_Vol_Single.png")


def run_silver_task():
    print("\n🌟 [任务 2] 白银 (Silver)...")
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=180)
    
    try:
        shfe = ak.futures_main_sina(symbol="ag0", start_date=start.strftime("%Y%m%d"))
        shfe['日期'] = pd.to_datetime(shfe['日期'])
        shfe.set_index('日期', inplace=True)
        
        comex = ak.futures_foreign_hist(symbol="SI")
        comex['date'] = pd.to_datetime(comex['date'])
        comex.set_index('date', inplace=True)
        comex = comex[comex.index > start]
        
        fx = get_real_fx(start, end)
    except Exception as e:
        print(f"   ❌ 白银数据中断: {e}")
        return

    # [4] 溢价图
    df = pd.DataFrame({'SHFE': shfe['收盘价']})
    df = df.join(comex['close'], how='inner').rename(columns={'close':'COMEX'})
    df = df.join(fx.rename('fx'), how='left').ffill().fillna(7.25)
    
    # 白银换算: 1kg = 32.1507 oz
    df['Implied'] = (df['COMEX'] * 32.1507) * df['fx']
    df['Premium'] = (df['SHFE'] / df['Implied'] - 1) * 100
    
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['Premium'], color='#d62728')
    ax.axhline(0, color='black', linestyle='--')
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']>=0), facecolor='red', alpha=0.1)
    plt.title(f'Silver Premium: {df["Premium"].iloc[-1]:.2f}%', fontsize=12)
    plt.savefig(f"{OUTPUT_DIR}/4_Silver_Premium.png", dpi=300)
    print(f"   ✅ 生成: 4_Silver_Premium.png")
    
    # [5] 成交量 vs 持仓量
    plot_dual_axis(shfe, '成交量', '持仓量', 'Silver (SHFE): Vol vs Open Interest', '5_Silver_Vol_OI.png')

    # [6] 单边成交量
    plt.figure(figsize=(10, 5))
    plt.plot(shfe.index, shfe['成交量'], color='#1f77b4', label='SHFE Vol')
    plt.title('Silver Volume (SHFE Only)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{OUTPUT_DIR}/6_Silver_Vol_Single.png", dpi=300)
    print(f"   ✅ 生成: 6_Silver_Vol_Single.png")
    
    # [7] 库存 (Stocks) - 使用仓单数据
    try:
        # 尝试获取仓单
        stock = ak.futures_shfe_warehouse_receipt(symbol="ag")
        stock['date'] = pd.to_datetime(stock['date'])
        stock.set_index('date', inplace=True)
        stock = stock[stock.index > start]
        # 字段兼容
        col = 'receipt' if 'receipt' in stock.columns else stock.columns[0]
        
        plt.figure(figsize=(10, 5))
        plt.plot(stock.index, stock[col], color='#2ca02c')
        plt.fill_between(stock.index, 0, stock[col], color='#2ca02c', alpha=0.1)
        plt.title('Silver SHFE Stocks (Warehouse Receipts)', fontsize=12)
        plt.savefig(f"{OUTPUT_DIR}/7_Silver_Stocks.png", dpi=300)
        print(f"   ✅ 生成: 7_Silver_Stocks.png")
    except:
        print("   ⚠️ 白银库存数据暂不可用 (接口维护中)")

def run_platinum_task():
    print("\n🌟 [任务 3] 铂金 (Platinum)...")
    
    # 暴力搜索活跃合约
    candidates = [f"pt260{i}" for i in range(1, 7)] + ["pt2512"]
    shfe_pt = pd.DataFrame()
    code = ""
    for c in candidates:
        try:
            df = ak.futures_zh_daily_sina(symbol=c)
            if len(df) > len(shfe_pt):
                shfe_pt = df
                code = c
        except: pass
    
    if shfe_pt.empty:
        print("   ❌ 未找到铂金合约")
        return

    shfe_pt['date'] = pd.to_datetime(shfe_pt['date'])
    shfe_pt.set_index('date', inplace=True)
    # 关键修复: 重命名列
    rename_map = {'volume': '成交量', 'open_interest': '持仓量', 'hold': '持仓量', 'close': '收盘价'}
    shfe_pt.rename(columns=rename_map, inplace=True)

    # [8] 溢价图 (VS SGE Spot)
    try:
        sge = ak.spot_hist_sge(symbol="Pt99.95")
        sge['date'] = pd.to_datetime(sge['date'])
        sge.set_index('date', inplace=True)
        
        df = pd.DataFrame({'Futures': shfe_pt['收盘价']})
        # 时区对其
        if df.index.tz: df.index = df.index.tz_localize(None)
        bench = sge['close']
        if bench.index.tz: bench.index = bench.index.tz_localize(None)
        
        df = df.join(bench.rename('Spot'), how='inner')
        df['Premium'] = (df['Futures'] / df['Spot'] - 1) * 100
        
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['Premium'], color='#9467bd')
        plt.axhline(0, color='black', linestyle='--')
        plt.fill_between(df.index, 0, df['Premium'], where=(df['Premium']>=0), facecolor='#9467bd', alpha=0.2)
        plt.title(f'Platinum Premium ({code} vs SGE): {df["Premium"].iloc[-1]:.2f}%', fontsize=12)
        plt.savefig(f"{OUTPUT_DIR}/8_Platinum_Premium.png", dpi=300)
        print(f"   ✅ 生成: 8_Platinum_Premium.png")
    except Exception as e:
        print(f"   ❌ 铂金溢价图失败: {e}")

    # [9] 量仓图
    plot_dual_axis(shfe_pt, '成交量', '持仓量', f'Platinum ({code}): Vol vs Open Interest', '9_Platinum_Vol_OI.png')

if __name__ == "__main__":
    run_gold_task()
    run_silver_task()
    run_platinum_task()
    print(f"\n🎉 全部完成！请查看 ./{OUTPUT_DIR}/ 文件夹 (应有 9 张图片)")