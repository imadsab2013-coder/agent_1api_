import streamlit as st
import json
import os
import requests
import google.generativeai as genai
from openai import OpenAI

# ---------------------------------------------------------
# 1. إعدادات النظام وتخزين الحالة (Architecture & Session)
# ---------------------------------------------------------
st.set_page_config(page_title="السبورة التفاعلية - Single-Agent", layout="wide")

CONFIG_FILE = "config.json"

MODELS_MATRIX = {
    "gemini": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.0-pro", "gemini-1.5-pro", "gemini-2.0-pro-exp"],
    "groq": ["llama3-8b-8192", "mixtral-8x7b-32768", "gemma2-9b-it", "llama3-70b-8192", "whisper-large-v3"],
    "gpt": ["gpt-4o-mini", "gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4o", "o1-mini"],
    "deepseek": ["deepseek-chat", "deepseek-coder", "deepseek-moe", "deepseek-reasoner", "deepseek-r1"]
}

BASE_URLS = {
    "gpt": None, 
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1"
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"system_prompt": "", "engines": {"gemini": {"api_key": "", "status": "ON"}, "groq": {"api_key": "", "status": "OFF"}, "gpt": {"api_key": "", "status": "OFF"}, "deepseek": {"api_key": "", "status": "OFF"}}}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

if "config" not in st.session_state:
    st.session_state.config = load_config()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "status_bulb" not in st.session_state:
    st.session_state.status_bulb = "⚪ بانتظار الاتصال"
if "active_model" not in st.session_state:
    st.session_state.active_model = MODELS_MATRIX["gemini"][0]
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7

config = st.session_state.config

# ---------------------------------------------------------
# 2. ميكانيكا فحص الاتصال (Ping Logic)
# ---------------------------------------------------------
def test_connection(engine, api_key, model):
    if not api_key:
        return False
    try:
        if engine == "gemini":
            genai.configure(api_key=api_key)
            test_model = genai.GenerativeModel(model)
            test_model.generate_content("ping")
            return True
        else:
            client = OpenAI(api_key=api_key, base_url=BASE_URLS[engine])
            # استثناء فحص نموذج الصوت النصي لتجنب أخطاء بروتوكول الـ API
            test_mod = "llama3-8b-8192" if model == "whisper-large-v3" else model
            client.chat.completions.create(
                model=test_mod,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            return True
    except Exception:
        return False

# ---------------------------------------------------------
# 3. واجهة الإعدادات الفرعية (Settings Panel)
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ إعدادات النظام")
    
    # البرومبت الحاكم
    new_prompt = st.text_area("النص الحاكم (System Prompt):", value=config.get("system_prompt", ""), height=150)
    
    # تحديد المحرك النشط (ON/OFF Logic حتمي)
    engines_list = list(config["engines"].keys())
    active_engine_index = 0
    for i, eng in enumerate(engines_list):
        if config["engines"][eng]["status"] == "ON":
            active_engine_index = i
            break
            
    selected_engine = st.radio("المحرك النشط (حظر التعدد):", engines_list, index=active_engine_index)
    
    # المفاتيح واختيار الموديل
    st.markdown("---")
    api_keys_input = {}
    for eng in engines_list:
        api_keys_input[eng] = st.text_input(f"مفتاح {eng.upper()}:", value=config["engines"][eng]["api_key"], type="password")
        
    st.markdown("---")
    selected_model = st.selectbox("الموديل:", MODELS_MATRIX[selected_engine], index=MODELS_MATRIX[selected_engine].index(st.session_state.active_model) if st.session_state.active_model in MODELS_MATRIX[selected_engine] else 0)
    selected_temp = st.slider("درجة الحرارة (Temperature):", 0.0, 1.0, st.session_state.temperature, 0.1)

    if st.button("حفظ وفحص الاتصال", use_container_width=True):
        # تحديث التهيئة المادية
        config["system_prompt"] = new_prompt
        for eng in engines_list:
            config["engines"][eng]["api_key"] = api_keys_input[eng]
            config["engines"][eng]["status"] = "ON" if eng == selected_engine else "OFF"
        
        save_config(config)
        st.session_state.config = config
        st.session_state.active_model = selected_model
        st.session_state.temperature = selected_temp
        
        # تنفيذ الفحص
        is_connected = test_connection(selected_engine, api_keys_input[selected_engine], selected_model)
        if is_connected:
            st.session_state.status_bulb = f"🟢 متصل ({selected_engine.upper()})"
        else:
            st.session_state.status_bulb = f"🔴 غير متصل ({selected_engine.upper()})"
        st.rerun()

# ---------------------------------------------------------
# 4. هندسة السبورة الموحدة والتنفيذ (The Board UI & Execution)
# ---------------------------------------------------------
st.markdown(f"### حالة المحرك: {st.session_state.status_bulb}")
st.markdown("---")

# حاوية السبورة - استدعاء الحوار
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# إدخال المستخدم وحقن القيود
if prompt := st.chat_input("اكتب تحليلك هنا..."):
    # إضافة سؤال المستخدم للسبورة
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # تحديد المحرك النشط وقراءة مفتاحه
    active_eng = None
    for eng, details in config["engines"].items():
        if details["status"] == "ON":
            active_eng = eng
            break
            
    active_key = config["engines"][active_eng]["api_key"]
    sys_prompt = config["system_prompt"]
    current_model = st.session_state.active_model
    temp = st.session_state.temperature

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""

        try:
            if not active_key:
                raise ValueError("مفتاح API غير متوفر للمحرك النشط.")

            if active_eng == "gemini":
                genai.configure(api_key=active_key)
                m = genai.GenerativeModel(model_name=current_model, system_instruction=sys_prompt)
                
                # بناء هيكل الرسائل لـ Gemini
                history = []
                for m_dict in st.session_state.messages[:-1]:
                    role = "user" if m_dict["role"] == "user" else "model"
                    history.append({"role": role, "parts": [m_dict["content"]]})
                
                chat = m.start_chat(history=history)
                response = chat.send_message(prompt, generation_config=genai.types.GenerationConfig(temperature=temp))
                full_response = response.text

            else:
                client = OpenAI(api_key=active_key, base_url=BASE_URLS[active_eng])
                
                # حقن البرومبت الحاكم في الـ OpenAI Compatible API
                messages_payload = [{"role": "system", "content": sys_prompt}]
                for m_dict in st.session_state.messages:
                    messages_payload.append({"role": m_dict["role"], "content": m_dict["content"]})

                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages_payload,
                    temperature=temp
                )
                full_response = response.choices[0].message.content

            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = f"**خطأ مادي في الاتصال:** {str(e)}"
            response_placeholder.markdown(error_msg)
            st.session_state.status_bulb = f"🔴 غير متصل ({active_eng.upper()})"
