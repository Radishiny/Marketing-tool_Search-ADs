import streamlit as st
import pandas as pd
import google.generativeai as genai
import json
import io
import time
import requests
import base64
import hmac
import hashlib

st.set_page_config(page_title="Ad-Inverted AI Pro", layout="wide")

# ---------------------------------------------------------
# 사이드바 (API 키 설정)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ API 설정")
    gemini_api_key = st.text_input(
        "Google Gemini API Key 입력", 
        type="password", 
        help="https://aistudio.google.com/ 에서 발급받은 키를 입력하세요."
    )
    st.markdown("[👉 Gemini API 키 발급받기](https://aistudio.google.com/)")
    
    st.divider()
    
    st.subheader("🔑 네이버 검색광고 API (키워드/검색량 분석용)")
    naver_api_key = st.text_input("Access License (API Key)", type="password")
    naver_secret_key = st.text_input("Secret Key", type="password")
    naver_customer_id = st.text_input("Customer ID (숫자)")

st.title("🚀 경쟁사 소재 분석 및 소재 디벨롭 툴 (Kyeong's)")
st.caption("경쟁사 소재 데이터 분석(소구점·문장구조·SWOT) ➔ 효율 개선 전략 수립")

# ---------------------------------------------------------
# Session State 초기화 (경쟁사 소재)
# ---------------------------------------------------------
if "competitors" not in st.session_state:
    st.session_state.competitors = [
        {"brand": "", "title": "", "sub_title": "", "desc": "", "url": ""}
    ]

def add_competitor():
    st.session_state.competitors.append({"brand": "", "title": "", "sub_title": "", "desc": "", "url": ""})

def remove_competitor(index):
    if len(st.session_state.competitors) > 1:
        st.session_state.competitors.pop(index)

# ---------------------------------------------------------
# 화면 레이아웃 구성
# ---------------------------------------------------------
col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.subheader("1️⃣ 메인 키워드 및 경쟁사 소재")
    keyword = st.text_input("분석할 메인 검색어", value="책상")
    
    st.markdown("##### 🎯 경쟁사 광고 소재")
    
    for idx, comp in enumerate(st.session_state.competitors):
        with st.expander(f"📌 경쟁사 소재 #{idx + 1}", expanded=True):
            c_top1, c_top2 = st.columns([3, 1])
            with c_top1:
                comp["brand"] = st.text_input(f"경쟁사 브랜드명/업체명 #{idx + 1}", value=comp["brand"], key=f"brand_{idx}")
            with c_top2:
                if len(st.session_state.competitors) > 1:
                    st.button("🗑️ 삭제", key=f"del_{idx}", on_click=remove_competitor, args=(idx,))
            
            c1, c2 = st.columns(2)
            with c1:
                comp["title"] = st.text_input(f"광고 제목 #{idx + 1}", value=comp["title"], placeholder="예: [공식] 맞춤형 모션데스크", key=f"title_{idx}")
            with c2:
                comp["sub_title"] = st.text_input(f"추가 제목 (서브링크/확장) #{idx + 1}", value=comp["sub_title"], placeholder="예: 당일출고 / 5년 무상AS", key=f"sub_{idx}")
                
            comp["desc"] = st.text_area(f"광고 설명 #{idx + 1}", value=comp["desc"], placeholder="예: 튼튼한 E0 자재 사용, 높낮이 조절 책상, 지금 주문시 무료배송 혜택 제공", key=f"desc_{idx}", height=70)
            comp["url"] = st.text_input(f"랜딩페이지 URL #{idx + 1}", value=comp["url"], placeholder="예: https://example.com/desk", key=f"url_{idx}")

    st.button("➕ 경쟁사 소재 추가하기", on_click=add_competitor, use_container_width=True)

with col2:
    st.subheader("2️⃣ 광고주 정보 & 매체 설정")
    my_brand_name = st.text_input("브랜드명", value="", placeholder="공란으로 두거나 브랜드를 입력하세요")
    my_brand_url = st.text_input("랜딩페이지 URL", value="", placeholder="공란으로 두거나 URL을 입력하세요")
    
    must_include = st.text_input("강조할 키워드/소구점", value="당일출고, 5년 무상보증")
    tone = st.text_input("소재 톤앤매너", value="직관적/성능강조형/전문성")
    
    st.markdown("##### 📐 타겟 매체 설정")
    use_naver = st.checkbox("네이버 파워링크 (제목 15자 / 설명 45자)", value=True)
    use_google = st.checkbox("구글 검색광고 RSA (제목 30자 / 설명 90자)", value=True)

# ---------------------------------------------------------
# 네이버 검색광고 API 함수 (연관성 높은 키워드 정제 및 정렬)
# ---------------------------------------------------------
def generate_naver_signature(timestamp, method, uri, secret_key):
    message = f"{timestamp}.{method}.{uri}"
    byte_secret_key = bytes(secret_key, 'UTF-8')
    byte_message = bytes(message, 'UTF-8')
    return base64.b64encode(hmac.new(byte_secret_key, byte_message, hashlib.sha256).digest()).decode('utf-8')

def fetch_naver_keyword_data(search_keyword, api_key, secret_key, customer_id):
    base_url = "https://api.naver.com"
    uri = "/keywordstool"
    method = "GET"
    timestamp = str(int(time.time() * 1000))
    signature = generate_naver_signature(timestamp, method, uri, secret_key)
    
    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": api_key,
        "X-Customer": customer_id,
        "X-Signature": signature
    }
    params = {"hintKeywords": search_keyword, "showDetail": 1}
    try:
        response = requests.get(base_url + uri, headers=headers, params=params, timeout=7)
        if response.status_code == 200:
            data = response.json().get("keywordList", [])
            processed = []
            
            clean_keyword = search_keyword.replace(" ", "")
            
            for idx, item in enumerate(data):
                rel_kw = item.get("relKeyword", "")
                clean_rel_kw = rel_kw.replace(" ", "")
                
                is_relevant = (clean_keyword in clean_rel_kw) or (clean_rel_kw in clean_keyword) or (idx < 15)
                
                if not is_relevant:
                    continue

                pc_cnt = item.get("monthlyPcQcCnt", 0)
                mobile_cnt = item.get("monthlyMobileQcCnt", 0)
                
                pc_val = int(pc_cnt) if isinstance(pc_cnt, int) or str(pc_cnt).isdigit() else 5
                mobile_val = int(mobile_cnt) if isinstance(mobile_cnt, int) or str(mobile_cnt).isdigit() else 5
                total_cnt = pc_val + mobile_val
                
                processed.append({
                    "연관키워드": rel_kw,
                    "총 월간검색량": total_cnt,
                    "PC 검색량": pc_cnt,
                    "모바일 검색량": mobile_cnt,
                    "경쟁정도": item.get("compIdx")
                })
            
            processed.sort(key=lambda x: x["총 월간검색량"], reverse=True)
            return processed[:10]
    except Exception:
        pass
    return []

# ---------------------------------------------------------
# 실행 버튼 및 AI 분석 프로세스
# ---------------------------------------------------------
st.divider()

if st.button("🚀 경쟁사 심층 분석 및 AI 소재 기획 실행", use_container_width=True):
    if not gemini_api_key:
        st.error("좌측 사이드바에 Google Gemini API Key를 입력해주세요!")
    else:
        try:
            genai.configure(api_key=gemini_api_key)
            
            comp_list = []
            for idx, c in enumerate(st.session_state.competitors):
                if c["title"] or c["desc"] or c["brand"]:
                    comp_list.append({
                        "번호": idx + 1,
                        "경쟁사/브랜드명": c["brand"] if c["brand"] else f"경쟁사 {idx + 1}",
                        "광고 제목": c["title"],
                        "추가 제목": c["sub_title"],
                        "광고 설명": c["desc"],
                        "랜딩페이지 URL": c["url"]
                    })
            
            df_comp = pd.DataFrame(comp_list)
            
            st.subheader(f"📊 입력된 경쟁사 광고 소재 데이터 ({len(df_comp)}건)")
            if len(df_comp) > 0:
                st.dataframe(df_comp, use_container_width=True)
                
                csv_data = df_comp.to_csv(index=False, encoding='utf-8-sig')
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="📥 입력 경쟁사 소재 CSV 다운로드",
                        data=csv_data,
                        file_name=f"경쟁사_광고소재_{keyword}.csv",
                        mime="text/csv"
                    )
                with col_dl2:
                    try:
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df_comp.to_excel(writer, index=False, sheet_name='Competitor_Ads')
                        st.download_button(
                            label="📥 입력 경쟁사 소재 엑셀(.xlsx) 다운로드",
                            data=excel_buffer.getvalue(),
                            file_name=f"경쟁사_광고소재_{keyword}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception:
                        pass
            else:
                st.info("💡 입력된 경쟁사 소재가 없습니다. 업계 일반 패턴 분석 및 기획이 진행됩니다.")

            naver_data = []
            if naver_api_key and naver_secret_key and naver_customer_id:
                with st.spinner("네이버 검색광고 API에서 쿼리수 높은 연관키워드 수집 중..."):
                    naver_data = fetch_naver_keyword_data(keyword, naver_api_key, naver_secret_key, naver_customer_id)

            if naver_data:
                st.subheader("📈 네이버 공식 API - 핵심 연관키워드 TOP 10 (쿼리수 정렬)")
                st.dataframe(pd.DataFrame(naver_data), use_container_width=True)

            st.divider()

            with st.spinner("경쟁사 심층 분석(소구점·문장구조·SWOT) 및 소재를 기획 중입니다..."):
                prompt = f"""
[경고: 인사말, 자기소개, 인트로, 서론 문구는 절대 출력하지 마십시오.]
"반갑습니다", "안녕하세요", "10년 차 수석 마케터입니다" 같은 어떠한 인사나 인트로 문구도 쓰지 말고, 곧바로 '### 1️⃣ 경쟁사 심층 분석' 헤더부터 답변을 시작하십시오.

[타겟 검색 키워드]
{keyword}

[등록된 경쟁사 광고 소재 목록]
{df_comp.to_json(orient='records', force_ascii=False) if len(df_comp) > 0 else "데이터 없음"}

[네이버 공식 API 연관키워드 수치]
{json.dumps(naver_data, ensure_ascii=False) if naver_data else "데이터 없음"}

[브랜드 정보]
- 브랜드명: {my_brand_name if my_brand_name else "(브랜드명 미지정 - 범용/자사 맞춤형 적용)"}
- 브랜드 URL: {my_brand_url if my_brand_url else "(URL 미지정)"}

[광고주 필수 요청사항]
- 필수 강조 문구/소구점: {must_include}
- 톤앤매너: {tone}

---

### 1️⃣ 경쟁사 심층 분석 (소구점, 문장구조, SWOT)
- **핵심 소구점 및 혜택 분석**: 경쟁사들이 주로 강조하는 가치(가격, 품질, 배송, 이벤트 등)와 표현 패턴 분석.
- **문장 구조 및 패러다임 분석**: 경쟁사가 주로 사용하는 문장 구조 패턴과 진부해진 표현 도출.
- **경쟁사 전체 SWOT 분석**:
  * **Strong Points (강점)**
  * **Weak Points (약점)**
  * **Opportunities (기회)**
  * **Threats (위협)**

### 2️⃣ 디벨롭 카피라이팅 (우리 브랜드 맞춤형 역발상 소재)
- 매체별 글자 수 제한(공백 포함 순수 글자수)을 엄격히 준수:
  * 네이버 파워링크: 제목 **최대 15자** / 설명 **최대 45자**
  * 구글 검색광고 RSA: 제목 **최대 30자** / 설명 **최대 90자**
- 아래 표 형식으로 3세트 이상 작성:
  | 매체 | 세트 구분 | 구분(제목/설명/추가제목) | 디벨롭 광고 카피 문구 | 순수 글자수 | 경쟁사 대비 차별화 기획 의도 |

### 3️⃣ 네이버 파워링크 확장소재 및 캠페인 전략
- **네이버 파워링크 엄격한 글자수 규격 적용 확장소재 기획**:
  * **서브링크**: **최대 6자 제한** (예: 혜택 모아보기, 공식 스토어)
  * **이미지형 서브링크**: **최대 6자 제한** (예: 모션데스크, 맞춤형 책상)
  * **홍보문구**: **최대 14자 제한** (예: 지금 주문시 당일출고 혜택)
- **A/B 테스트 및 점수 관리 가이드**: 혜택 제안형 vs 문제 해결형 대립 테스트 및 구글 RSA 이점 점수 향상 팁.
"""

                response = None
                candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                try:
                    valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    if valid_models:
                        candidate_models = valid_models + candidate_models
                except Exception:
                    pass

                last_err = None
                for model_name in candidate_models:
                    try:
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        selected_model = model_name
                        break
                    except Exception as e:
                        last_err = e
                        continue

                if response:
                    st.success(f"✨ 경쟁사 심층 분석 & 소재 기획 완료! (사용 엔진: {selected_model})")
                    st.markdown(response.text)
                else:
                    raise last_err

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
