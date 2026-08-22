

import streamlit as st
import google.generativeai as genai
import requests
import json

from database import query_database


# =====================================================
# CONFIGURATION
# =====================================================

API_KEY = st.secrets["API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    "gemini-2.5-flash"
)


# =====================================================
# PAGE
# =====================================================

st.set_page_config(
    page_title="INGRES AI Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 INGRES AI Assistant")


# =====================================================
# CHAT HISTORY
# =====================================================

if "messages" not in st.session_state:

    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# =====================================================
# PDF
# =====================================================

st.sidebar.header("📄 PDF Knowledge Base")

uploaded_file = st.sidebar.file_uploader(
    "Upload PDF",
    type=["pdf"]
)


# =====================================================
# PDF SEARCH
# =====================================================

def search_knowledge(question):

    if uploaded_file is None:

        return ""

    try:

        from pypdf import PdfReader

        reader = PdfReader(uploaded_file)

        text = ""

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:

                text += page_text + "\n"

        if not text.strip():

            return ""

        # Give Gemini the PDF text
        # and let it determine relevant information.

        prompt = f"""
You are searching an uploaded INGRES PDF.

USER QUESTION:
{question}

PDF CONTENT:
{text}

Return ONLY the parts of the PDF that are
relevant to answering the user's question.

If the PDF does not contain relevant
information, return:

NOT_FOUND
"""

        response = model.generate_content(prompt)

        result = response.text.strip()

        if result == "NOT_FOUND":

            return ""

        return result

    except Exception:

        return ""


# =====================================================
# WEB SEARCH
# =====================================================

def search_web(query):

    try:

        response = requests.post(
            "https://api.tavily.com/search",

            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True
            },

            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        result = ""

        if data.get("answer"):

            result += (
                data["answer"]
                + "\n\n"
            )

        for item in data.get("results", []):

            result += (
                f"Title: {item.get('title')}\n"
                f"URL: {item.get('url')}\n"
                f"Content: {item.get('content')}\n\n"
            )

        return result

    except Exception:

        return ""


# =====================================================
# GENERATE SQL FROM QUESTION
# =====================================================

def generate_sql(question):

    sql_prompt = f"""
You are an SQL expert working with an INGRES
groundwater database.

The database has these tables.

TABLE: assessments

Columns:
- id
- state
- district
- block
- year
- recharge_bcm
- extractable_bcm
- extraction_bcm
- stage_percent
- category

TABLE: faq

Columns:
- id
- question
- answer

Convert the user's natural-language question
into ONE SQLite SELECT query.

Rules:

1. Only generate SELECT queries.
2. You can use JOIN, WHERE, GROUP BY,
   ORDER BY, COUNT, AVG, MAX, MIN, etc.
3. Search both assessments and faq when
   appropriate.
4. Do not invent table or column names.
5. Return ONLY the SQL query.
6. Do not use markdown.

USER QUESTION:

{question}
"""

    response = model.generate_content(
        sql_prompt
    )

    sql = response.text.strip()

    if sql.startswith("```"):

        lines = sql.split("\n")

        sql = "\n".join(
            lines[1:-1]
        ).strip()

    return sql


# =====================================================
# ANSWER FROM DATABASE
# =====================================================

def answer_from_database(
    question,
    database_result
):

    prompt = f"""
You are the INGRES AI assistant.

Answer the user's question using the
database result below.

DATABASE RESULT:

{database_result}

USER QUESTION:

{question}

Rules:

- Use the database result.
- Do not invent information.
- Explain numbers clearly.
- If multiple records were returned,
  summarize them appropriately.
- Give a direct answer.
"""

    response = model.generate_content(
        prompt
    )

    return response.text.strip()


# =====================================================
# MAIN QUESTION LOGIC
# =====================================================

def process_question(question):

    # =================================================
    # 1. DATABASE FIRST
    # =================================================

    with st.spinner(
        "🔎 Searching INGRES database..."
    ):

        try:

            sql_query = generate_sql(
                question
            )

            database_result = query_database(
                sql_query
            )

        except Exception:

            database_result = ""


    # =================================================
    # DATABASE FOUND SOMETHING
    # =================================================

    if database_result:

        return answer_from_database(
            question,
            database_result
        )


    # =================================================
    # 2. DATABASE DID NOT HAVE IT
    # → CHECK PDF
    # =================================================

    with st.spinner(
        "📄 Checking uploaded PDF..."
    ):

        pdf_context = search_knowledge(
            question
        )


    if pdf_context:

        prompt = f"""
You are the INGRES AI assistant.

Answer the user's question using the
uploaded PDF information.

PDF INFORMATION:

{pdf_context}

USER QUESTION:

{question}

Do not invent information.
Give a clear and helpful answer.
"""

        response = model.generate_content(
            prompt
        )

        return response.text.strip()


    # =================================================
    # 3. DATABASE + PDF DID NOT HAVE IT
    # → NORMAL AI / WEB
    # =================================================

    router_prompt = f"""
The INGRES database and uploaded PDF have
already been checked.

Decide whether this question requires
a live web search.

Reply ONLY YES or NO.

Question:

{question}
"""

    response = model.generate_content(
        router_prompt
    )

    needs_web = response.text.strip().upper()


    if "YES" in needs_web:

        with st.spinner(
            "🌐 Searching the web..."
        ):

            web_context = search_web(
                question
            )

        prompt = f"""
Answer the user's question using the
following web research.

WEB RESEARCH:

{web_context}

USER QUESTION:

{question}

Give a clear and accurate answer.
"""

        response = model.generate_content(
            prompt
        )

        return response.text.strip()


    # =================================================
    # NORMAL GEMINI
    # =================================================

    response = model.generate_content(
        question
    )

    return response.text.strip()


# =====================================================
# CHAT INPUT
# =====================================================

if prompt := st.chat_input(
    "Ask about INGRES..."
):

    if not prompt.strip():

        st.warning(
            "Please enter a question."
        )

        st.stop()


    # -------------------------------------------------
    # USER MESSAGE
    # -------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)


    # -------------------------------------------------
    # ASSISTANT
    # -------------------------------------------------

    with st.chat_message("assistant"):

        try:

            answer = process_question(
                prompt
            )

        except Exception as e:

            answer = (
                f"Error: {e}"
            )

        st.markdown(answer)


    # -------------------------------------------------
    # SAVE ANSWER
    # -------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )
