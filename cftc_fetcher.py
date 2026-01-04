import pandas as pd
import matplotlib.pyplot as plt
import datetime
import io
import requests
import zipfile
import platform

# --- 全局设置 ---
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def find_col(df, keywords):
    """辅助函数：根据关键词模糊查找列名"""
    for col in df.columns:
        # 转大写比较
        c_str = str(col).upper()
        if all(k.upper() in c_str for k in keywords):
            return col
    return None

def download_cftc_year(year):
    """
    下载并智能解析 CFTC ZIP (V4: 基于表头自动匹配)
    """
    url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    print(f"   ☁️ [CFTC] 尝试下载 {year}: {url} ...")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers)
        
        if r.status_code == 404:
            print(f"      ⚠️ {year} 数据未发布 (404)，跳过。")
            return pd.DataFrame()
            
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            filename = z.namelist()[0]
            with z.open(filename) as f:
                # 1. 尝试带表头读取 (header=0)
                try:
                    df = pd.read_csv(f, low_memory=False)
                except:
                    # 如果编码报错，尝试 latin1
                    f.seek(0)
                    df = pd.read_csv(f, low_memory=False, encoding='latin1')

                # 2. 智能寻找关键列
                # 日期列通常叫 "As_of_Date_In_Form_YYMMDD"
                col_date = find_col(df, ["DATE", "YYMMDD"])
                # 代码列通常叫 "CFTC_Contract_Market_Code"
                col_code = find_col(df, ["CODE", "MARKET"]) 
                # 投机多头 "NonComm_Positions_Long_All"
                col_long = find_col(df, ["NON", "LONG", "ALL"])
                # 投机空头 "NonComm_Positions_Short_All"
                col_short = find_col(df, ["NON", "SHORT", "ALL"])
                
                # 检查是否找齐
                if not all([col_date, col_code, col_long, col_short]):
                    print("      ❌ 无法识别列名，文件结构可能已变。")
                    print(f"      检测到的列: {list(df.columns)}")
                    return pd.DataFrame()

                # 3. 提取并标准化
                data = df[[col_date, col_code, col_long, col_short]].copy()
                data.columns = ['Date', 'Code', 'Long', 'Short']
                
                # 4. 清洗数据
                # 日期解析: 格式通常是 YYMMDD (例如 250101)
                data['Date'] = pd.to_datetime(data['Date'], format='%y%m%d', errors='coerce')
                
                # 去除无效日期
                data = data.dropna(subset=['Date'])
                
                # 代码补零 (88691 -> 088691)
                data['Code'] = data['Code'].astype(str).str.strip().str.split('.').str[0].str.zfill(6)
                
                # 数值转换
                data['Long'] = pd.to_numeric(data['Long'], errors='coerce').fillna(0)
                data['Short'] = pd.to_numeric(data['Short'], errors='coerce').fillna(0)
                
                print(f"      ✅ 成功解析 {year} 数据: {len(data)} 条 (由智能表头识别)")
                return data
                
    except Exception as e:
        print(f"      ❌ 下载失败: {e}")
        return pd.DataFrame()

def get_robust_data():
    """获取数据（以现实世界存在的年份为准）"""
    real_now = datetime.datetime.now()
    # 尝试下载去年和今年
    years = [real_now.year - 1, real_now.year]
    
    dfs = []
    for y in years:
        df = download_cftc_year(y)
        if not df.empty:
            dfs.append(df)
    
    if not dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(dfs)
    full_df.set_index('Date', inplace=True)
    full_df.sort_index(inplace=True)
    return full_df

def plot_cftc_v4(df, metal_name, cftc_code, output_file):
    print(f"   🔍 绘图: {metal_name} (Code: {cftc_code})...")
    
    data = df[df['Code'] == cftc_code].copy()
    
    if data.empty:
        print(f"      ⚠️ 未找到 {metal_name} 数据 (Code: {cftc_code})")
        return

    # 计算净头寸
    data['Net_Spec'] = data['Long'] - data['Short']
    
    # 强制取最后 30 周数据 (约7个月)，保证有图
    data_plot = data.tail(30)
    
    if data_plot.empty:
        print("      ⚠️ 数据处理后为空")
        return

    # 打印时间范围供确认
    d_start = data_plot.index[0].strftime('%Y-%m-%d')
    d_end = data_plot.index[-1].strftime('%Y-%m-%d')
    print(f"      📅 绘图区间: {d_start} -> {d_end}")

    # 绘图
    plt.figure(figsize=(10, 5))
    plt.plot(data_plot.index, data_plot['Net_Spec'], color='#1f77b4', linewidth=2, marker='o', markersize=4)
    
    last_val = data_plot['Net_Spec'].iloc[-1]
    
    plt.title(f'CFTC {metal_name} Speculative Net Positions\nLatest: {int(last_val):,} ({d_end})', fontsize=12)
    plt.ylabel('Net Long Contracts')
    plt.axhline(0, color='black', linestyle='--', alpha=0.5)
    plt.grid(True, alpha=0.3)
    
    plt.savefig(output_file, dpi=300)
    print(f"   ✅ 已生成: {output_file}")

if __name__ == "__main__":
    print("🚀 [CFTC V4] 启动智能表头识别版...")
    
    raw_df = get_robust_data()
    
    if not raw_df.empty:
        # 1. Gold
        plot_cftc_v4(raw_df, "Gold", "088691", "charts_final/Fig_CFTC_Gold.png")
        # 2. Silver (Fig 3)
        plot_cftc_v4(raw_df, "Silver", "084691", "charts_final/Fig3_CFTC_Silver.png")
        # 3. Platinum (Fig 4)
        plot_cftc_v4(raw_df, "Platinum", "076651", "charts_final/Fig4_CFTC_Platinum.png")
        
        print("\n🎉 CFTC 任务全部完成！请检查图片。")
    else:
        print("❌ 未获取到有效数据。")