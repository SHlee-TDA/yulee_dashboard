# --- 0. GCF 환경 설정 ---
import matplotlib
matplotlib.use('Agg') # ★ GCF 필수: GUI 없는 백엔드 설정

import google.auth
import pandas as pd
import gspread
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from google.oauth2.service_account import Credentials
from datetime import time, timedelta
import matplotlib.font_manager as fm

# -------------------------------------------------------------------
# ★ GCF 필수: 한글 폰트 설정
# 'NanumGothic.ttf' 파일을 main.py와 같은 폴더에 업로드해야 합니다.
# -------------------------------------------------------------------
try:
    font_path = 'NanumGothic.ttf' 
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
except Exception as e:
    print(f"폰트 로드 실패. 기본 폰트로 실행됩니다. 오류: {e}")
    
plt.rcParams['axes.unicode_minus'] = False # 마이너스 기호

# --- 1. GSpread 인증 및 데이터 로드/클린 함수 ---
def data_clean(master_df, birth_date):
    master_df['분유(ml)'] = pd.to_numeric(master_df['분유(ml)'], errors='coerce')
    master_df['기저귀(대/소)'] = master_df['기저귀(대/소)'].fillna('')

    time_str_am_pm = master_df['시간(HH:MM)'].astype(str).str.replace('오전', 'AM').str.replace('오후', 'PM').str.strip()
    time_obj = pd.to_datetime(time_str_am_pm, errors='coerce', format='%p %I:%M:%S')

    # 3. datetime 객체에서 '시간(time)' 정보만 최종 추출
    master_df['시간(HH:MM)'] = time_obj.dt.time

    # --- (↑ 여기까지 수정된 코드입니다 ↑) ---

    # 'date'와 '시간'을 합쳐서 완벽한 'timestamp' 열 생성
    # (이제 이 코드가 오류 없이 정상적으로 작동합니다)
    master_df['timestamp'] = master_df.apply(
        lambda row: pd.Timestamp.combine(row['date'], row['시간(HH:MM)']) if pd.notna(row['시간(HH:MM)']) else pd.NaT,
        axis=1
    )

    master_df = master_df.dropna(subset=['timestamp'])
    master_df = master_df.sort_values(by='timestamp').reset_index(drop=True)

    master_df['주차(Week)'] = ((master_df['timestamp'] - birth_date).dt.days // 7) + 1

    return master_df

def load_and_clean_data():
    """
    Google Sheet에 연결하고 모든 데이터를 불러와 마스터 DataFrame을 생성합니다.
    (GCF 런타임 권한 자동 사용 버전)
    """
    print("--- 1. 데이터 로딩 및 클리닝 시작 ---")
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

    # --- ★ 여기가 수정된 부분 ★ ---
    # GCF 런타임에 설정된 서비스 계정의 권한을 자동으로 가져옵니다.
    creds, _ = google.auth.default(scopes=SCOPES)
    client = gspread.authorize(creds)
    # --- (credentials.json 파일 필요 없음) ---

    # (이하 코드는 동일...)
    spreadsheet_name = "율이데시보드" 
    spreadsheet = client.open(spreadsheet_name)

    # '아이정보' 시트에서 생년월일 읽기
    info_sheet = spreadsheet.worksheet("아이정보")
    birth_date_str = info_sheet.acell('B2').value 
    birth_date = pd.to_datetime(birth_date_str)
    print(f"아기 생년월일: {birth_date_str}")

    all_data_frames = []
    all_sheet_names = [sheet.title for sheet in spreadsheet.worksheets()]

    for sheet_name in all_sheet_names:
        if sheet_name.count('.') == 2 and sheet_name.startswith('2025'):
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                print(f"시트 로딩 중: {sheet_name} ...")
                
                # ★ 컬럼 범위를 D:G (시간,분유,기저귀,메모)로 가정합니다.
                # 템플릿에 맞게 조절하세요. (예: 'D:H')
                records = worksheet.get('D:G') 
                
                if not records or len(records) < 1:
                    print(f"  (경고) '{sheet_name}' 시트에 데이터가 없습니다.")
                    continue

                daily_df = pd.DataFrame(records[1:], columns=records[0])
                
                daily_df['date'] = pd.to_datetime(sheet_name, format='%Y.%m.%d')
                
                # 'B3' 셀에서 몸무게 읽기
                weight_val = worksheet.acell('B3').value 
                daily_df['weight_kg'] = pd.to_numeric(weight_val, errors='coerce')
                
                all_data_frames.append(daily_df)
            except Exception as e:
                print(f"  (오류) '{sheet_name}' 시트 처리 중 오류: {e}")

    if not all_data_frames:
        print("❌ 분석할 날짜 시트를 찾지 못했습니다.")
        return None, None

    master_df = pd.concat(all_data_frames, ignore_index=True)
    master_df = data_clean(master_df, birth_date)
    
    print("--- ✅ 데이터 로딩 및 클리닝 완료 ---")
    return master_df, birth_date

# --- 2. 분석 함수 (Jupyter Notebook에서 완성한 v2.0 함수들) ---

def analyze_daily(daily_df):
    """일별 분석 (v2.0)"""
    # (Jupyter Notebook에서 완성한 코드를 그대로 붙여넣기)
    if daily_df.empty:
        return pd.Series(name="일일 분석 (데이터 없음)")

    total_feed = daily_df['분유(ml)'].sum()
    feed_count = daily_df['분유(ml)'].count()
    diaper_count = daily_df[daily_df['기저귀(대/소)'] != ''].shape[0]

    feed_df = daily_df.dropna(subset=['분유(ml)']).sort_values(by='timestamp')
    intervals = feed_df['timestamp'].diff()
    avg_interval = intervals.mean()
    std_interval = intervals.std() 

    avg_feed_amount = 0
    if feed_count > 0:
        avg_feed_amount = total_feed / feed_count

    stats = {
        '총수유량(ml)': total_feed, '수유횟수(회)': feed_count,
        '기저귀(개)': diaper_count, '평균 수유텀': avg_interval,
        '수유텀 표준편차': std_interval, '1회 평균 수유량(ml)': avg_feed_amount
    }
    return pd.Series(stats, name=daily_df['timestamp'].dt.date.iloc[0])


def analyze_weekly(master_df, birth_date):
    """주별 분석 (v2.0)"""
    # (Jupyter Notebook에서 완성한 코드를 그대로 붙여넣기)
    print("\n--- 📊 2. 주별 분석 시작 ---")
    if '주차(Week)' not in master_df.columns:
        master_df['주차(Week)'] = ((master_df['timestamp'] - birth_date).dt.days // 7) + 1

    # 밤중 수유 (22:00 ~ 06:00)
    night_start, night_end = time(22, 0), time(6, 0)
    night_feed_df = master_df[
        ((master_df['timestamp'].dt.time >= night_start) | (master_df['timestamp'].dt.time < night_end)) &
        (master_df['분유(ml)'].notna())
    ].copy()
    
    night_daily_summary = night_feed_df.groupby(['주차(Week)', night_feed_df['timestamp'].dt.date]).agg(일일_밤중수유=('분유(ml)', 'count'))
    night_weekly_stats = night_daily_summary.groupby('주차(Week)').mean()
    night_weekly_stats.columns = ['밤중수유_하루평균(회)']
    
    # 일일 요약
    daily_summary = master_df.groupby(['주차(Week)', master_df['timestamp'].dt.date]).agg(
        일일_총수유량=('분유(ml)', 'sum'),
        일일_기저귀=('기저귀(대/소)', lambda x: x.loc[x != ''].count()),
        일일_수유횟수=('분유(ml)', 'count')
    )
    weekly_stats = daily_summary.groupby('주차(Week)').mean()
    weekly_stats.columns = ['총수유량_하루평균', '기저귀_하루평균', '수유횟수_하루평균']
    
    # 수유텀 안정성
    feed_df = master_df.dropna(subset=['분유(ml)']).copy()
    feed_df['수유텀'] = feed_df.sort_values(by='timestamp')['timestamp'].diff()
    if '주차(Week)' not in feed_df.columns:
        feed_df['주차(Week)'] = ((feed_df['timestamp'] - birth_date).dt.days // 7) + 1
    stability_stats = feed_df.groupby('주차(Week)')['수유텀'].agg(수유텀_평균='mean', 수유텀_표준편차='std')

    # 통계 합치기
    final_weekly_stats = weekly_stats.join(stability_stats).join(night_weekly_stats).round(2).fillna(0)
    print("--- 📊 주수별 분석 리포트 (v2.0) 📊 ---")
    print(final_weekly_stats)

    # 그래프 그리기
    if 'hour' not in master_df.columns:
        master_df['hour'] = master_df['timestamp'].dt.hour
    feed_data = master_df.dropna(subset=['분유(ml)'])
    unique_weeks = sorted(feed_data['주차(Week)'].unique())
    
    for week in unique_weeks:
        plt.figure(figsize=(12, 6))
        week_data = feed_data[feed_data['주차(Week)'] == week]
        sns.barplot(data=week_data, x='hour', y='분유(ml)', color='skyblue', errorbar=None)
        plt.title(f'★ {week} 주차 ★ 시간대별 1회 평균 수유량', fontsize=16)
        plt.xlabel('시간 (0-23시)', fontsize=12)
        plt.ylabel('1회 평균 수유량 (ml)', fontsize=12)
        plt.xticks(range(0, 24, 2))
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        
        # ★ GCF 필수: /tmp/ 폴더에 저장
        filename = f'/tmp/weekly_feeding_by_hour_week_{week}.png'
        plt.savefig(filename)
        plt.close()
        print(f"✅ '{filename}' 차트 저장 완료")
    
    return final_weekly_stats


def analyze_total(master_df):
    """전체 분석 (v2.1)"""
    # (Jupyter Notebook에서 완성한 코드를 그대로 붙여넣기)
    print("\n--- 📈 3. 전체 분석 시작 ---")
    
    # 1. 일별 요약
    daily_summary = master_df.groupby(master_df['timestamp'].dt.date).agg(
        총수유량=('분유(ml)', 'sum'),
        기저귀=('기저귀(대/소)', lambda x: x.loc[x != ''].count())
    )
    daily_weight = master_df.groupby(master_df['timestamp'].dt.date)['weight_kg'].first()
    daily_summary = daily_summary.join(daily_weight)
    
    # 2. 7일 이동평균(MA)
    window_size = 7
    daily_summary['총수유량_MA'] = daily_summary['총수유량'].rolling(window=window_size, min_periods=1).mean()
    daily_summary['기저귀_MA'] = daily_summary['기저귀'].rolling(window=window_size, min_periods=1).mean()
    print("--- 📈 전체 기간 일별 요약 (MA 포함) 📈 ---")
    print(daily_summary.tail())

    # 3. 트렌드 그래프 3종 (MA 포함)
    fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=True)
    # (그래프 1: 체중)
    axes[0].plot(daily_summary.index, daily_summary['weight_kg'], marker='o', color='b', linestyle='-')
    axes[0].set_title('전체 기간 체중 변화', fontsize=16)
    axes[0].set_ylabel('몸무게 (kg)', fontsize=12)
    axes[0].grid(True, linestyle='--', alpha=0.6)
    # (그래프 2: 수유량 + MA)
    axes[1].bar(daily_summary.index, daily_summary['총수유량'], color='skyblue', alpha=0.7, label='일일 총량')
    axes[1].plot(daily_summary.index, daily_summary['총수유량_MA'], color='red', lw=2.5, label=f'{window_size}일 이동평균')
    axes[1].set_title('전체 기간 일일 총 수유량', fontsize=16)
    axes[1].set_ylabel('총 수유량 (ml)', fontsize=12)
    axes[1].grid(True, linestyle='--', alpha=0.6)
    axes[1].legend()
    # (그래프 3: 기저귀 + MA)
    axes[2].bar(daily_summary.index, daily_summary['기저귀'], color='lightgreen', alpha=0.7, label='일일 횟수')
    axes[2].plot(daily_summary.index, daily_summary['기저귀_MA'], color='darkgreen', lw=2.5, label=f'{window_size}일 이동평균')
    axes[2].set_title('전체 기간 일일 기저귀 교체 횟수', fontsize=16)
    axes[2].set_ylabel('기저귀 횟수 (개)', fontsize=12)
    axes[2].grid(True, linestyle='--', alpha=0.6)
    axes[2].legend()
    fig.autofmt_xdate()
    plt.tight_layout()
    # ★ GCF 필수: /tmp/ 폴더에 저장
    filename_trends = '/tmp/total_trends_over_time_v2.png'
    plt.savefig(filename_trends)
    plt.close(fig)
    print(f"✅ '{filename_trends}' 차트 3종 (MA 포함) 저장 완료")

    # 4. 시간대별 barplot (전체 기간)
    if 'hour' not in master_df.columns:
         master_df['hour'] = master_df['timestamp'].dt.hour
    feed_data = master_df.dropna(subset=['분유(ml)'])
    plt.figure(figsize=(12, 6))
    sns.barplot(data=feed_data, x='hour', y='분유(ml)', color='mediumpurple', errorbar=None)
    plt.title('★ 전체 기간 ★ 시간대별 1회 평균 수유량', fontsize=16)
    plt.xlabel('시간 (0-23시)', fontsize=12)
    plt.ylabel('1회 평균 수유량 (ml)', fontsize=12)
    plt.xticks(range(0, 24, 2))
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    # ★ GCF 필수: /tmp/ 폴더에 저장
    filename_barplot = '/tmp/total_feeding_by_hour_barplot.png'
    plt.savefig(filename_barplot)
    plt.close()
    print(f"✅ '{filename_barplot}' 차트 저장 완료")
    
    # 5. 수유-배변 간격(Lag Time)
    print("\n--- 💩 수유-배변 간격 분석 중 ---")
    poop_events = master_df[master_df['기저귀(대/소)'].isin(['대', '대소'])][['timestamp']].sort_values(by='timestamp')
    feed_events = master_df.dropna(subset=['분유(ml)'])[['timestamp']].sort_values(by='timestamp')
    feed_events_to_merge = feed_events.copy()
    feed_events_to_merge['feed_time'] = feed_events_to_merge['timestamp']

    if not poop_events.empty and not feed_events_to_merge.empty:
        merged = pd.merge_asof(poop_events, feed_events_to_merge, on='timestamp', direction='backward')
        merged['lag_time'] = merged['timestamp'] - merged['feed_time']
        valid_lags = merged[merged['lag_time'] < pd.Timedelta(days=1)]
        if not valid_lags.empty:
            avg_lag = valid_lags['lag_time'].mean()
            print(f"✅ 평균 수유-배변 간격 (Lag Time): {avg_lag}")
        else: print("❌ 유효한 수유-배변 간격 데이터를 찾을 수 없습니다.")
    else: print("❌ 수유 또는 배변 데이터가 부족하여 간격 계산을 스킵합니다.")

    return daily_summary

# --- 3. GCF 진입점 함수 ---

def run_analysis(request):
    """
    Google Cloud Function이 호출할 메인 함수입니다.
    HTTP 요청을 받으면 전체 분석 파이프라인을 실행합니다.
    """
    print("--- 🚀 분석 파이프라인 실행 시작 🚀 ---")
    
    master_df, birth_date = load_and_clean_data()
    
    if master_df is None or birth_date is None:
        return "데이터 로드 실패. 분석을 중단합니다.", 500

    # 분석 함수 실행 (일별, 주별, 전체)
    # (일별 분석은 샘플로 마지막 날짜만 실행)
    last_day_df = master_df[master_df['date'] == master_df['date'].max()]
    daily_stats = analyze_daily(last_day_df)
    print("\n--- ☀️ 1. 일별 분석 (샘플) ☀️ ---")
    print(daily_stats)
    
    weekly_summary = analyze_weekly(master_df, birth_date)
    
    total_summary = analyze_total(master_df)
    
    print("\n--- ✅ 모든 분석 완료 ---")
    
    # TODO: /tmp/ 폴더에 저장된 이미지들을 Google Cloud Storage에 업로드하고,
    # gspread를 이용해 Google Sheet에 이미지 링크를 삽입하는 코드를
    # 여기에 추가하면 완벽한 자동화가 완성됩니다.
    
    return "분석 파이프라인이 성공적으로 실행되었습니다.", 200

# --- 4. 로컬 테스트용 실행 코드 ---
if __name__ == '__main__':
    # 로컬에서 python main.py를 실행할 때
    # GCF의 'request' 객체가 없으므로 가짜 객체(None)로 테스트
    run_analysis(None)