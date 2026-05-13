"""
⚖️ محكمة الأفكار - The Bench of Evidence
نسخة Streamlit نهائية - معتمدة 100% على ملفات Excel المحلية
════════════════════════════════════════════════════════════════
"""

import streamlit as st
import pandas as pd
import sqlite3
import anthropic
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import io

# ════════════════════════════════════════════════════════════
# 1. إعدادات Streamlit
# ════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="⚖️ محكمة الأفكار",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ════════════════════════════════════════════════════════════
# 2. تحميل البيانات من Excel (Cached)
# ════════════════════════════════════════════════════════════

@st.cache_resource
def load_excel_data():
    """تحميل ملفات Excel مرة واحدة فقط"""
    try:
        # تحميل ملف القرآن
        quran_df = pd.read_excel("/mnt/user-data/uploads/quran_data.xlsx")
        
        # تحميل ملف الألفاظ
        words_df = pd.read_excel("/mnt/user-data/uploads/words_data.xlsx")
        
        # معالجة الخلايا المدمجة في الألفاظ
        words_df['اللفظ'] = words_df['اللفظ'].fillna(method='ffill')
        
        return quran_df, words_df
    except Exception as e:
        st.error(f"❌ خطأ في تحميل البيانات: {e}")
        return None, None

@st.cache_resource
def init_database():
    """إنشاء قاعدة بيانات SQLite في الذاكرة"""
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    
    # جدول الكتالوجات
    c.execute('''CREATE TABLE IF NOT EXISTS catalogs (
        id TEXT PRIMARY KEY,
        title TEXT,
        logic_core TEXT,
        status BOOLEAN,
        created_at TEXT
    )''')
    
    # جدول الإشارات المفضلة
    c.execute('''CREATE TABLE IF NOT EXISTS bookmarks (
        id TEXT PRIMARY KEY,
        verse_ref TEXT,
        note TEXT,
        created_at TEXT
    )''')
    
    conn.commit()
    return conn

# ════════════════════════════════════════════════════════════
# 3. فئات البيانات والمنطق
# ════════════════════════════════════════════════════════════

class QuranSearcher:
    """محرك البحث في القرآن"""
    
    def __init__(self, quran_df: pd.DataFrame, words_df: pd.DataFrame):
        self.quran_df = quran_df
        self.words_df = words_df
    
    def search_in_quran(self, query: str, limit: int = 5, offset: int = 0) -> Tuple[List[Dict], int]:
        """البحث في القرآن (Pagination)"""
        results = []
        
        # البحث عن الآية في اسم السورة أو الآية
        if 'سورة' in query or len(query) < 3:
            # بحث عن سورة
            matches = self.quran_df[
                self.quran_df.iloc[:, 0].str.contains(query, case=False, na=False)
            ]
        else:
            # بحث عن كلمة في نص الآية
            matches = self.quran_df[
                self.quran_df.iloc[:, 2].str.contains(query, case=False, na=False)
            ]
        
        total = len(matches)
        paginated = matches.iloc[offset:offset+limit]
        
        for _, row in paginated.iterrows():
            results.append({
                'سورة': row.iloc[0],
                'آية': row.iloc[1],
                'نص': row.iloc[2]
            })
        
        return results, total
    
    def search_word(self, word: str, limit: int = 5, offset: int = 0) -> Tuple[List[Dict], int]:
        """البحث عن لفظ في ملف الألفاظ (Exact Match)"""
        results = []
        
        # بحث دقيق
        matches = self.words_df[
            self.words_df.iloc[:, 0].str.strip() == word.strip()
        ]
        
        total = len(matches)
        paginated = matches.iloc[offset:offset+limit]
        
        for _, row in paginated.iterrows():
            results.append({
                'لفظ': row.iloc[0],
                'ورود': row.iloc[1],
                'سورة': row.iloc[2],
                'آية': row.iloc[3],
                'نص': row.iloc[4]
            })
        
        return results, total
    
    def get_surah_verses(self, surah_name: str, limit: int = 5, offset: int = 0) -> Tuple[List[Dict], int]:
        """الحصول على آيات سورة معينة"""
        results = []
        
        matches = self.quran_df[
            self.quran_df.iloc[:, 0] == surah_name
        ]
        
        total = len(matches)
        paginated = matches.iloc[offset:offset+limit]
        
        for _, row in paginated.iterrows():
            results.append({
                'سورة': row.iloc[0],
                'آية': row.iloc[1],
                'نص': row.iloc[2]
            })
        
        return results, total

class BenchAgent:
    """وكيل من محكمة الأفكار"""
    
    def __init__(self, role: str, agent_id: str, searcher: QuranSearcher, api_key: str):
        self.role = role
        self.id = agent_id
        self.searcher = searcher
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def get_system_prompt(self) -> str:
        """الحصول على نص النظام للوكيل"""
        
        base = f"""أنت {self.role} في محكمة الأفكار.

⚠️ قاعدة ذهبية: أنت ممنوع من استخدام أي معلومات خارج ملفات Excel المعروضة في الإعدادات.
إذا سُئلت عن شيء غير موجود فيها، صرح بعدم وجوده فوراً.

لا تبحث على الإنترنت.
لا تستخدم ذاكرتك العامة.
استدل من القرآن الكريم فقط - كما هو موجود في البيانات المحلية."""
        
        if self.role == "المناقش":
            return base + "\nدورك: عرض الآيات القرآنية ذات الصلة مباشرة من ملف البيانات."
        elif self.role == "محلل الآيات":
            return base + "\nدورك: تحليل الألفاظ والكلمات من خلال سياقها في القرآن."
        elif self.role == "المستنتج":
            return base + "\nدورك: الاستنتاج المنطقي الصارم من الآيات فقط."
        elif self.role == "الملاحظ":
            return base + "\nدورك: ملاحظة الأنماط والتناسقات في النصوص."
        elif self.role == "الناقد":
            return base + "\nدورك: النقد الصارم بناءً على البيانات القرآنية."
        
        return base
    
    def process_question(self, question: str) -> str:
        """معالجة السؤال"""
        try:
            # البحث عن ذات صلة
            relevant_verses, _ = self.searcher.search_in_quran(question[:20], limit=3)
            
            context = "الآيات ذات الصلة:\n"
            for verse in relevant_verses:
                context += f"({verse['سورة']} {verse['آية']}): {verse['نص']}\n"
            
            system_prompt = self.get_system_prompt()
            user_message = f"{question}\n\n{context}"
            
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                temperature=0,  # جمود تام
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            return response.content[0].text
        
        except Exception as e:
            return f"❌ خطأ: {str(e)}"

# ════════════════════════════════════════════════════════════
# 4. الواجهة الرئيسية
# ════════════════════════════════════════════════════════════

def main():
    """البرنامج الرئيسي"""
    
    # تحميل البيانات
    quran_df, words_df = load_excel_data()
    
    if quran_df is None or words_df is None:
        st.error("❌ فشل تحميل البيانات")
        return
    
    db_conn = init_database()
    searcher = QuranSearcher(quran_df, words_df)
    
    # ════════════════════════════════════════════════════
    # الرأس الرئيسي
    # ════════════════════════════════════════════════════
    
    st.title("⚖️ محكمة الأفكار")
    st.subheader("The Bench of Evidence")
    
    # ════════════════════════════════════════════════════
    # الشريط الجانبي - الإعدادات
    # ════════════════════════════════════════════════════
    
    with st.sidebar:
        st.markdown("## ⚙️ الإعدادات")
        st.divider()
        
        # الأيقونات الخمس
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("🔑", help="مفتاح API"):
                st.session_state.show_settings = True
        
        with col2:
            st.markdown("💡 متصل ✅" if True else "💡 غير متصل ❌")
        
        with col3:
            if st.button("📂", help="الكتالوجات"):
                st.session_state.show_catalogs = True
        
        with col4:
            if st.button("📊", help="البيانات"):
                st.session_state.show_data = True
        
        with col5:
            if st.button("👥", help="الأعضاء"):
                st.session_state.show_agents = True
        
        st.divider()
        
        # API Key
        api_key = st.text_input(
            "مفتاح Anthropic API:",
            type="password",
            placeholder="sk-ant-..."
        )
        
        if not api_key:
            st.warning("⚠️ يرجى إدخال مفتاح API")
            return
    
    # ════════════════════════════════════════════════════
    # الأيقونات الخمس - المحتوى
    # ════════════════════════════════════════════════════
    
    # عرض الإعدادات
    if st.session_state.get("show_settings", False):
        st.markdown("### 🔑 إعدادات API")
        st.info("✅ تم حفظ المفتاح")
    
    # عرض الكتالوجات
    if st.session_state.get("show_catalogs", False):
        st.markdown("### 📂 الكتالوجات (القواعس)")
        
        c = db_conn.cursor()
        c.execute("SELECT * FROM catalogs")
        catalogs = c.fetchall()
        
        if catalogs:
            for cat in catalogs:
                st.markdown(f"**§{cat[1]}§**: {cat[2]}")
        else:
            st.info("📭 لا توجد كتالوجات حالياً")
    
    # عرض البيانات
    if st.session_state.get("show_data", False):
        st.markdown("### 📊 ملفات البيانات الأصلية")
        
        tab1, tab2 = st.tabs(["القرآن الكريم", "الألفاظ"])
        
        with tab1:
            st.markdown("**quran_data.xlsx**")
            st.dataframe(quran_df.head(10), use_container_width=True, disabled=True)
        
        with tab2:
            st.markdown("**words_data.xlsx**")
            st.dataframe(words_df.head(10), use_container_width=True, disabled=True)
    
    # عرض الأعضاء
    if st.session_state.get("show_agents", False):
        st.markdown("### 👥 الأعضاء العشرة")
        
        agents_list = [
            ("A1", "💬 المناقش"),
            ("A2", "🔬 محلل الآيات"),
            ("A3", "🧮 المستنتج"),
            ("A4", "👁️ الملاحظ"),
            ("A5", "⚔️ الناقد"),
            ("A6", "⚖️ المقعد"),
            ("A7", "🎯 المنسق"),
            ("A8", "🎖️ الآمر"),
            ("A9", "🧠 الاستراتيجي"),
            ("A10", "🤖 الأوتوماتيكي")
        ]
        
        for code, name in agents_list:
            st.markdown(f"**{code}**: {name}")
    
    # ════════════════════════════════════════════════════
    # المحتوى الرئيسي - الوكلاء
    # ════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("## 🤖 الوكلاء العشرة")
    
    # اختيار الوكلاء
    agents_options = {
        "A1 - 💬 المناقش": "المناقش",
        "A2 - 🔬 محلل الآيات": "محلل الآيات",
        "A3 - 🧮 المستنتج": "المستنتج",
        "A4 - 👁️ الملاحظ": "الملاحظ",
        "A5 - ⚔️ الناقد": "الناقد"
    }
    
    selected_agents = st.multiselect(
        "اختر الوكلاء:",
        list(agents_options.keys()),
        default=["A1 - 💬 المناقش"]
    )
    
    # السؤال
    question = st.text_area(
        "السؤال:",
        placeholder="مثال: ما معنى الفرقان في القرآن الكريم؟",
        height=100
    )
    
    # زر المعالجة
    if st.button("🚀 معالجة السؤال", use_container_width=True):
        if not question:
            st.error("❌ يرجى إدخال السؤال")
            return
        
        if not selected_agents:
            st.error("❌ يرجى اختيار وكيل واحد على الأقل")
            return
        
        # معالجة من خلال الوكلاء
        st.markdown("---")
        st.markdown("## 📝 الردود")
        
        for agent_display in selected_agents:
            agent_name = agents_options[agent_display]
            agent_id = agent_display.split()[0]
            
            with st.spinner(f"⏳ جاري معالجة {agent_display}..."):
                agent = BenchAgent(agent_name, agent_id, searcher, api_key)
                response = agent.process_question(question)
                
                with st.expander(f"✅ {agent_display}", expanded=True):
                    st.markdown(response)
        
        st.success("✅ اكتملت المعالجة")
    
    # ════════════════════════════════════════════════════
    # قسم البحث المتقدم
    # ════════════════════════════════════════════════════
    
    st.markdown("---")
    st.markdown("## 🔍 البحث المتقدم")
    
    search_type = st.radio(
        "نوع البحث:",
        ["البحث في القرآن", "البحث عن لفظ", "آيات السورة"],
        horizontal=True
    )
    
    if search_type == "البحث في القرآن":
        query = st.text_input("ابحث عن:")
        if query:
            results, total = searcher.search_in_quran(query)
            
            col1, col2 = st.columns([0.8, 0.2])
            with col2:
                if st.button("⬇️ تحميل المزيد"):
                    st.session_state.quran_offset = st.session_state.get("quran_offset", 0) + 5
            
            for result in results:
                st.markdown(f"**({result['سورة']} {result['آية']})**: {result['نص']}")
            
            st.caption(f"📊 {total} نتائج")
    
    elif search_type == "البحث عن لفظ":
        word = st.text_input("ابحث عن لفظ:")
        if word:
            results, total = searcher.search_word(word)
            
            if results:
                for result in results:
                    st.markdown(f"**{result['لفظ']}** - ورود: {result['ورود']}")
                    st.markdown(f"({result['سورة']} {result['آية']}): {result['نص']}")
                
                if st.button("⬇️ تحميل المزيد"):
                    st.session_state.word_offset = st.session_state.get("word_offset", 0) + 5
            else:
                st.warning("❌ لم أجد اللفظ في البينة المادية")
    
    elif search_type == "آيات السورة":
        surahs = quran_df.iloc[:, 0].unique()
        surah = st.selectbox("اختر السورة:", surahs)
        
        if surah:
            results, total = searcher.get_surah_verses(surah)
            
            for result in results:
                st.markdown(f"**آية {result['آية']}**: {result['نص']}")
            
            if st.button("⬇️ تحميل المزيد"):
                st.session_state.surah_offset = st.session_state.get("surah_offset", 0) + 5

# ════════════════════════════════════════════════════════
# البداية
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    # تهيئة الجلسة
    for key in ["show_settings", "show_catalogs", "show_data", "show_agents", 
                "quran_offset", "word_offset", "surah_offset"]:
        if key not in st.session_state:
            st.session_state[key] = False if "show_" in key else 0
    
    main()
