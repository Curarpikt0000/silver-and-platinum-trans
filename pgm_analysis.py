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

def get_real_fx():
    """获取汇率，失败则用固定值"""
    try:
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=180)
        fx_df = ak.currency_boc_sina(symbol="美元", start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"))
        fx_df['date'] = pd.to_datetime(fx_df['日期'])
        fx_df.set_index('date', inplace=True)
        fx_rate = fx_df['中行折算价'].astype(float) / 100
        return fx_rate.resample('D').ffill()
    except:
        return None

def find_active_contract(symbol_root):
    """
    暴力搜索活跃合约 (针对 GFEX 这种新交易所)
    策略：尝试抓取 pt2601 - pt2606，谁有数据且量大就用谁
    """
    print(f"   🔍 正在暴力搜索 {symbol_root} 的活跃合约...")
    # 生成潜在合约列表 (假设当前是2026年初)
    candidates = [f"{symbol_root}260{i}" for i in range(1, 7)] + [f"{symbol_root}2512"]
    
    best_df = pd.DataFrame()
    best_code = ""
    max_len = 0
    
    for code in candidates:
        try:
            # print(f"      试探: {code} ...", end="")
            # 使用日线行情接口
            df = ak.futures_zh_daily_sina(symbol=code)
            if not df.empty and len(df) > 5: # 至少得有几天数据
                # print(f" 有数据 ({len(df)}条)")
                if len(df) > max_len:
                    max_len = len(df)
                    best_df = df
                    best_code = code
            else:
                pass
                # print(" 无效")
        except:
            pass
            
    if not best_df.empty:
        print(f"   ✅ 锁定主力合约: {best_code} ({len(best_df)}条数据)")
        best_df['date'] = pd.to_datetime(best_df['date'])
        best_df.set_index('date', inplace=True)
        return best_df, best_code
    else:
        print(f"   ❌ {symbol_root} 全系合约搜索失败 (可能未上市或无成交)")
        return None, None

def get_benchmark_price(metal_type):
    """
    获取基准价格 (由于 NYMEX 接口不稳，我们尝试多种替代方案)
    1. 尝试 NYMEX 期货 (PL/PA)
    2. 失败则尝试 SGE 现货 (Pt99.95) 作为 'Spot' 代理
    """
    # 方案 A: 原始 NYMEX
    symbol_map = {"Platinum": "PL", "Palladium": "PA"}
    intl_sym = symbol_map.get(metal_type, "")
    
    try:
        df = ak.futures_foreign_hist(symbol=intl_sym)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            # 截取最近半年
            start_dt = datetime.datetime.now() - datetime.timedelta(days=180)
            df = df[df.index > start_dt]
            if not df.empty:
                print(f"   ✅ 获取到 NYMEX {intl_sym} 数据")
                return df['close'], "USD", "NYMEX Futures"
    except:
        pass
    
    # 方案 B: 降级方案 - 使用上海金交所现货 (SGE Spot)
    # 这虽然是国内现货，但如果是计算 '期现溢价' (Futures vs Spot)，这其实更符合逻辑！
    print(f"   ⚠️ NYMEX 接口失效，切换为 SGE 现货作为基准 (计算期现基差)...")
    sge_code = "Pt99.95" if metal_type == "Platinum" else "Ag(T+D)" # 钯金现货很难找，暂无
    if metal_type == "Palladium":
        print("   ❌ 钯金缺乏现货数据，无法绘制对比图。")
        return None, None, None
        
    try:
        # ak.spot_hist_sge(symbol="Pt99.95")
        df = ak.spot_hist_sge(symbol=sge_code)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        start_dt = datetime.datetime.now() - datetime.timedelta(days=180)
        df = df[df.index > start_dt]
        return df['close'], "CNY", "SGE Spot (China)"
    except Exception as e:
        print(f"   ❌ SGE 现货也获取失败: {e}")
        return None, None, None

def plot_pgm_final(metal_name, root_code):
    print(f"\n🎨 [处理 {metal_name}] ------------------")
    
    # 1. 获取国内期货 (暴力搜索)
    dom_df, dom_code = find_active_contract(root_code)
    if dom_df is None:
        return

    # 2. 获取基准价格 (国际期货 或 现货)
    bench_series, currency, bench_name = get_benchmark_price(metal_name)
    if bench_series is None:
        # 如果没有对比数据，只画个价格走势图也行，别空手而归
        print(f"   ⚠️ 仅绘制国内期货 {dom_code} 价格走势...")
        dom_df['close'].plot(figsize=(10,5), title=f'{metal_name} Futures Price ({dom_code})')
        plt.savefig(f'{metal_name}_price_only.png')
        return

    # 3. 对齐
    df = pd.DataFrame()
    df['Futures'] = dom_df['close']
    
    # 清洗时区
    if df.index.tz is not None: df.index = df.index.tz_localize(None)
    if bench_series.index.tz is not None: bench_series.index = bench_series.index.tz_localize(None)
    
    df = df.join(bench_series.rename('Benchmark'), how='inner')
    
    # 4. 计算溢价
    if currency == "USD":
        # 需要汇率换算
        fx = get_real_fx()
        if fx is None: fx = pd.Series(7.25, index=df.index)
        
        # 1 oz = 31.1035 g
        # Benchmark(USD/oz) -> CNY/g
        if isinstance(fx, pd.Series):
             # 对齐汇率
             df = df.join(fx.rename('fx'), how='left').fillna(method='ffill')
             df['fx'] = df['fx'].fillna(7.25)
             df['Bench_CNY'] = (df['Benchmark'] / 31.1035) * df['fx']
        else:
             df['Bench_CNY'] = (df['Benchmark'] / 31.1035) * 7.25
             
    else:
        # 都是人民币 (SGE Spot)，直接比
        # SGE 是 元/克，GFEX 也是 元/克，直接比
        df['Bench_CNY'] = df['Benchmark']

    # 计算溢价 %
    df['Premium'] = (df['Futures'] / df['Bench_CNY'] - 1) * 100
    
    # 5. 绘图
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['Premium'], color='#9467bd', linewidth=2, label='Premium')
    
    ax.axhline(0, color='black', linestyle='--', alpha=0.5)
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']>=0), facecolor='#9467bd', alpha=0.2)
    ax.fill_between(df.index, 0, df['Premium'], where=(df['Premium']<0), facecolor='green', alpha=0.1)
    
    last = df['Premium'].iloc[-1]
    title = f'{metal_name} Premium: {dom_code} vs {bench_name}\nCurrent: {last:.2f}%'
    plt.title(title, fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.ylabel('Premium (%)')
    
    fname = f'{metal_name}_v3_final.png'
    plt.savefig(fname, dpi=300)
    print(f"   🎉 成功保存: {fname}")

if __name__ == "__main__":
    # 铂金 (Platinum) -> search pt...
    plot_pgm_final("Platinum", "pt")
    
    # 钯金 (Palladium) -> search pa...
    plot_pgm_final("Palladium", "pa")