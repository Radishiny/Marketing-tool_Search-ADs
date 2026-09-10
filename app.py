import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import google.generativeai as genai
import json
import io
import time
import requests
import base64
import hmac
import hashlib
import re

# 페이지 기본 설정
st.set_page_config(page_title="Ad-Inverted & Monitoring Pro", layout="wide")

# ---------------------------------------------------------
# Session State 초기화
# ---------------------------------------------------------
if "ad_history" not in st.session_state:
    st.session_state["ad_history"] = pd.DataFrame(
        columns=["수집시간", "키워드", "브랜드", "URL", "광고 제목", "추가제목", "설명", "홍보문구", "서브링크"]
    )

if "competitors" not in st.session_state:
    st.session_state.competitors = [
        {"brand": "", "title": "", "sub_title": "", "desc": "", "url": ""}
    ]

if "banner_result" not in st.session_state:
    st.session_state["banner_result"] = None

def add_competitor():
    st.session_state.competitors.append({"brand": "", "title": "", "sub_title": "", "desc": "", "url": ""})

def remove_competitor(index):
    if len(st.session_state.competitors) > 1:
        st.session_state.competitors.pop(index)

# ---------------------------------------------------------
# 사이드바 (API 키 및 데이터 관리)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ API 및 시스템 설정")
    gemini_api_key = st.text_input(
        "Google Gemini API Key 입력", 
        type="password", 
        help="https://aistudio.google.com/ 에서 발급받은 키를 입력하세요."
    )
    st.markdown("[👉 Gemini API 키 발급받기](https://aistudio.google.com/)")
    
    st.divider()
    
    st.subheader("🔑 네이버 검색광고 API (선택)")
    naver_api_key = st.text_input("Access License (API Key)", type="password", key="nav_api")
    naver_secret_key = st.text_input("Secret Key", type="password", key="nav_sec")
    naver_customer_id = st.text_input("Customer ID (숫자)", key="nav_cust")

    st.divider()
    st.subheader("💾 누적 수집 데이터 관리")
    st.write(f"현재 DB 수집 소재 수: **{len(st.session_state['ad_history'])}개**")
    if st.button("수집 데이터 초기화", use_container_width=True):
        st.session_state["ad_history"] = pd.DataFrame(
            columns=["수집시간", "키워드", "브랜드", "URL", "광고 제목", "추가제목", "설명", "홍보문구", "서브링크"]
        )
        st.success("저장된 데이터가 초기화되었습니다.")

# ---------------------------------------------------------
# 상단 기능 선택 배너 / 네비게이션
# ---------------------------------------------------------
st.title("🚀 소재 데이터화 & 기획 자동화 툴 (Kyeong's)")

mode = st.radio(
    "📌 원하는 작업 모드를 선택하세요:",
    ["1️⃣ 경쟁사 소재 분석 & AI 소재 기획 (Kyeong's)", "2️⃣ 네이버SA 실시간 모니터링 & 소재 데이터화"],
    horizontal=True,
    key="main_mode"
)

st.divider()

# =========================================================
# [모드 1] 경쟁사 소재 분석 & AI 소재 기획 (Kyeong's)
# =========================================================
if mode == "1️⃣ 경쟁사 소재 분석 & AI 소재 기획 (Kyeong's)":
    st.caption("경쟁사 소재 데이터 분석(소구점·문장구조·SWOT) ➔ 효율 개선 전략 수립 및 혁신 지표 산출")

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

    col1, col2 = st.columns([1.1, 0.9])

    with col1:
        st.subheader("1️⃣ 메인 키워드 및 경쟁사 소재")
        keyword = st.text_input("분석할 메인 검색어", value="책상", key="main_keyword_input")
        
        if not st.session_state["ad_history"].empty:
            if st.button("📥 [모드 2]에서 수집한 DB 데이터를 입력창으로 가져오기"):
                st.session_state.competitors = []
                for _, row in st.session_state["ad_history"].iterrows():
                    st.session_state.competitors.append({
                        "brand": row["브랜드"],
                        "title": row["광고 제목"],
                        "sub_title": row["추가제목"],
                        "desc": row["설명"],
                        "url": row["URL"]
                    })
                st.success("수집된 DB 데이터를 분석 목록으로 불러왔습니다!")

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
                    
                comp["desc"] = st.text_area(f"광고 설명 #{idx + 1}", value=comp["desc"], placeholder="예: 튼튼한 E0 자재 사용, 높낮이 조절 책상", key=f"desc_{idx}", height=70)
                comp["url"] = st.text_input(f"랜딩페이지 URL #{idx + 1}", value=comp["url"], placeholder="예: https://example.com/desk", key=f"url_{idx}")

        st.button("➕ 경쟁사 소재 추가하기", on_click=add_competitor, use_container_width=True)

    with col2:
        st.subheader("2️⃣ 광고주 정보 & 매체 설정")
        my_brand_name = st.text_input("브랜드명", value="", placeholder="공란으로 두거나 브랜드를 입력하세요", key="my_brand")
        my_brand_url = st.text_input("랜딩페이지 URL", value="", placeholder="공란으로 두거나 URL을 입력하세요", key="my_url")
        
        must_include = st.text_input("강조할 키워드/소구점", value="당일출고, 5년 무상보증", key="must_inc")
        tone = st.text_input("소재 톤앤매너", value="직관적/성능강조형/전문성", key="tone_val")
        
        st.markdown("##### 📐 타겟 매체 설정")
        use_naver = st.checkbox("네이버 파워링크 (제목 15자 / 설명 45자)", value=True, key="chk_naver")
        use_google = st.checkbox("구글 검색광고 RSA (제목 30자 / 설명 90자)", value=True, key="chk_google")

    st.divider()

    if st.button("🚀 경쟁사 심층 분석 및 AI 기획 실행", use_container_width=True):
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
                            mime="text/csv",
                            key="dl_csv_1"
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
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_xlsx_1"
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

                with st.spinner("경쟁사 심층 분석, AI 카피라이팅 및 [혁신 예측 지표] 산출 중입니다..."):
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
- 브랜드명: {my_brand_name if my_brand_name else "(브랜드명 미지정)"}
- 브랜드 URL: {my_brand_url if my_brand_url else "(URL 미지정)"}

[광고주 필수 요청사항]
- 필수 강조 문구/소구점: {must_include}
- 톤앤매너: {tone}

---

### 1️⃣ 경쟁사 심층 분석 (소구점, 문장구조, SWOT)
- **핵심 소구점 및 혜택 분석**: 경쟁사들이 주로 강조하는 가치와 표현 패턴 분석.
- **문장 구조 및 패러다임 분석**: 경쟁사가 주로 사용하는 문장 구조 패턴과 진부해진 표현 도출.
- **경쟁사 전체 SWOT 분석**:
  * **Strong Points (강점)**
  * **Weak Points (약점)**
  * **Opportunities (기회)**
  * **Threats (위협)**

### 2️⃣ 디벨롭 카피라이팅 & [혁신 정량 예측 지표]
- 매체별 글자 수 제한(공백 포함 순수 글자수)을 엄격히 준수:
  * 네이버 파워링크: 제목 **최대 15자** / 설명 **최대 45자**
  * 구글 검색광고 RSA: 제목 **최대 30자** / 설명 **최대 90자**
- 아래 표 형식으로 3세트 이상 작성하되, **예상 CTR(클릭률) 상승 예측치(%)**와 **경쟁사 대비 차별화 지수(0~100점)**를 정량 지표로 함께 기재:
  | 매체 | 세트 구분 | 디벨롭 광고 카피 문구 (구분/내용) | 순수 글자수 | 예상 CTR 상승률 (%) | 차별화 지수 (100점 만점) | 기획 의도 |

### 3️⃣ 네이버 파워링크 확장소재 및 캠페인 전략
- **네이버 파워링크 확장소재 규격 적용**:
  * **서브링크**: **최대 6자 제한** (예: 혜택 모아보기, 공식 스토어)
  * **이미지형 서브링크**: **최대 6자 제한** (예: 모션데스크, 맞춤형 책상)
  * **홍보문구**: **최대 14자 제한** (예: 지금 주문시 당일출고 혜택)
- **A/B 테스트 및 점수 관리 가이드**: 혜택 제안형 vs 문제 해결형 대립 테스트 전략.
"""

                    response = None
                    candidate_models = ["gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
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
                        st.success(f"✨ 경쟁사 심층 분석 & 혁신 기획 완료! (사용 엔진: {selected_model})")
                        st.markdown(response.text)
                    else:
                        raise last_err

            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

    # ---------------------------------------------------------
    # AI 광고 이미지 시안 컨셉 & 프롬프트 생성 (네이버 검수 기준 반영: 텍스트 원천 차단)
    # ---------------------------------------------------------
    st.divider()
    st.subheader("🎨 AI 이미지 프롬프트 생성")
    st.caption("네이버 검색광고 가이드 준수: **이미지 내 텍스트/워터마크 삽입 금지**, **100% 실물 중심 스튜디오 컷**, **최적 파일 용량 및 압축 스펙** 반영")
    
    if "banner_concept_input_box" not in st.session_state:
        st.session_state["banner_concept_input_box"] = f"{keyword} 실물 중심, 깔끔한 스튜디오 조명, 텍스트 없는 순수 제품 컷"

    banner_concept_input = st.text_input(
        "배너 핵심 컨셉 키워드", 
        value=st.session_state["banner_concept_input_box"], 
        key="banner_concept_input_box"
    )
    
    def generate_banner_concept():
        if not gemini_api_key:
            st.error("좌측 사이드바에 Google Gemini API Key를 입력해주세요!")
            return
        
        with st.spinner("네이버 광고 검수 기준(텍스트 금지 및 실물 중심)에 맞춘 비주얼 가이드를 빌드 중입니다..."):
            try:
                genai.configure(api_key=gemini_api_key)
                vis_prompt = f"""
                너는 네이버 검색광고(파워링크 이미지 및 확장소재) 검수 규정을 완벽히 꿰뚫고 있는 수석 광고 디자이너야.
                사용자가 입력한 검색 키워드와 컨셉을 바탕으로, **네이버 검수 반려 우려가 없는 100% 순수 실물 비주얼 광고 배너 기획서**를 작성해줘.

                - 입력 키워드: {keyword}
                - 사용자 컨셉: {st.session_state.get("banner_concept_input_box", keyword)}

                [네이버 검색광고 철저 준수 원칙]
                1. **이미지 내 텍스트/글자/워터마크 절대 삽입 금지 (Text-Free Image)**: 네이버 광고 가이드상 이미지 내에 글자나 슬로건, 로고가 포함되면 검수에 불합격하므로, 오직 **순수 제품/오브젝트 및 공간 배경**만으로 신뢰를 주는 연출법을 기획할 것.
                2. **현실적이고 상업적인 실물 톤앤매너**: 공상과학적, 미래지향적, 초현실적인 몽환적 느낌을 완전히 배제하고, 실제 소비자가 스토어에서 구매할 때 보는 직관적이고 깔끔한 실물 촬영본 느낌을 살릴 것.
                3. **업계 맞춤형 비주얼 보정**: '{keyword}'의 특성(예: 가구는 실제 인테리어 공간 속 배치, 식품은 신선한 실물 접사, IT는 깔끔한 화이트 배경 속 제품 디테일 등)에 맞게 최적화.
                4. **웹 최적화 파일 스펙 제안**: 네이버 권장 확장자(JPG, PNG, WebP) 및 로딩 지연을 막기 위한 적정 파일 용량(100KB~200KB 이하 권장) 관리 가이드 포함.

                [출력 포함 내용]
                1. 🔍 **[업계 키워드 맞춤 비주얼 방향성 및 검수 안전 가이드]**: 텍스트 없이 시각적 신뢰감을 주는 연출 전략
                2. 🖼️ **[배너 레이아웃 및 구도 스펙]**: 여백, 피사체 배치, 조명 셋업
                3. 🎨 **[컬러 팔레트 및 배경 톤]**: 구매 전환율을 높이는 현실적인 색감 조합
                4. 💡 **[AI 이미지 생성 영문 프롬프트 (텍스트 없음, 100% 순수 실물 컷)]**: 미드저니/DALL-E 등에서 글자 없이 실물 사진을 뽑아낼 수 있는 구체적인 프롬프트
                """
                
                vis_model = genai.GenerativeModel("gemini-3.6-flash")
                vis_res = vis_model.generate_content(vis_prompt)
                st.session_state["banner_result"] = vis_res.text
            except Exception as e:
                st.error(f"콘셉트 생성 중 오류 발생: {e}")

    st.button(
        "🖼️ AI 이미지 생성하기", 
        on_click=generate_banner_concept, 
        use_container_width=True, 
        key="btn_gen_banner"
    )

    if st.session_state.get("banner_result"):
        st.success("✨ 네이버 검수 규격(텍스트 제외, 실물 중심) 반영 완료된 배너 비주얼 기획서 생성 완료!")
        st.markdown(st.session_state["banner_result"])

# =========================================================
# [모드 2] 네이버SA 실시간 모니터링 & 소재 데이터화
# =========================================================
else:
    tab1, tab2 = st.tabs(["1. 모바일 실시간 모니터링 & 소재 수집", "2. 누적 데이터베이스"])

    with tab1:
        st.markdown("### ⚡ 네이버 파워링크 모니터링 & 소재 분류")
        target_keyword = st.text_input("모니터링할 키워드를 입력하세요", "책상", key="mon_keyword")
        
        col1, col2 = st.columns([1.1, 0.9])
        
        with col1:
            st.markdown("#### 📱 모바일 파워링크 (MO)")
            with st.container():
                iframe_html = f"""
                <div style="display: flex; justify-content: center; background-color: #f0f2f5; padding: 10px; border-radius: 12px;">
                    <div style="width: 480px; height: 720px; border: 6px solid #222; border-radius: 28px; overflow: hidden; background: #fff; box-shadow: 0 6px 15px rgba(0,0,0,0.18);">
                        <iframe src="https://m.ad.search.naver.com/search.naver?where=m_ad&query={target_keyword}" 
                                width="100%" height="100%" frameborder="0" style="zoom: 0.85; -moz-transform: scale(0.85); -moz-transform-origin: 0 0;"></iframe>
                    </div>
                </div>
                """
                components.html(iframe_html, height=750, scrolling=False)

        with col2:
            st.markdown("#### 🧠 AI 소재 자동 분류")
            st.caption("모바일 광고 영역을 드래그하여 붙여넣으세요. 항목별로 깔끔하게 분류되어 DB에 누적됩니다.")
            
            raw_text_input = st.text_area(
                "경쟁사 소재 문구 통복사 붙여넣기", 
                placeholder="favicon\n아성가구\nasungoa.com\n네이버페이\n네이버 톡톡\n책상 아성가구 대량견적 추가할인!\n...",
                height=350,
                key="raw_txt_area"
            )
            
            if st.button("🤖 AI로 소재 정밀 분류 및 DB 등록", use_container_width=True, key="btn_parse_db"):
                if not gemini_api_key:
                    st.error("좌측 사이드바에 Gemini API Key를 입력해 주세요.")
                elif not raw_text_input.strip():
                    st.warning("붙여넣을 텍스트를 입력해 주세요.")
                else:
                    try:
                        genai.configure(api_key=gemini_api_key)
                        
                        try:
                            model = genai.GenerativeModel('gemini-3.6-flash')
                        except Exception:
                            try:
                                model = genai.GenerativeModel('gemini-2.0-flash')
                            except Exception:
                                model = genai.GenerativeModel('gemini-1.5-pro')
                        
                        parsing_prompt = f"""
                        다음은 사용자가 네이버 검색광고 화면에서 복사한 원본 텍스트입니다:
                        
                        "{raw_text_input}"
                        
                        [엄격 파싱 및 분리 규칙]
                        1. 'favicon', '네이버페이', '네이버 톡톡' 등 시스템 아이콘 및 부가 안내 문구는 완전 무시하고 제외하세요.
                        2. 브랜드 및 URL: 'favicon' 아래 나오는 브랜드명과 웹사이트 도메인을 각각 'brand', 'url'로 지정하세요.
                        3. 타이틀 영역 (광고 제목 & 추가제목):
                           - 타이틀 라인에서 브랜드명을 기준으로, 앞부분(키워드+브랜드명)은 '광고 제목'으로, 그 뒤에 붙은 문구는 '추가제목'으로 정확히 분리하세요.
                        4. 설명 (대표 설명문구):
                           - 긴 본문 설명 문구만 '설명' 칸에 넣으세요.
                        5. 홍보문구:
                           - '할인', '이벤트', '사은품', '특가' 등 단독 태그 단어와 그 바로 밑/뒤에 오는 홍보 문구는 묶어서 'promo_text' 칸에 넣으세요.
                        6. 서브링크:
                           - 홍보문구 밑에 나열된 카테고리 단어들은 쉼표(,)로 연결하여 '서브링크' 칸에 넣으세요.
                        7. 데이터가 없는 항목은 빈 문자열("")로 두세요.

                        결과는 오직 아래 JSON 배열 형식으로만 출력하세요. 백틱이나 부연 설명은 절대 금지합니다.
                        [
                            {{
                                "brand": "브랜드명",
                                "url": "URL",
                                "title": "광고 제목",
                                "sub_title": "추가제목",
                                "desc": "설명",
                                "promo_text": "홍보문구",
                                "sub_links": "서브링크들"
                            }}
                        ]
                        """
                        
                        with st.spinner("AI가 소재를 정밀 분류 및 누적 중입니다..."):
                            response = model.generate_content(parsing_prompt)
                            
                            cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
                            cleaned_json = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_json)
                            
                            parsed_data = json.loads(cleaned_json, strict=False)
                            
                            current_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_rows = []
                            for item in parsed_data:
                                new_rows.append({
                                    "수집시간": current_time,
                                    "키워드": target_keyword,
                                    "브랜드": item.get("brand", "") or "",
                                    "URL": item.get("url", "") or "",
                                    "광고 제목": item.get("title", "") or "",
                                    "추가제목": item.get("sub_title", "") or "",
                                    "설명": item.get("desc", "") or "",
                                    "홍보문구": item.get("promo_text", "") or "",
                                    "서브링크": item.get("sub_links", "") or ""
                                })
                            
                            added_df = pd.DataFrame(new_rows)
                            st.session_state["ad_history"] = pd.concat(
                                [st.session_state["ad_history"], added_df], ignore_index=True
                            )
                            
                            st.success(f"🎉 성공적으로 {len(added_df)}개 소재가 DB에 누적되었습니다!")
                            st.dataframe(added_df, use_container_width=True)
                            
                    except Exception as e:
                        st.error(f"파싱 중 오류가 발생했습니다: {e}")

    with tab2:
        st.markdown("### 📊 수집된 경쟁사 소재 데이터베이스")
        
        if st.session_state["ad_history"].empty:
            st.write("저장된 데이터가 없습니다.")
        else:
            st.dataframe(st.session_state["ad_history"], use_container_width=True)
            
            csv = st.session_state["ad_history"].to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 CSV 데이터 다운로드",
                data=csv,
                file_name="competitor_ads_history.csv",
                mime="text/csv",
                key="dl_csv_db"
            )
