import streamlit as st 
import folium
from streamlit_folium import st_folium
import sys, os
import requests
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from ml_python.train import TrainModel

import pandas as pd
# 주소 정보 받아오기
from naver_api import naver_map_api as na

from dabang_web_scrap import getDabangList
from zigbang import ZigbangAPI, ZigbangDataProcessor

# [ '사이트', '시도', '자치구명', '법적동명', '세부 URL', '방식', '건물 형식', '보증금', '월세', '관리비', '전세금', '면적', '임대면적', '층수' ]

# 직방 df 받아오기
def getSaleList(lat: float, lon: float):
    all_dfs = []
    zigbang_types = ['villa', 'oneroom', 'officetel']

    for room in zigbang_types:
        api = ZigbangAPI(lat, lon, room_type=room, delta=0.005)
        item_ids = api.get_item_ids()
        details = api.get_item_details_v3(item_ids)
        # 보증금 값 통일
        for detail in details:
            if int(detail["보증금"]) >= 10000:
                eok = detail["보증금"] // 10000
                man = detail["보증금"] % 10000
                if man == 0:
                    result = f"{eok}억"
                else:
                    result = f"{eok}억{man}"
                detail["보증금"] = result
        # details를 DataFrame으로 변환 후 all_dfs에 추가
        df = pd.DataFrame(details)
        all_dfs.append(df)

    return all_dfs
            

def getDabangDataFrame(address):
    bang_type_list = ["원룸/투룸", "아파트", "주택빌라", "오피스텔"]
    dabang_list = []

    for bang_type in bang_type_list:
        try:
            bang_list = getDabangList(address, bang_type)
            if isinstance(bang_list, dict) and "errorMessage" in bang_list:
                print(f"오류 발생: {bang_list['errorMessage']}")
            elif bang_list:
                dabang_list.extend(bang_list)
        except Exception as e:
            print(f"다방 {bang_type} 오류 발생: {e}")

    return dabang_list
    

sample_data = [
    {"name": "장소 1", "lat": 37.5665, "lon": 126.9780, "detail": "장소 1의 상세 설명입니다."},
    {"name": "장소 2", "lat": 37.5651, "lon": 126.9895, "detail": "장소 2의 상세 설명입니다."},
    {"name": "장소 3", "lat": 37.5700, "lon": 126.9825, "detail": "장소 3의 상세 설명입니다."}
]

st.session_state.select_list = sample_data

def mainView():

    st.title("부동산 매물 검색기")

    if "search_clicked" not in st.session_state:
        st.session_state.search_clicked = False
    if "selected_place" not in st.session_state:
        st.session_state.selected_place = None

    address = st.text_input("주소를 입력하세요:")

    if st.button("검색"):
        st.session_state.search_clicked = True
        st.session_state.selected_place = None  # 검색하면 선택 초기화

    if st.session_state.search_clicked:
        ######################################
        # 주소 입력 시 위,경도 추출 함수 작성
        # with st.spinner("상세 정보를 불러오는 중입니다..."):
        #     ex) lat, lon = getCoordinate(address)
        ######################################
        
        with st.spinner("상세 정보를 불러오는 중입니다..."):
            # 좌표 데이터
            xy_data = na.mapXY(address)
            
            zigbang_list = getSaleList(float(xy_data["위도"]), float(xy_data["경도"]))
            dabang_list = getDabangDataFrame(address)

            # 직방 리스트를 DataFrame으로 변환
            zigbang_df = pd.concat(zigbang_list, ignore_index=True) if zigbang_list else pd.DataFrame()

            # 다방 리스트를 DataFrame으로 변환
            dabang_df = pd.DataFrame(dabang_list) if dabang_list else pd.DataFrame()
            if not dabang_df.empty:
                dabang_df.insert(0, "사이트", "다방")

            # 두 데이터프레임 합치기
            combined_df = pd.concat([zigbang_df, dabang_df], ignore_index=True)

            st.subheader("통합 매물 리스트")
            st.dataframe(combined_df)
        
        #debug
        lat, lon = 37.5665, 126.9780

        ######################################
        # 위,경도 얻을 시, 크롤링으로 부동산 매물 리스트 받아오는 함수 작성
        # with st.spinner("상세 정보를 불러오는 중입니다..."):
        #     ex) saleList = getSaleList(lat,lon)
        # sample_data를 리스트변수로 변경할것
        ######################################

        col1, col2 = st.columns([2, 1])

        with col1:
            m = folium.Map(location=[lat, lon], zoom_start=14)
            for item in sample_data:
                folium.Marker(
                    location=[item["lat"], item["lon"]],
                    popup=item["name"],
                    icon=folium.Icon(color='blue',icon='star')
                ).add_to(m)
            st_folium(m, width=700, height=500)

        with col2:
            st.subheader("장소 리스트")
            selected = st.radio(
                "항목을 선택하세요",
                [item["name"] for item in st.session_state.select_list]
            )
            
            ######################################
            # 장소 선택 시, 자치구,법정동,층,임대면적.보증금 정보가져오는 함수 작성
            #     ex) saleInfo = getSaleInfo(name)
            ######################################
            st.session_state.selected_place = selected #화면 나오기 전에 미리 데이터를 가져오고 state를 변경

        if "inference_cache" not in st.session_state: #folium 등으로 이벤트발생시 모델중복실행을 방지하기위해 캐시저장 dict선언
            st.session_state.inference_cache = {}

        if selected not in st.session_state.inference_cache: #radio변경때만 model실행
            with st.spinner("상세 정보를 불러오는 중입니다..."):
                res = requests.post("http://devtomato.synology.me:9904/api/model/getModelResult", json={
                    "J": "영등포구",
                    "B": "신도림동",
                    "Floor": 7,
                    "Area": 27.01,
                    "securityMoney": 1000
                })

                if res.ok:
                    result = res.json()["content"]
                st.session_state.inference_cache[selected] = result
                
        else:
            result = st.session_state.inference_cache[selected]

        selected = st.session_state.selected_place

        
        selected_detail = next(
            (item["detail"] for item in sample_data if item["name"] == st.session_state.selected_place), ""
        )
        st.markdown("---")
        st.markdown(f"예상 월 임대료:{result}만원 오차금액 +-20만원")
        st.subheader("상세 정보")
        st.write(selected_detail)


if __name__ == "__main__":
    mainView()