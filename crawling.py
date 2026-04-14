########################################
# 라이브러리 불러오기

import pandas as pd
import datetime
from datetime import timedelta

import time
import re

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains # 마우스 오버를 위해
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
 
# 목적지 리스트
arrival_airports= {   
    "일본": ["NRT", "KIX", "FUK"],
    "중국": ["PVG", "PEK", "TAO"], 
    "동북아시아_기타": ["TPE", "HKG","UBN"],
    "동남아시아":["BKK", "DAD", "HAN", "SIN"],
    "서유럽": ["LHR", "CDG", "FRA", "AMS", "ZRH"],
    "남유럽": ["FCO", "BCN", "LIS"],
    "동유럽": ["PRG", "BUD", "WAW", "VIE"],
    "북유럽": ["HEL", "CPH"],
    "미국_서부": ["LAX", "SFO", "LAS"],
    "미국_동부": ["JFK", "EWR", "BOS"],
    "캐나다": ["YVR", "YYZ"],
    "오세아니아": ["GUM", "SYD", "HNL"]
}

    

# WebDriver 및 기타 전역 변수 설정
driver = None
wait = None
actions = None
departure_airport_code = "ICN" # 인천공항 (고정)

# 데이터 저장을 위한 리스트
data_1_1 = [] # 현재 시점 최저가 출발일 항공권 정보
data_1_2 = [] # 현재 시점 출발일에 따른 항공권 가격 분포
data_2_1 = [] # 출발일별 최적 구매일
data_2_2 = [] # 과거 시점 출발일에 따른 항공권 가격 분포
data_2_3 = [] # 항공권의 일반 범위


# 데이터 저장 및 로드 관련 전역 설정
import os
import sqlite3
DB_NAME = "GoogleFlights.db" # SQL 데이터베이스 파일 이름
DATA_DIR = "/Users/hwi/Desktop/ML_project/ML_project_DB" # 상태 파일을 저장할 폴더
STATUS_FILE = os.path.join(DATA_DIR, "crawling_status.json") # 크롤링 상태 저장 파일

# 각 데이터 유형별 JSON 파일 경로 매핑 (백업용으로 유지)
FILE_PATHS = {
    "1-1": os.path.join(DATA_DIR, "data_1_1.json"),
    "1-2": os.path.join(DATA_DIR, "data_1_2.json"),
    "2-1": os.path.join(DATA_DIR, "data_2_1.json"),
    "2-2": os.path.join(DATA_DIR, "data_2_2.json"),
    "2-3": os.path.join(DATA_DIR, "data_2_3.json"),
}


TODAY = datetime.date.today()

########################################

def initialize_driver():
    global driver, wait, actions
    try:
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        #options.add_argument('--headless')   # Spyder에서 실행 시 창을 보고 싶으면 '--headless'를 주석 처리
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--lang=ko') # 언어 설정 (한국어)
        options.add_experimental_option('excludeSwitches', ['enable-logging']) # 불필요한 로그 제거
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1200, 900) # 창 크기 설정
        wait = WebDriverWait(driver, 12) # 최대 12초까지 기다림
        actions = ActionChains(driver)

        print("WebDriver 초기화 완료.")
    except Exception as e:
        print(f"WebDriver 초기화 오류: {e}")
        if driver:
            driver.quit()

########################################

def enter_GoogleFlight(arrival_airport_code):
    """구글 항공권 페이지 열고 편도, 출발지, 목적지 설정"""
    try:
        driver.get("https://www.google.com/travel/flights?hl=ko")

# 1. 드롭다운(왕복/편도) 버튼 누르고 [편도] 선택
## 웹 개발자 도구: "왕복/편도" 텍스트를 가진 요소 찾기
        round_trip_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, '//div[@role = "combobox" and @aria-haspopup = "listbox"]')))
        round_trip_dropdown.click()
        time.sleep(1)

## 웹 개발자 도구: "편도" 텍스트를 가진 요소 찾기
        set_oneway = wait.until(EC.element_to_be_clickable((By.XPATH, '//li[@role="option" and .//span[text()="편도"]]')))
        set_oneway.click()
        print(" 편도 선택 완료.")

# 2. 출발지 입력 (인천공항)
## 웹 개발자 도구: 출발지 입력 필드 찾기
## 클릭하여 활성화 후, 실제 입력 필드 찾기
        field_departure_airport = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@role = "combobox" and contains(@aria-label, "출발지")]')))
        field_departure_airport.click()
        input_departure_airport = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@role = "combobox"  and contains(@aria-label, "출발지가 있나요?")]')))
        input_departure_airport.send_keys(departure_airport_code) # 인천공항 (ICN) 입력
        time.sleep(1)
        input_departure_airport.send_keys(Keys.ENTER) # 엔터 눌러서 선택
        print(f" 출발지 '{departure_airport_code}' 입력 완료.")

# 3. 목적지 입력
## 클릭하여 활성화 후, 실제 입력 필드 찾기
        field_arrival_airport = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@role = "combobox" and contains(@aria-label,"목적지")]')))
        field_arrival_airport.click()
        #input_arrival_airport = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@role = "combobox" and contains(@aria-label, "목적지가 어디인가요?")]')))
        input_arrival_airport = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="i23"]/div[6]/div[2]/div[2]/div[1]/div/input')))
        input_arrival_airport.send_keys(arrival_airport_code) # 목적지 코드 입력
        time.sleep(1)
        input_arrival_airport.send_keys(Keys.ENTER) # 엔터 눌러서 선택
        print(f"  [공통] 목적지 '{arrival_airport_code}' 입력 완료.")
        time.sleep(1) # 목적지 선택 후 다음 UI 로드 대기

        return True

    except Exception as e:
        print(f"  [공통] 기본 설정 오류: {e}")
        # driver.save_screenshot(f"error_common_setup_{arrival_airport_code}.png")
        return False

########################################

def return_to_initial_page (target_date, arrival_airport_code):
    """
    문제가 발생했을 때 초기화면으로 돌아가고 날짜와 목적지를 재설정
    """
    print("^^^^^^ 초기화면으로 돌아갑니다 (재시도) ^^^^^^")
    
    try:
        enter_GoogleFlight(arrival_airport_code)
        
        click_date_on_calendar(target_date)
        
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[@aria-label = '검색']")))
        search_button.click()
        print("^^^^^^ 검색을 다시 시작합니다 ^^^^^^")
        return True
    
    except Exception as e:
        print(f"!!! 복구 실패: {e}")
        return False

########################################

def parse_date(date_text):
    """
    'YYYY-MM-DD' 형식의 문자열에서 날짜 객체 반환.
    """
    try:
        return datetime.datetime.strptime(date_text, "%Y-%m-%d").date()
    except Exception as e:
        print(f"  ISO 날짜 파싱 오류: {e}, 텍스트: '{date_text}'")
        return None
    
########################################

def convert_time_to_minutes(time_str):
    """
    "X시간 Y분" 형태의 비행 시간을 총 분(int)으로 변환합니다.
    "X시간" 또는 "Y분"만 있는 경우도 처리합니다.
    """
    if not time_str:
        return None

    total_minutes = 0
    match = re.search(r'(\d+)시간(?:\s*(\d+)분)?', time_str)
    if match:
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        total_minutes = (hours * 60) + minutes
        return total_minutes
    
    match_minutes_only = re.search(r'(\d+)분', time_str)
    if match_minutes_only:
        total_minutes = int(match_minutes_only.group(1))
        return total_minutes
        
    return None

########################################

def convert_to_24hr(ampm, time_str):
    """
    '오전/오후 HH:MM'를 'HH:MM'(24-hour)로 변환합니다.
    """
    hour, minute = map(int, time_str.split(':'))
    if ampm == '오후' and hour != 12:
        hour += 12
    elif ampm == '오전' and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"

########################################

def click_date_on_calendar(date_str):
    """달력에서 YYYY-MM-DD 형식의 날짜를 클릭합니다"""
    try:
# 1. 달력 버튼 클릭
        calendar_field = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@aria-label = "출발"]')))
        calendar_field.click()
        time.sleep(3)

        # 최대 N개월 탐색 (무한 루프 방지)
        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
# 2. 현재 달력에 해당 날짜가 있는지 확인
            try:
                date_element = driver.find_element(By.XPATH, f'//div[@data-iso = "{date_str}"]')
                date_element.click()
                print(f"날짜 {date_str}를 선택했습니다.")
                break
# 3. 현재 달력에 해당 날짜를 찾지 못하면 다음 달로 이동
            except NoSuchElementException:
                print(f"--- 날짜 '{date_str}'를 현재 달력에서 찾을 수 없습니다. 다음 달로 이동합니다. ---")
                
                try:
                    calendar_flip_button = wait.until(EC.element_to_be_clickable((By.XPATH,  '//button[@aria-label = "다음"]')))
                    calendar_flip_button.click()
                    print("@@@ 다음 달력 페이지로 이동 완료 @@@")
                    attempts += 1
                    time.sleep(3)
                except:
                    print("--- 다음 달 버튼을 찾을 수 없습니다. 달력 끝에 도달했거나 XPath가 잘못되었습니다. ---")
                    break

# 4. 날짜 선택 후 [확인] 버튼 클릭 
        confirm_button = wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@aria-label, '확인.')]")))
        confirm_button.click()
        print("@@@ '확인' 버튼 클릭 완료 @@@")
        
    except Exception as e:
        print(f"!!!   날짜 '{date_str}' 달력 선택 오류: {e}   !!!")
        #driver.save_screenshot(f"error_calendar_select_{date_str}.png")
        return False

########################################

def extract_flight_info(flight_item, departure_date_str, arrival_airport_code):
    """개별 항공편 아이템에서 정보 추출 (항공사, 시간, 가격 등)"""
    current_search_date = datetime.date.today().strftime("%Y-%m-%d")
    try:
        flight_data = {}
        flight_data["검색일"] = current_search_date
        flight_data["출발공항"] = departure_airport_code
        flight_data["도착공항"] = arrival_airport_code
        try:
            flight_text = driver.find_element(By.XPATH, '//div[@role = "link" and @class = "JMc5Xc"]').get_attribute('aria-label').strip()

# 항공사 이름 &  경유여부
            airline_match = re.search(r'([가-힣A-Za-z\s]+?)의\s*(?:직항|(\d+)회\s*경유)?\s*항공편입니다', flight_text)
            if airline_match:
                airline_name = airline_match.group(1).strip()
                stop_count = airline_match.group(2)
                stopover = "직항" if stop_count is None else f"{stop_count}회 경유"
                flight_data["항공사명"] = airline_name
                flight_data["경유여부"] = stopover
            else:
                flight_data['항공사명'] = 'N/A'
                flight_data["경유여부"] = "N/A"

# 출발/도착 시간
            time_date_match = re.search(r'\. (월요일|화요일|수요일|목요일|금요일|토요일|일요일),\s*(\d{1,2}월\s*\d{1,2})\s*(오전|오후)\s*(\d{1,2}:\d{2})에.*?출발하여 (.*?),\s*(\d{1,2}월\s*\d{1,2})?\s*(오전|오후)\s*(\d{1,2}:\d{2})에',flight_text)
            if time_date_match:
                flight_data['출발요일'] = time_date_match.group(1).strip()
                flight_data['출발일'] = departure_date_str
                flight_data['출발시간_원문'] = f"{time_date_match.group(3)} {time_date_match.group(4)}"
                flight_data['출발시간_24시'] = convert_to_24hr(time_date_match.group(3), time_date_match.group(4))
                flight_data['도착요일'] = time_date_match.group(5).strip()
                flight_data['도착일'] = time_date_match.group(6)
                flight_data['도착시간_원문'] = f"{time_date_match.group(7)} {time_date_match.group(8)}"
                flight_data['도착시간_24시'] = convert_to_24hr(time_date_match.group(7), time_date_match.group(8))

                arr_month_day = time_date_match.group(6).split('월')
                arr_month = int(arr_month_day[0])
                arr_day = int(arr_month_day[1])
                
                # 날짜 변경 처리
                # 출발일의 월이 도착일의 월보다 크다면 연도를 바꾼다
                try:
                    dep_year = int(departure_date_str.split('-')[0])
                    dep_month = int(departure_date_str.split('-')[1])
                    if arr_month < dep_month:
                        flight_data['도착일'] = f"{dep_year + 1}-{arr_month}-{arr_day}"
                    else:
                        flight_data['도착일'] = f"{dep_year}-{arr_month}-{arr_day}"
                except ValueError:
                # 월 파싱 실패 시 기본 연도 유지
                    flight_data["도착일"] = "N/A"
                    print("Error: [도착일] 저장 실패")

            else:
                print("$$$ 시간 및 날짜 정보 추출 오류 $$$")
                flight_data['출발요일'] =  "N/A"
                flight_data['출발시간_원문'] =  "N/A"
                flight_data['출발시간_24시'] =  "N/A"
                flight_data['도착요일'] =  "N/A"
                flight_data['도착시간_원문'] =  "N/A"
                flight_data['도착시간_24시'] =  "N/A"
                flight_data['도착일'] = "N/A"

# 비행시간
            flight_time_match = re.search(r'총 비행 시간은 (\d+시간(?:\s*\d+분)?)',flight_text)
            if flight_time_match:
                flight_time_str = flight_time_match.group(1)
                if flight_time_str:
                    flight_time= convert_time_to_minutes(flight_time_str)
                else:
                    print("!!!   비행시간 단위 변환 실패   !!!")
                    flight_time = "N/A"
            else:
                print("!!!   비행시간을 찾지 못하였습니다   !!!")
                flight_time = "N/A"
            flight_data["비행시간_분"] = flight_time
# 가격
            price_match = re.search(r'최저가는\s+([\d,]+)\s+대한민국\s+원입니다', flight_text)
            if price_match:
                flight_data['가격'] = int(price_match.group(1).replace(',',''))
            else:
                flight_data['가격'] = "N/A"
        

            return flight_data
    
    
        except Exception as e:
            print(f"!!!   개별 항공편 정보 추출 오류: {e}   !!!")
            return None

    except:
        print("!!!   추출 함수 불러오기 실패   !!!")

########################################

def crawling_type_1_2(arrival_airport_code, region_name):
    """1-1. 현재 시점의 최저가가 되는 날짜와 해당 항공권 정보 수집"""
    """1-2. 현재 시점 출발일에 따른 항공권 가격 분포 수집 (달력 전체)"""
    print(f"\n  --- 1. 달력 데이터 수집 및 최저가 탐색 ({arrival_airport_code}) ---")
    current_search_date = datetime.date.today().strftime("%Y-%m-%d")
    

# 1. 달력 열기
    try:
        calendar_field = wait.until(EC.element_to_be_clickable((By.XPATH, '//input[@aria-label = "출발"]')))
        calendar_field.click()
        time.sleep(1)
    except Exception as e:
        print(f"    달력 열기 실패. 1-1 스킵: {e}")
        # driver.save_screenshot(f"error_1_1_calendar_open_{arrival_airport_code}.png")
        return

    # 최저가 추적 변수
    min_price_item_list = None #{"price": int, "date": date, "element": element}
    min_price = float('inf')

    
    # 달력 전환 횟수
    calendar_flipper = 0
    MAX_FLIP_ATTEMPTS = 10
    
    # 이미 처리된 날짜를 추적하기 위한 집합 (set)
    processed_date = set()


#================= <1-2> =================
# 2. 셀 정보 로드
    while calendar_flipper < MAX_FLIP_ATTEMPTS:
        try:
# 모든 활성 날짜 셀 (가격이 있는) 찾기
            time.sleep(3)
            wait.until(EC.presence_of_all_elements_located((By.XPATH, '//div[@role="gridcell"]')))
            all_cells = wait.until(EC.presence_of_all_elements_located((By.XPATH, '//div[@role="gridcell"]')))
            #all_cells = driver.find_elements(By.XPATH, '//div[@role = "gridcell"]')
        
            if not all_cells:
                print("$$$ 캘린더 날짜 셀을 찾을 수 없습니다.")
                break
        
            print(f"총 {len(all_cells)}개의 캘린더 셀을 찾았습니다.")
            #time.sleep(1)
        
            for cell in all_cells:
                cell_price = None
                cell_date_str = None #YYYY-MM-DD 형식 문자열
                try:
# 2-1. 셀의 날짜 정보 로드
                    cell_date_str = cell.get_attribute('data-iso')
                    print(cell_date_str)
                    if not cell_date_str:
                        continue
                    if cell_date_str in processed_date:
                        continue
# 2-2. 셀의 가격 정보 로드(자식노드)
                    price_element = cell.find_element(By.XPATH,'.//div[contains(@aria-label, "대한민국 원")]')
                    print(price_element)
                    #time.sleep(1)

                    if price_element:
                        cell_price_text = price_element.text.strip()
                        cell_aria_label = price_element.get_attribute("aria-label")

                        cell_price = float(re.search(r'₩([\d.]+)',cell_price_text).group(1))
                        cell_price_detail = int(re.sub(r'[^\d]','',cell_aria_label))

# 2-3. 날짜 요일 로드 (1-2 데이터용)
                    dow_element = driver.find_element(By.XPATH, '//div[contains(@aria-label,"요일")]')
                    if dow_element:
                        date_aria_label = dow_element.get_attribute('aria-label')
                        dow_match = re.search(r'(월요일|화요일|수요일|목요일|금요일|토요일|일요일)', date_aria_label)
                        if dow_match:
                            dow = dow_match.group(1)
                        else:
                            dow = "N/A"
# 2-4. [1-2 데이터(가격분포)] 저장
                    if (cell_date_str is not None) and (cell_price is not None):
                        data_1_2.append({
                            "검색일": current_search_date,
                            "목적지": arrival_airport_code,
                            "대륙/지역": region_name,
                            "출발일": cell_date_str,
                            "출발요일": dow,
                            "가격": cell_price_detail,
                            "가격 요약": cell_price,
                            "데이터 유형": "1-2",
                            })
                        processed_date.add(cell_date_str)# 성공적으로 처리된 날짜만 추가
# 3. <1-1>을 위한 준비
# 3-1. 최저가 식별 및 업데이트
                    if cell_price is not None:
                        if round(cell_price,1) < min_price:
                            min_price = round(cell_price,1)
                            min_price_item_list = [{
                            "가격": cell_price,
                            "출발일": cell_date_str,
                            "비고": cell # 나중에 해당 요소 찾을 때 사용
                            }]
                            print(f"      [최저가 업데이트] 날짜: {cell_date_str}, 가격: {cell_price}")
                        elif round(cell_price,1) == min_price:
                            min_price_item_list.append({
                                "가격": cell_price,
                                "출발일": cell_date_str,
                                "비고": cell
                            })
                            print(f"      [동일 최저가 추가] 날짜: {cell_date_str}, 가격: {cell_price}")
                        
                except Exception as e:
                    # 개별 셀 처리 중 오류 발생 (예: 가격/날짜 요소가 없거나 파싱 실패)
                    print(f"    개별 셀 처리 중 오류 발생: {e}")
                    # pass # 오류 메시지 출력 없이 건너뜁니다.
            
            calendar_flipper += 1 # 현재 달력 탐색 완료
            
            
# 3-2. 다음 달로 이동
            try:
## 다음 달 버튼 누르기
                calendar_flip_button = wait.until(EC.element_to_be_clickable((By.XPATH,  '//button[@aria-label = "다음"]')))
                calendar_flip_button.click()
                time.sleep(1)
                print(f"@@@ 다음 달력 페이지로 이동 완료. 총 달력 넘긴 횟수: {calendar_flipper}/{MAX_FLIP_ATTEMPTS} @@@")
            except:
                print("!!!   달력을 넘기는 버튼을 찾을 수 없습니다   !!!")
                break # 월 탐색 루프 종료
                
        except Exception as month_e:
            print(f"!!!   <1-1> 달력 탐색 중 오류발생: {month_e}   !!!")
            break
            
    print(f"\n######## <1-2> 달력 데이터 수집 완료. 총 {len(data_1_2)}개의 가격 분포 데이터 수집. ########")
    return min_price_item_list
    
#================= <1-1> =================

def crawling_type_1_1(arrival_airport_code, min_price_item, region_name):
    print(f"\n--- 1-1. 최저가 출발일 항공권 탐색 ({arrival_airport_code}) ---")

# 공통 과정 재실행 (페이지 초기화 및 출발/목적지 설정)
    if not enter_GoogleFlight(arrival_airport_code):
        print("$$$    <1-1> 화면 초기화 실패.")
        return
# <1-2> 정보 가져오기
    if not min_price_item:
        print("$$$     <1-1> 최저가 정보 로드 실패.")
        return

    previous_item_num = len(data_1_1)


# 2. 최저가 셀 클릭
    if len(min_price_item)> 1:
        print(f"   최저가가 출발일이 총 '{len(min_price_item)}'개 있습니다.")
#    error_1_1 = []
    
    first_iteration_done = False
    
    
    for p in min_price_item:
        print(f"  >>> 최저가 출발일: {p['출발일']} (가격: {p['가격']}만원) <<<")
        
        target_date = str(p["출발일"])
        #target_element = p["비고"]
        
        click_date_on_calendar(target_date)
        # 첫 번째 루프에서만 '검색' 버튼을 누르고, 이후부터는 '확인' 버튼까지만 누른다.
        if not first_iteration_done:
            try:
                search_button =  wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[@aria-label = '검색']")))
                search_button.click()
                print("@@@ '검색' 버튼 클릭 완료 @@@")
                first_iteration_done = True
            except:
                print("!!!   '검색' 버튼 클릭 오류   !!!")
                continue
            
        print("@@@ 해당하는 옵션의 항공권 목록을 가져오고 있습니다.")
        #time.sleep(1)
        
        # 첫번째 항공권 박스만 가져오기        
        target_flight_item = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role = "link" and contains(@aria-label,"최저가는")]')))
        flight_info = extract_flight_info(target_flight_item, target_date, arrival_airport_code) #{"flight_item": target_flight_item, "departure_date_str": target_date, "arrival_airport_code": arrival_airport_code}
        flight_info["데이터 유형"] = "1-1"
        flight_info["대륙/지역"] = region_name
        
        data_1_1.append(flight_info)
        
        
        present_item_num = len(data_1_1)
        
    print(f"\n######## <1-1> 최저가 날짜의 항공권 데이터 수집 완료. 총 {present_item_num - previous_item_num}/{len(min_price_item)}개의 가격 분포 데이터 수집. ########")
        

#================= <2> =================

def crawling_type_2(arrival_airport_code, region_name):
    """2. 출발일마다 최적 구매일 및 가격 변동 내역 수집"""
    print(f"\n  --- 2. 가격 변동 내역 탐색 ({arrival_airport_code}) ---")
    
# 1. 검색 가능한 미래 출발일 리스트 생성
    today = TODAY
    future_departure_dates = []
    first_iteration_done = False
    
    for i in range(0, 270, 9): # 오늘부터 270일간 9일 간격으로
        future_departure_dates.append((today + timedelta(days=i)).strftime("%Y-%m-%d"))

    for dep_date_str in future_departure_dates:
        print(f"    >>> 출발일: {dep_date_str} 에 대한 가격 변동 내역 <<<")
        
# 2. 달력에서 출발일 선택
        click_date_on_calendar(dep_date_str)
        # 첫 번째 루프에서만 '검색' 버튼을 누르고, 이후부터는 '확인' 버튼까지만 누른다.
        if not first_iteration_done:
            try:
                search_button =  wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[@aria-label = '검색']")))
                search_button.click()
                print("@@@ '검색' 버튼 클릭 완료 @@@")
                first_iteration_done = True
            except:
                print("!!!   '검색' 버튼 클릭 오류   !!!")
                continue

        
#================= 2-1, 2-2, 2-3 통합: [가격 변동 내역 보기] =================
        try:
            # 1. 페이지 하단으로 스크롤 (팝업이 나타나게 하기 위함)
            driver.execute_script("window.scrollBy(0,450);")
            time.sleep(1)
        
            # 2. 팝업 닫기 시도
            try:
                popup_button = WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CLASS_NAME, 'I0Kcef')))
                driver.execute_script("arguments[0].click();", popup_button)
                print("@@@   팝업 닫기 완료   @@@")
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@role='button' and contains(@aria-label,'닫기')]")))
            except:
                print("--- 팝업이 없거나 닫기 실패 (JavaScript 시도). 다음 단계로 진행합니다 ---")

            # 3. 드롭다운 버튼 위치로 스크롤
            dropdown_button_xpath = '//button[@aria-label="가격 변동 내역 보기"]'
            try:
                price_history_button = wait.until(EC.visibility_of_element_located((By.XPATH, dropdown_button_xpath)))
                driver.execute_script("arguments[0].scrollIntoView(true);", price_history_button)
                driver.execute_script("window.scrollBy(0, -100)")  # 여유 공간 확보
                #time.sleep(1)

                # 4. 드롭다운 버튼 클릭
                dropdown_button =wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_button_xpath)))
                actions.move_to_element(dropdown_button).click().perform()
                print("@@@   드롭다운 버튼 클릭 완료   @@@")
                #time.sleep(1)
            
# 로딩이 느려 요소를 발견하지 못한 예외 처리
            except TimeoutException:
                print(f"!!! 가격 변동 내역 보기 버튼을 찾을 수 없습니다. {dep_date_str} 재시도 !!!")
                if not return_to_initial_page(dep_date_str, arrival_airport_code):
                    print("!!! 복구 실패 → 해당 출발일을 건너뜁니다 !!!")
                    continue
                else:
                    print("@@@ 항공권을 재검색합니다. 드롭 다운 버튼을 다시 클릭합니다 @@@")
                    driver.execute_script("window.scrollBy(0,450);")
                    time.sleep(3)
                    try:
                        popup_button = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, 'I0Kcef')))
                        driver.execute_script("arguments[0].click();", popup_button)
                        print("@@@   팝업 닫기 완료   @@@")
                        wait.until(EC.invisibility_of_element_located((By.XPATH, "//div[@role='button' and contains(@aria-label,'닫기')]")))
                    except:
                        print("--- 팝업이 없거나 닫기 실패 (JavaScript 시도). 다음 단계로 진행합니다 ---")

                    # 드롭다운 버튼 위치로 스크롤
                    dropdown_button_xpath = '//button[@aria-label="가격 변동 내역 보기"]'
                    try:
                        price_history_button = wait.until(EC.visibility_of_element_located((By.XPATH, dropdown_button_xpath)))
                        driver.execute_script("arguments[0].scrollIntoView(true);", price_history_button)
                        driver.execute_script("window.scrollBy(0, -100)")  # 여유 공간 확보
                        #time.sleep(1)

                        # 드롭다운 버튼 클릭
                        dropdown_button =wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_button_xpath)))
                        actions.move_to_element(dropdown_button).click().perform()
                        print("@@@   드롭다운 버튼 클릭 완료   @@@")
                    except Exception as e:
                        print(f"!!! 재시도 실패: {e} !!!")
                        continue
            
            except Exception as e:
                print(f"!!! 가격 변동 내역 보기 버튼 클릭 오류: {e}. {dep_date_str} 스킵 !!!")
                # driver.save_screenshot(f"error_2_price_history_button_error_{dep_date_str}.png")
                continue 

#================= <2-3> =================
            try:
# 1. '유사한 ...행의 최저가 항공편은 대개 [범위] 사이입니다' 문구 정보 가져오기
                price_range_info_elem = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '유사한')]")))
                price_range_text = price_range_info_elem.text.strip()
                range_match = re.search(r'대개 (.*?)\s*사이입니다', price_range_text)
                price_range_str = range_match.group(1).strip() if range_match else "N/A"
# 2. 일반적인 항공권 가격 범위 가져오기
                print(price_range_str)
                lower_bound = "N/A"
                upper_bound = "N/A"
                
                if price_range_str != "N/A":
                    bound_match = re.search(r'₩([\d,]+)~([\d,]+)', price_range_str)
                
                    if bound_match:
                        lower_str = bound_match.group(1).replace('₩','').replace(',','')
                        upper_str = bound_match.group(2).replace(',','')
  
                    try:
                        lower_bound = int(lower_str)
                        upper_bound = int(upper_str)
                    except ValueError:
                        pass
                    
# 3. [2-1 데이터(항공권의 일반 범위)] 저장 **********************
                data_2_3.append({
                    "검색일": datetime.date.today().strftime("%Y-%m-%d"),
                    "출발일": dep_date_str,
                    "목적지": arrival_airport_code,
                    "데이터 유형": "2-3",
                    "가격 범위 텍스트": price_range_str,
                    "가격 범위 하한": lower_bound,
                    "가격 범위 상한": upper_bound,
                    "대륙/지역": region_name
                })
                print("######## [2-3] 가격 변동 일반 범위 수집 완료 ########")
            except Exception as error_2_3:
                print(f"!!!   [2-3] 최저가 예상 범위 문구 수집 오류: {error_2_3}   !!!")
                
                
#================= 2-1 & 2-2. 가격 변동 그래프 데이터 수집 =================
# 4-1. 그래프 찾기
            try:
                points = None
                graph_element = driver.find_elements(By.XPATH, '//div[@aria-label = "가격 변동 그래프"]')
                if not graph_element:
                    print("!!!   그래프 요소를 찾을 수 없습니다   !!!")
                    pass
# 4-2. 그래프에서 각 포인트 객체 리스트 추출
                points = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'pKrx3d-JNdkSc')),message="!!!   그래프에서 포인트 요소를 찾을 수 없습니다   !!!")
    
                if not points:
                    print("!!!   그래프에서 툴팁 정보를 가진 포인트 요소를 찾을 수 없습니다   !!!")
                else:
                    print(f"@@@   총 {len(points)}개의 툴팁 정보를 가진 포인트 요소를 발견했습니다   @@@")                
                
# 4-3. 객체 리스트에서 정보 추출
                points_aria_label = []
                points_parsed = []


## for 루프를 사용하여 각 WebElement 객체에 접근하고 정보를 추출
                
                for i, point in enumerate(points):
                    try:
## WebElement 객체에서 'aria-label' 속성 값(문자열)을 로드
                        print(point)
                        actions.move_to_element(point).perform()
                        child_with_label = point.find_element(By.XPATH, './/*[@aria-label]')
                        aria_label_text = child_with_label.get_attribute('aria-label')

                        print(aria_label_text)
                        if aria_label_text:
                            points_aria_label.append(aria_label_text) # 원본 aria-label 문자열 저장
                            
## 가져온 문자열에서 날짜와 가격을 정규표현식으로 파싱
                            days_ago_match = re.search(r'(\d+)\s*?일 전', aria_label_text) # '며칠 전' 정보
                            price_match = re.search(r'₩([\d,]+)', aria_label_text)
                        
                            # 날짜 정보 파싱
                            if days_ago_match:
                                days_ago_point = int(days_ago_match.group(1))
                            else:
                                print(f"!!!   (며칠 전) 파싱 실패(1): {aria_label_text}   !!!")
                        
                            # 가격정보 파싱
                            if price_match:
                                price_point = int(price_match.group(1).replace(',', ''))
                            else:
                                print(f"!!!   (며칠 전) 파싱 실패(2): {aria_label_text}   !!!")
# 5. 구매 날짜 계산
                            purchase_date_obj = TODAY - timedelta(days=days_ago_point)
                            if not purchase_date_obj:
                                print("!!!   그래프로부터 구매일을 계산하지 못했습니다   !!!")
            
# 6. 날짜별 가격 변동 데이터 수집
                            points_parsed.append({
                                "검색일": TODAY.strftime("%Y-%m-%d"),
                                "출발일": dep_date_str,
                                "목적지": arrival_airport_code,
                                "대륙/지역": region_name,
                                "구매일": purchase_date_obj.strftime("%Y-%m-%d"),
                                "가격": price_point,
                                "검색일로부터 며칠 전": days_ago_point,
                                "데이터 유형": "2-2"
                                })
                        else:
                            print(f"!!!   {i+1}번째 요소에 'aria-label' 정보를 확인할 수 없습니다   !!!")
                        
                    
                    except Exception as e:
                        print(f"!!!   그래프 포인트 {i+1}번째 요소 처리 중에 오류 발생: {e}   !!!")
                        # 개별 요소 처리 중 오류가 발생하더라도 다른 요소 처리는 계속 진행
                driver.execute_script('window.scrollTo(0,0)')
                    
#================= <2-2> =================
# 7. [2-2 데이터(과거 시점 출발일에 따른 항공권 가격 분포)] 저장 **********************
                if points_parsed:
                # 같은 출발일에 대한 2-2 데이터는 하나의 레코드로 묶거나, 별도로 처리
                # 여기서는 모든 상세 데이터를 한 리스트에 추가 (각각의 데이터 포인트)
                    data_2_2.extend(points_parsed)
                    print(f"######## [2-2] {len(points_parsed)}개의 가격 변동 상세 데이터 수집 완료 ########")
                else:
                    print("!!!   [2-2] 가격 변동 상세 데이터를 찾을 수 없습니다   !!!")


#================= <2-1> =================
# 8-1. 최소 가격 지점 확인
                # 그래프에서 가격이 최소가 되는 정보를 담을 딕셔너리
                min_price_point_data = None
                if points_parsed:
                    min_price_point = min(points_parsed, key=lambda x: x['가격'])
# 8-2. 최소 가격 지점 정보 추출
                    min_price_point_data = {
                        "검색일": TODAY.strftime("%Y-%m-%d"), # 현재 검색일
                        "출발일": dep_date_str,              # 현재 출발일
                        "목적지": arrival_airport_code,
                        "대륙/지역": region_name,
                        "구매일": min_price_point['구매일'], # 최저가 날짜
                        "최소가격": min_price_point['가격'],
                        "검색일로부터 며칠 전": min_price_point['검색일로부터 며칠 전'],
                        "데이터 유형": "2-1 가격최소구매일", # 2-1 데이터 유형 명시
                        }
                    print("######## [2-1] 최소 가격 구매일 정보 수집 완료 ########")
                else:
                    print("!!!   [2-1] 그래프에서 최소 가격 지점을 찾을 수 없습니다   !!!")
# 8-3. [2-1 데이터(출발일별 최적 구매일)]  저장 **********************
                if min_price_point_data:
                    data_2_1.append(min_price_point_data)
                    
            except Exception as e:
                print(f"!!!   그래프를 찾을 수 없습니다(오류: {e})   !!!")
            
        except Exception as e:
            print(f"!!!   가격 변동 그래프 버튼을 찾을 수 없습니다(오류: {e})   !!!")
            #driver.save_screenshot(f"error_2_price_history_{dep_date_str}.png")


# 유틸리티 함수 추가
def create_table_if_not_exists(cursor, table_name, columns_with_types, unique_constraints=None):
    """
    테이블이 없으면 생성.
    columns_with_types: {'컬럼명': '데이터타입', ...}
    unique_constraints: {'제약조건명': ('컬럼1', '컬럼2', ...), ...} 또는 리스트 [('컬럼1', '컬럼2'), ...]
    """
    
    cols_str = [f'"{col}" {typ}' for col, typ in columns_with_types.items()]
    
    # UNIQUE 제약 조건 추가
    if unique_constraints:
        for constraint_cols in unique_constraints: # unique_constraints는 튜플의 리스트로 가정
            cols_str.append(f"UNIQUE ({', '.join(f'\"{c}\"' for c in constraint_cols)})")

    create_sql = f'''
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(cols_str)}
    )
    '''
    cursor.execute(create_sql)

def save_data_to_db(data_list, table_name, conn):
    """
    데이터를 데이터베이스에 저장.
    unique_subset_cols: 중복을 판단할 컬럼들의 리스트. 이 컬럼들을 기준으로 중복 제거 후 저장.
                    None이면 DataFrame 내의 모든 컬럼을 기준으로 중복 제거.
                    빈 리스트([])이면 중복 제거를 하지 않고 모두 append.
    """
    if not data_list:
        print(f"[스킵] '{table_name}' 저장할 데이터 없음.")
        return
    df = pd.DataFrame(data_list)
    # '저장시간' 컬럼 추가 (DataFrame에서 처리)
    df["저장시간"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 컬럼 이름과 플레이스홀더 준비
    columns = df.columns.tolist()
    placeholders = ', '.join(['?' for _ in columns])
    columns_str = ', '.join([f'"{col}"' for col in columns]) # 컬럼명에 따옴표 추가

    # INSERT OR IGNORE 문 사용 (DB에 UNIQUE 제약 조건이 있어야 작동)
    insert_sql = f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    cursor = conn.cursor()
    saved_count = 0
    skipped_count = 0
    for index, row in df.iterrows():
        try:
            cursor.execute(insert_sql, row.values.tolist())
            # execute가 성공했다고 바로 inserted를 의미하는 것은 아니므로, 실제로 삽입되었는지 확인하는 로직은 더 복잡해질 수 있음.
            # 여기서는 INSERT OR IGNORE의 동작을 신뢰.
            saved_count += 1
        except sqlite3.IntegrityError: # UNIQUE 제약 조건 위반 시 (INSERT OR IGNORE 사용 시 발생하지 않음)
            skipped_count += 1
        except Exception as e:
            print(f"Error inserting row: {row.values.tolist()} - {e}")
            skipped_count += 1
    conn.commit() # 변경사항 커밋
    print(f"[DB 저장 완료] {table_name} ({saved_count} rows saved, {skipped_count} rows skipped due to potential duplicates or errors)")


# --- 메인 실행 흐름 ---
if __name__ == "__main__":
    initialize_driver()
    
    conn_db = sqlite3.connect(DB_NAME)
    cursor = conn_db.cursor()
    # 테이블 생성
    create_table_if_not_exists(cursor, "data_1_1_table", {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "검색일": "TEXT", "출발공항": "TEXT", "도착공항": "TEXT", "항공사명": "TEXT",
        "출발요일": "TEXT", "출발일": "TEXT", "출발시간_원문": "TEXT", "출발시간_24시": "TEXT",
        "도착요일": "TEXT", "도착일": "TEXT", "도착시간_원문": "TEXT", "도착시간_24시": "TEXT",
        "비행시간_분": "INTEGER", "가격": "INTEGER", "경유여부": "TEXT",
        "데이터 유형": "TEXT", "대륙/지역": "TEXT","저장시간": "TEXT"
    })

    create_table_if_not_exists(cursor, "data_1_2_table", {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "검색일": "TEXT", "목적지": "TEXT", "대륙/지역": "TEXT",
        "출발일": "TEXT", "출발요일": "TEXT", "가격": "INTEGER",
        "가격 요약": "REAL", "데이터 유형": "TEXT","저장시간": "TEXT"
    })

    create_table_if_not_exists(cursor, "data_2_1_table", {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "검색일": "TEXT", "출발일": "TEXT", "목적지": "TEXT", "대륙/지역": "TEXT",
        "구매일": "TEXT", "최소가격": "INTEGER", "검색일로부터 며칠 전": "INTEGER",
        "데이터 유형": "TEXT","저장시간": "TEXT"
    })

    create_table_if_not_exists(cursor, "data_2_2_table", {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "검색일": "TEXT", "출발일": "TEXT", "목적지": "TEXT", "대륙/지역": "TEXT",
        "구매일": "TEXT", "가격": "INTEGER", "검색일로부터 며칠 전": "INTEGER",
        "데이터 유형": "TEXT","저장시간": "TEXT"
    })

    create_table_if_not_exists(cursor, "data_2_3_table", {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "검색일": "TEXT", "출발일": "TEXT", "목적지": "TEXT", "데이터 유형": "TEXT",
        "가격 범위 텍스트": "TEXT", "가격 범위 하한": "INTEGER", "가격 범위 상한": "INTEGER",
        "대륙/지역": "TEXT","저장시간": "TEXT"
    })
    
    conn_db.commit()

    for group, airports in arrival_airports.items():
        print(f"\n===== 그룹: {group} 크롤링 시작 =====")


        for airport_code in airports:
            print(f"\n>>>> 목적지: {airport_code} 크롤링 시작 <<<<")
            
            # 1-2. 현재 시점 출발일에 따른 항공권 가격 분포 수집
            enter_GoogleFlight(airport_code)
            min_price_item = crawling_type_1_2(airport_code, group)
            driver.back()
            time.sleep(1) # 다음 작업 전 대기
            
            # 1-1. 현재 시점 최저가 출발일 항공권 정보 수집
            # 공통 과정 재실행 (페이지 초기화 및 출발/목적지 설정)
            target_date = None # 최저가 날짜 (YYYY-MM-DD 형식 문자열)
            crawling_type_1_1(airport_code, min_price_item,group)
            time.sleep(1) # 다음 작업 전 대기
            
            # 2. 출발일마다 최적 구매일 및 가격 변동 내역 수집
            enter_GoogleFlight(airport_code)
            crawling_type_2(airport_code, group)
            
            print(f">>>> 목적지: {airport_code} 크롤링 완료 <<<<\n")
            time.sleep(7) # 각 목적지별 충분한 대기 시간 
            
            print(f"===== 그룹: {group} 크롤링 완료 - 저장 시작 =====")
            # CSV + DB 저장 루프
            for data_list, table_name, file_name in [
                    (data_1_1, "data_1_1_table", "GoogleFlights_1_1.csv"),
                    (data_1_2, "data_1_2_table", "GoogleFlights_1_2.csv"),
                    (data_2_1, "data_2_1_table", "GoogleFlights_2_1.csv"),
                    (data_2_2, "data_2_2_table", "GoogleFlights_2_2.csv"),
                    (data_2_3, "data_2_3_table", "GoogleFlights_2_3.csv")]:
                if data_list:
                    df = pd.DataFrame(data_list)
                    df["저장시간"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # CSV 저장
                    df.to_csv(file_name, index=False, mode = 'a', header = not os.path.exists(file_name), encoding='utf-8-sig')
                    print(f"[{group}] CSV 저장 완료 -> {file_name} ({len(df)} rows)")
                    # DB 저장
                    save_data_to_db(data_list, table_name, conn_db)
                    print(f"[{group}] DB 저장 완료 -> {file_name} ({len(df)} rows)")
                else:
                    print(f"[{group}] {table_name} 저장할 데이터 없음")

    conn_db.close()
    if driver:
        driver.quit()
        print("WebDriver 종료.")
        
    print("=== 모든 데이터가 데이터베이스에 저장되었습니다 ===")
    