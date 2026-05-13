"""
⚖️ محكمة الأفكار - The Bench of Evidence
نسخة Streamlit نهائية - معتمدة 100% على ملفات Excel المحلية (نسخة Gemini)
════════════════════════════════════════════════════════════════
"""

import streamlit as st
import pandas as pd
import google.generativeai as genai
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import io

# 1. إعدادات Streamlit
st.set_page_config(
    page_title="⚖️ محكمة الأفكار",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. تحميل البيانات من Excel (المسارات أصبحت محلية لتعمل على GitHub)
@st.cache_resource
def load_excel_data():
    try:
        # قراءة الملفات من المجلد الرئيسي للمستودع مباشرة
        quran_df = pd.read_excel("quran_data.xlsx")
        words_df = pd.read_excel("words_data.xlsx")
        
        # معالجة الخلايا المدمجة
        words_df['اللفظ'] = words_df['اللفظ'].ffill()
        return quran_df, words_df
    except Exception as e:
        st.error(f"❌ خطأ مادي في تحميل البيانات: {e}")
        return None, None

# 3. محرك البحث الصارم
class QuranSearcher:
    def __init__(self, quran_df: pd.DataFrame, words_df: pd.DataFrame):
        self.quran_df = quran_df
        self.words_df = words_df
    
    def search_in_quran(self, query: str, limit: int = 5, offset: int = 0) -> Tuple[List[Dict], int]:
        if 'سورة' in query or len(query) < 3:
            matches = self.quran_df[self.quran_df.iloc[:, 0].str.contains(query, case=False, na=False)]
        else:
            matches = self.quran_df[self.quran_df.iloc[:, 2].str.contains(query, case=False, na=False)]
        total = len(matches)
        paginated = matches.iloc[offset:offset+limit]
        return [{'سورة': r.iloc[0], 'آية': r.iloc[1], 'نص': r.iloc[2]} for _, r in paginated.iterrows()], total

    def search_word(self, word: str, limit: int = 5, offset: int = 0) -> Tuple[List[Dict], int]:
        matches = self.words_df[self.words_df.iloc[:, 0].str.strip() == word.strip()]
        total = len(matches)
        paginated = matches.iloc[offset:offset+limit]
        return [{'لفظ': r.iloc[0], 'ورود': r.iloc[1], 'سورة': r.iloc[2], 'آية': r.iloc[3], 'نص': r.iloc[4]} for _, r in paginated.iterrows()], total

# 4. وكيل المحكمة (باستخدام Gemini)
class BenchAgent:
    def __init__(self, role: str, agent_id: str, searcher: QuranSearcher, api_key: str):
        self.role = role
        self.id = agent_id
        self.searcher = searcher
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def process_question(self, question: str) -> str:
        try:
            relevant_verses, _ = self.searcher.search_in_quran(question[:20], limit=3)
            context = "الآيات ذات الصلة من البينة المادية:\n" + "\n".join([f"({v['سورة']} {v['آية']}): {v['نص']}" for v in relevant_verses])
            
            system_prompt = f"أنت {self.role} في محكمة الأفكار. ممنوع استخدام أي معلومة خارج نصوص الإكسيل المرفقة. التزم بالمنطق المادي الصارم."
            response = self.model.generate_content(f"{system_prompt}\n\nالسؤال: {question}\n\n{context}")
            return response.text
        except Exception as e:
            return f"❌ خطأ في المعالجة: {str(e)}"

# 5. الواجهة الرئيسية
def main():
    quran_df, words_df = load_excel_data()
    if quran_df is None: return

    searcher = QuranSearcher(quran_df, words_df)
    st.title("⚖️ محكمة الأفكار")
    
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        api_key = st.text_input("Gemini API Key:", type="password")
        if not api_key:
            st.warning("⚠️ أدخل مفتاح API لتفعيل الوكلاء")
            # السماح بالبحث حتى بدون مفتاح
        
        if st.button("📊 عرض البيانات"):
            st.session_state.show_data = not st.session_state.get("show_data", False)

    if st.session_state.get("show_data", False):
        st.dataframe(quran_df.head(5))

    # قسم الوكلاء
    st.markdown("## 🤖 الوكلاء العشرة")
    agent_choice = st.selectbox("اختر الوكيل:", ["A1 - المناقش", "A2 - محلل الآيات", "A3 - المستنتج"])
    question = st.text_area("أدخل تساؤلك المنطقي:")
    
    if st.button("🚀 تنفيذ الاستنباط"):
        if api_key and question:
            agent = BenchAgent(agent_choice.split("-")[1].strip(), agent_choice.split("-")[0], searcher, api_key)
            st.markdown(agent.process_question(question))
        else:
            st.error("المعطيات ناقصة (المفتاح أو السؤال)")

    # قسم البحث
    st.markdown("---")
    st.markdown("## 🔍 البحث السريع")
    search_query = st.text_input("ابحث في نص القرآن:")
    if search_query:
        results, total = searcher.search_in_quran(search_query)
        for res in results:
            st.write(f"**{res['سورة']} ({res['آية']})**: {res['نص']}")

if __name__ == "__main__":
    main()
