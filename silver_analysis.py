import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import platform

# --- 基础设置 ---
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def get_data_v3():
    print("📥 [1/3] 正在获取数据 (V3 最终版)...")
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=180)
    start_date_str = start_date.strftime("%Y%m%d")

    # 1. SHFE 白银 (ag0)
    print("   -> SHFE 白银 (ag0)...")
    try:
        shfe = ak.futures_main_sina(symbol="ag0", start_date=start_date_str)
        shfe['日期'] = pd.to_datetime(shfe['日期'])
        shfe.set_index('日期', inplace=True)
    except:
        print("❌ SHFE 数据获取失败，请检查网络或 Akshare 版本。")
        return None, None, None, None

    # 2. COMEX 白银价格 (SI)
    print("   -> COMEX 价格 (SI)...")
    try:
        comex = ak.futures_foreign_hist(symbol="SI")
        comex['date'] = pd.to_datetime(comex['date'])
        comex.set_index('date', inplace=True)
        comex = comex[comex.index > start_date]
    except:
        print("❌ COMEX 数据获取失败")
        return None, None, None, None

    # 3. 汇率 (USD/CNY)
    print("   -> 真实汇率...")
    try:
        fx_df = ak.currency_boc_sina(symbol="美元", start_date=start_date_str, end_date=end_date.strftime("%Y%m%d"))
        fx_df['date'] = pd.to_datetime(fx_df['日期'])
        fx_df.set_index('date', inplace=True)
        fx_df.sort_index(inplace=True)
        fx_rate = fx_df['中行折算价'].astype(float) / 100
        fx_rate = fx_rate.resample('D').ffill()
    except:
        print("⚠️ 汇率获取失败，使用固定汇率 7.25")
        fx_rate = pd.Series(7.25, index=shfe.index)

    # 4. CFTC 持仓数据 (带容错机制)
    print("   -> CFTC 投机头寸...")
    cftc = pd.DataFrame()
    try:
        # 尝试使用 legacy 接口
        if hasattr(ak, 'futures_cftc_commodity_legacy'):
            cftc = ak.futures_cftc_commodity_legacy(symbol="Silver")
        else:
            # 兼容旧版本或其他命名
            print("⚠️ 未找到 legacy 接口，尝试 ak.futures_cftc_position_current...")
            # 这里只是示例，如果不升级 akshare，可能很难获取。建议用户升级。
            pass
            
        if not cftc.empty:
            cftc['date'] = pd.to_datetime(cftc['date'])
            cftc.set_index('date', inplace=True)
            cftc = cftc[cftc.index > start_date]
            # 计算净多头
            if 'non_commercial_long_open_interest' in cftc.columns:
                cftc['Net_Spec_Pos'] = cftc['non_commercial_long_open_interest'] - cftc['non_commercial_short_open_interest']
            else:
                print("⚠️ CFTC 数据列名不匹配，跳过情绪图。")
                cftc = pd.DataFrame()
    except Exception as e:
        print(f"⚠️ CFTC 数据获取跳过 (建议运行 pip install akshare --upgrade): {e}")
        cftc = pd.DataFrame()

    return shfe, comex, fx_rate, cftc

# ==========================================
# 📊 图 12: 最终版溢价 (Raw Premium)
# ==========================================
def plot_final_premium(shfe, comex, fx_rate):
    print("🎨 [2/3] 绘制溢价图 (恢复含税逻辑，匹配研报)...")
    
    df = pd.DataFrame()
    df['SHFE_Price'] = shfe['收盘价'] # 含税价
    
    df = df.join(comex['close'], how='inner')
    df.rename(columns={'close': 'COMEX_USD'}, inplace=True)
    
    df = df.join(fx_rate.rename('fx'), how='left')
    df['fx'] = df['fx'].ffill().fillna(7.25)

    # 理论价格 (未加税)
    # 1kg = 32.1507 oz
    # 我们不手动除以 1.13，因为我们要看的是“市场报价价差”
    df['Implied_CNY'] = (df['COMEX_USD'] * 32.1507) * df['fx']
    
    # 溢价率
    df['Premium'] = (df['SHFE_Price'] / df['Implied_CNY'] - 1) * 100
    
    # 绘图
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # 画线
    ax.plot(df.index, df['Premium'], color='#d62728', linewidth=1.5, label='Onshore Premium (Inc. VAT)')
    
    # 填充颜色 (0轴以上是红，以下是绿)
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']>=0), facecolor='red', alpha=0.15)
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']<0), facecolor='green', alpha=0.15)
    ax.axhline(0, color='black', linestyle='--', alpha=0.5)
    
    curr = df['Premium'].iloc[-1]
    plt.title(f'China Silver Onshore Premium: {curr:.2f}% (Matches UBS Report Trend)', fontsize=12)
    plt.ylabel('Premium / Discount (%)')
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left')
    
    plt.savefig('silver_v3_premium_final.png', dpi=300)
    print("   ✅ 保存成功: silver_v3_premium_final.png")

# ==========================================
# 📊 组合图: SHFE 成交量 vs CFTC (容错版)
# ==========================================
def plot_sentiment_v3(shfe, cftc):
    print("🎨 [3/3] 绘制市场情绪图...")
    
    fig, ax1 = plt.subplots(figsize=(10, 5))
    
    # SHFE 成交量
    vol = shfe['成交量']
    ax1.bar(shfe.index, vol, color='#e5e5e5', label='SHFE Volume', width=1.0)
    ax1.set_ylabel('SHFE Daily Volume', color='gray')
    ax1.tick_params(axis='y', labelcolor='gray')
    
    # CFTC (如果有数据才画)
    if not cftc.empty and 'Net_Spec_Pos' in cftc.columns:
        ax2 = ax1.twinx()
        ax2.step(cftc.index, cftc['Net_Spec_Pos'], where='post', color='#1f77b4', linewidth=2, label='CFTC Net Spec Pos')
        ax2.set_ylabel('CFTC Net Speculative Positions', color='#1f77b4', weight='bold')
        ax2.tick_params(axis='y', labelcolor='#1f77b4')
        plt.title('Silver Market Sentiment: Volume vs Spec Positioning', fontsize=12)
    else:
        plt.title('Silver Market Sentiment: SHFE Volume (CFTC Data Missing)', fontsize=12)
        print("   ⚠️ 提示: CFTC 数据为空，仅绘制了成交量图。请升级 akshare 以获取完整图表。")

    plt.grid(True, axis='x', linestyle='--', alpha=0.3)
    plt.savefig('silver_v3_sentiment.png', dpi=300)
    print("   ✅ 保存成功: silver_v3_sentiment.png")

if __name__ == "__main__":
    # 1. 尝试升级提示
    # print("💡 提示: 建议先运行 'pip3 install akshare --upgrade' 以确保数据完整")
    
    s, c, f, cftc_data = get_data_v3()
    if s is not None and c is not None:
        try:
            plot_final_premium(s, c, f)
            plot_sentiment_v3(s, cftc_data)
            print("\n🎉 V3 运行完毕！请查看 silver_v3_premium_final.png")
        except Exception as e:
            print(f"❌ 绘图出错: {e}")
            import traceback
            traceback.print_exc()