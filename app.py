
import streamlit as st
import sqlite3
import requests

from openai import OpenAI
from pypdf import PdfReader


# =====================================================
# CONFIGURATION
# =====================================================

DB_NAME = "ingres.db"

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]

client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="INGRES AI Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 INGRES AI Assistant")


# =====================================================
# SESSION STATE
# =====================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""


# =====================================================
# DISPLAY CHAT HISTORY
# =====================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =====================================================
# SIDEBAR PDF UPLOAD
# =====================================================

st.sidebar.header("📄 INGRES PDF")

uploaded_file = st.sidebar.file_uploader(
    "Upload INGRES PDF",
    type=["pdf"]
)


if uploaded_file is not None:

    if st.sidebar.button("Add PDF"):

        try:

            reader = PdfReader(uploaded_file)

            full_text = ""

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    full_text += text + "\n"

            st.session_state.pdf_text = full_text

            st.sidebar.success(
                "PDF added successfully!"
            )

        except Exception as e:

            st.sidebar.error(
                f"PDF error: {e}"
            )


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_connection():

    return sqlite3.connect(DB_NAME)


# =====================================================
# SEARCH FAQ DATABASE
# =====================================================

def search_faq(question):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
        SELECT question, answer
        FROM faq
        """)

        rows = cursor.fetchall()

        question_lower = question.lower()

        matches = []

        for faq_question, faq_answer in rows:

            text = (
                faq_question + " " + faq_answer
            ).lower()

            score = 0

            for word in question_lower.split():

                word = word.strip(
                    ".,?!:;'\""
                )

                if len(word) > 2 and word in text:
                    score += 1

            if score > 0:

                matches.append(
                    (score, faq_question, faq_answer)
                )

        matches.sort(
            key=lambda x: x[0],
            reverse=True
        )

        result = ""

        for score, q, answer in matches[:5]:

            result += (
                f"Question: {q}\n"
                f"Answer: {answer}\n\n"
            )

        return result

    finally:

        conn.close()


# =====================================================
# SEARCH ASSESSMENTS DATABASE
# =====================================================

def search_assessments(question):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute("""
        SELECT
            state,
            district,
            block,
            year,
            recharge_bcm,
            extractable_bcm,
            extraction_bcm,
            stage_percent,
            category
        FROM assessments
        """)

        rows = cursor.fetchall()

        question_lower = question.lower()

        matches = []

        for row in rows:

            state = str(row[0])
            district = str(row[1])
            block = str(row[2])
            year = str(row[3])
            recharge = str(row[4])
            extractable = str(row[5])
            extraction = str(row[6])
            stage = str(row[7])
            category = str(row[8])

            searchable_text = f"""
            {state}
            {district}
            {block}
            {year}
            {recharge}
            {extractable}
            {extraction}
            {stage}
            {category}
            """.lower()

            score = 0

            for word in question_lower.split():

                word = word.strip(
                    ".,?!:;'\""
                )

                if len(word) > 2 and word in searchable_text:
                    score += 1

            if score > 0:

                matches.append(
                    (score, row)
                )

        matches.sort(
            key=lambda x: x[0],
            reverse=True
        )

        result = ""

        for score, row in matches[:10]:

            result += f"""
State: {row[0]}
District: {row[1]}
Block: {row[2]}
Year: {row[3]}
Recharge: {row[4]} BCM
Extractable Groundwater: {row[5]} BCM
Extraction: {row[6]} BCM
Stage of Extraction: {row[7]}%
Category: {row[8]}

"""

        return result

    finally:

        conn.close()


# =====================================================
# SPECIAL DATABASE QUERIES
# =====================================================

def special_database_query(question):

    q = question.lower()

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # ---------------------------------------------
        # HIGHEST STAGE
        # ---------------------------------------------

        if (
            "highest" in q
            and (
                "stage" in q
                or "extraction" in q
            )
        ):

            cursor.execute("""
            SELECT
                state,
                district,
                block,
                stage_percent,
                category
            FROM assessments
            ORDER BY stage_percent DESC
            LIMIT 1
            """)

            row = cursor.fetchone()

            if row:

                return f"""
The location with the highest groundwater
stage of extraction is:

District: {row[1]}
State: {row[0]}
Block: {row[2]}
Stage of Extraction: {row[3]}%
Category: {row[4]}
"""


        # ---------------------------------------------
        # LOWEST STAGE
        # ---------------------------------------------

        if (
            "lowest" in q
            and (
                "stage" in q
                or "extraction" in q
            )
        ):

            cursor.execute("""
            SELECT
                state,
                district,
                block,
                stage_percent,
                category
            FROM assessments
            ORDER BY stage_percent ASC
            LIMIT 1
            """)

            row = cursor.fetchone()

            if row:

                return f"""
The location with the lowest groundwater
stage of extraction is:

District: {row[1]}
State: {row[0]}
Block: {row[2]}
Stage of Extraction: {row[3]}%
Category: {row[4]}
"""


        # ---------------------------------------------
        # OVER-EXPLOITED
        # ---------------------------------------------

        if (
            "over-exploited" in q
            or "over exploited" in q
        ):

            cursor.execute("""
            SELECT
                state,
                district,
                block,
                stage_percent
            FROM assessments
            WHERE category = 'Over-Exploited'
            """)

            rows = cursor.fetchall()

            if rows:

                answer = "Over-exploited areas:\n\n"

                for row in rows:

                    answer += (
                        f"- {row[1]}, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer


        # ---------------------------------------------
        # SAFE AREAS
        # ---------------------------------------------

        if (
            "safe areas" in q
            or "which areas are safe" in q
        ):

            cursor.execute("""
            SELECT
                state,
                district,
                block,
                stage_percent
            FROM assessments
            WHERE category = 'Safe'
            """)

            rows = cursor.fetchall()

            if rows:

                answer = "Safe areas:\n\n"

                for row in rows:

                    answer += (
                        f"- {row[1]}, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer


        # ---------------------------------------------
        # CRITICAL AREAS
        # ---------------------------------------------

        if (
            "critical areas" in q
            or "which areas are critical" in q
        ):

            cursor.execute("""
            SELECT
                state,
                district,
                block,
                stage_percent
            FROM assessments
            WHERE category = 'Critical'
            """)

            rows = cursor.fetchall()

            if rows:

                answer = "Critical areas:\n\n"

                for row in rows:

                    answer += (
                        f"- {row[1]}, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer

        return ""

    finally:

        conn.close()


# =====================================================
# SEARCH PDF
# =====================================================

def search_pdf(question):

    pdf_text = st.session_state.pdf_text

    if not pdf_text:
        return ""

    words = [
        word.strip(
            ".,?!:;'\""
        ).lower()

        for word in question.split()

        if len(word) > 2
    ]

    paragraphs = pdf_text.split("\n\n")

    matches = []

    for paragraph in paragraphs:

        paragraph_lower = paragraph.lower()

        score = 0

        for word in words:

            if word in paragraph_lower:
                score += 1

        if score > 0:

            matches.append(
                (score, paragraph)
            )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    if not matches:
        return ""

    context = ""

    for score, paragraph in matches[:8]:

        context += (
            paragraph + "\n\n"
        )

    return context


# =====================================================
# OPENAI ANSWER
# =====================================================

def ai_answer(question, context):

    prompt = f"""
You are an AI assistant for the INGRES project.

Use the provided context to answer the
user's question.

CONTEXT:
{context}

USER QUESTION:
{question}

Rules:
- Do not invent facts.
- Use the provided information.
- Give a clear and helpful answer.
"""

    response = client.responses.create(
        model="gpt-5.6",
        input=prompt
    )

    return response.output_text.strip()


# =====================================================
# TAVILY WEB SEARCH
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
                "Summary:\n"
                + data["answer"]
                + "\n\n"
            )

        for item in data.get(
            "results",
            []
        ):

            result += (
                f"Title: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"Content: {item.get('content', '')}\n\n"
            )

        return result

    except Exception:

        return ""


# =====================================================
# MAIN QUESTION ROUTER
# =====================================================

def process_question(question):

    # =================================================
    # 1. SPECIAL DATABASE QUERY
    # =================================================

    result = special_database_query(
        question
    )

    if result:

        return result


    # =================================================
    # 2. FAQ DATABASE
    # =================================================

    faq_context = search_faq(
        question
    )

    if faq_context:

        return faq_context


    # =================================================
    # 3. ASSESSMENT DATABASE
    # =================================================

    assessment_context = search_assessments(
        question
    )

    if assessment_context:

        return assessment_context


    # =================================================
    # 4. PDF
    # =================================================

    pdf_context = search_pdf(
        question
    )

    if pdf_context:

        return ai_answer(
            question,
            pdf_context
        )


    # =================================================
    # 5. WEB SEARCH
    # =================================================

    web_context = search_web(
        question
    )

    if web_context:

        return ai_answer(
            question,
            web_context
        )


    # =================================================
    # 6. GENERAL AI
    # =================================================

    return ai_answer(
        question,
        "No relevant INGRES database or PDF information was found."
    )


# =====================================================
# CHAT INPUT
# =====================================================

if prompt := st.chat_input(
    "Ask your question..."
):

    if not prompt.strip():

        st.warning(
            "Please enter a valid question."
        )

        st.stop()


    # User message

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)


    # Assistant

    with st.chat_message("assistant"):

        try:

            answer = process_question(
                prompt
            )

        except Exception as e:

            answer = f"Error: {e}"

        st.markdown(answer)


    # Save assistant message

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )
