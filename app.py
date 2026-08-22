import streamlit as st
import sqlite3
import requests
import re

from pypdf import PdfReader


# =====================================================
# CONFIGURATION
# =====================================================

DB_NAME = "ingres.db"

TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]


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
# CHAT HISTORY
# =====================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =====================================================
# PDF UPLOAD
# =====================================================

st.sidebar.header("📄 INGRES PDF")

uploaded_file = st.sidebar.file_uploader(
    "Upload INGRES PDF",
    type=["pdf"]
)

if uploaded_file is not None:

    if st.sidebar.button("Add PDF to Knowledge Base"):

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
# CLEAR CHAT
# =====================================================

if st.sidebar.button("Clear Chat"):

    st.session_state.messages = []

    st.rerun()


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_connection():

    return sqlite3.connect(DB_NAME)


# =====================================================
# GET ALL ASSESSMENTS
# =====================================================

def get_all_assessments():

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

        return cursor.fetchall()

    finally:

        conn.close()


# =====================================================
# FIND LOCATION
# =====================================================

def find_location(question):

    q = question.lower()

    rows = get_all_assessments()

    matches = []

    for row in rows:

        state = str(row[0]).lower()
        district = str(row[1]).lower()
        block = str(row[2]).lower()

        score = 0

        if district in q:
            score += 100

        if block in q:
            score += 80

        if state in q:
            score += 30

        if score > 0:

            matches.append(
                (score, row)
            )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    if matches:

        return [
            row
            for score, row in matches
        ]

    return []


# =====================================================
# FORMAT ASSESSMENT
# =====================================================

def format_assessment(row):

    return f"""
### 📍 Groundwater Assessment

**State:** {row[0]}

**District:** {row[1]}

**Block:** {row[2]}

**Year:** {row[3]}

**Groundwater Recharge:** {row[4]} BCM

**Extractable Groundwater:** {row[5]} BCM

**Groundwater Extraction:** {row[6]} BCM

**Stage of Extraction:** {row[7]}%

**Category:** {row[8]}
"""


# =====================================================
# SEARCH ASSESSMENT DATABASE
# =====================================================

def search_assessments(question):

    matches = find_location(question)

    if matches:

        answer = ""

        for row in matches:

            answer += format_assessment(row)

            answer += "\n---\n"

        return answer

    return ""


# =====================================================
# FAQ SEARCH
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

    finally:

        conn.close()

    q = question.lower()

    # -------------------------------------------------
    # DIRECT FAQ MATCHING
    # -------------------------------------------------

    best_match = None

    best_score = 0

    for faq_question, faq_answer in rows:

        faq_q = faq_question.lower()

        score = 0

        # Exact phrase
        if faq_q in q:

            score += 100

        # Important keywords
        words = re.findall(
            r"[a-zA-Z]+",
            faq_q
        )

        for word in words:

            if len(word) > 3 and word in q:

                score += 10

        if score > best_score:

            best_score = score

            best_match = (
                faq_question,
                faq_answer
            )

    if best_match and best_score > 0:

        return (
            f"**{best_match[0]}**\n\n"
            f"{best_match[1]}"
        )

    return ""


# =====================================================
# SPECIAL DATABASE QUESTIONS
# =====================================================

def special_database_query(question):

    q = question.lower()

    conn = get_connection()

    cursor = conn.cursor()

    try:

        # =================================================
        # HIGHEST EXTRACTION
        # =================================================

        if (
            "highest" in q
            and (
                "extraction" in q
                or "stage" in q
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
### 🔴 Highest Groundwater Extraction

**District:** {row[1]}

**State:** {row[0]}

**Block:** {row[2]}

**Stage of Extraction:** {row[3]}%

**Category:** {row[4]}
"""


        # =================================================
        # LOWEST EXTRACTION
        # =================================================

        if (
            "lowest" in q
            and (
                "extraction" in q
                or "stage" in q
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
### 🟢 Lowest Groundwater Extraction

**District:** {row[1]}

**State:** {row[0]}

**Block:** {row[2]}

**Stage of Extraction:** {row[3]}%

**Category:** {row[4]}
"""


        # =================================================
        # OVER-EXPLOITED
        # =================================================

        if (
            "over-exploited" in q
            or "over exploited" in q
            or "overexploited" in q
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

                answer = """
### 🔴 Over-Exploited Areas

"""

                for row in rows:

                    answer += (
                        f"- **{row[1]}**, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer


        # =================================================
        # SAFE
        # =================================================

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

                answer = """
### 🟢 Safe Areas

"""

                for row in rows:

                    answer += (
                        f"- **{row[1]}**, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer


        # =================================================
        # CRITICAL
        # =================================================

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

                answer = """
### 🟠 Critical Areas

"""

                for row in rows:

                    answer += (
                        f"- **{row[1]}**, {row[0]} "
                        f"({row[2]}) — "
                        f"{row[3]}% extraction\n"
                    )

                return answer

        return ""

    finally:

        conn.close()


# =====================================================
# PDF SEARCH
# =====================================================

def search_pdf(question):

    pdf_text = st.session_state.pdf_text

    if not pdf_text:

        return ""

    question_words = re.findall(
        r"[a-zA-Z0-9]+",
        question.lower()
    )

    paragraphs = pdf_text.split("\n")

    matches = []

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if not paragraph:
            continue

        paragraph_lower = paragraph.lower()

        score = 0

        for word in question_words:

            if len(word) > 2:

                if word in paragraph_lower:

                    score += 1

        if score > 0:

            matches.append(
                (
                    score,
                    paragraph
                )
            )

    matches.sort(
        key=lambda x: x[0],
        reverse=True
    )

    if not matches:

        return ""

    answer = """
### 📄 Information from Uploaded INGRES PDF

"""

    for score, paragraph in matches[:10]:

        answer += (
            paragraph
            + "\n\n"
        )

    return answer


# =====================================================
# TAVILY WEB SEARCH
# =====================================================

def search_web(question):

    try:

        response = requests.post(

            "https://api.tavily.com/search",

            json={
                "api_key": TAVILY_API_KEY,
                "query": question,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True
            },

            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        answer = ""

        if data.get("answer"):

            answer += (
                "### 🌐 Web Research\n\n"
                + data["answer"]
                + "\n\n"
            )

        results = data.get(
            "results",
            []
        )

        if results:

            answer += "### Sources\n\n"

            for result in results:

                title = result.get(
                    "title",
                    ""
                )

                url = result.get(
                    "url",
                    ""
                )

                content = result.get(
                    "content",
                    ""
                )

                answer += (
                    f"**{title}**\n\n"
                    f"{content}\n\n"
                    f"{url}\n\n"
                )

        return answer

    except Exception as e:

        return (
            "Web search is currently unavailable."
        )


# =====================================================
# SIMPLE QUESTION UNDERSTANDING
# =====================================================

def general_database_answer(question):

    q = question.lower()

    # -------------------------------------------------
    # CATEGORY QUESTIONS
    # -------------------------------------------------

    if "category" in q:

        matches = find_location(question)

        if matches:

            answer = ""

            for row in matches:

                answer += (
                    f"**{row[1]}** is classified as "
                    f"**{row[8]}**.\n\n"
                )

            return answer


    # -------------------------------------------------
    # STAGE QUESTIONS
    # -------------------------------------------------

    if (
        "stage" in q
        or "percentage" in q
    ):

        matches = find_location(question)

        if matches:

            answer = ""

            for row in matches:

                answer += (
                    f"**{row[1]}** has a Stage of "
                    f"Extraction of **{row[7]}%**.\n\n"
                )

            return answer


    # -------------------------------------------------
    # RECHARGE QUESTIONS
    # -------------------------------------------------

    if "recharge" in q:

        matches = find_location(question)

        if matches:

            answer = ""

            for row in matches:

                answer += (
                    f"Groundwater recharge in "
                    f"**{row[1]}** is "
                    f"**{row[4]} BCM**.\n\n"
                )

            return answer


    # -------------------------------------------------
    # EXTRACTION QUESTIONS
    # -------------------------------------------------

    if "extraction" in q:

        matches = find_location(question)

        if matches:

            answer = ""

            for row in matches:

                answer += (
                    f"Groundwater extraction in "
                    f"**{row[1]}** is "
                    f"**{row[6]} BCM**.\n\n"
                )

            return answer


    return ""


# =====================================================
# MAIN ROUTER
# =====================================================

def process_question(question):

    # =================================================
    # 1. SPECIAL DATABASE
    # =================================================

    result = special_database_query(
        question
    )

    if result:

        return result


    # =================================================
    # 2. LOCATION / ASSESSMENT DATABASE
    # =================================================

    result = search_assessments(
        question
    )

    if result:

        return result


    # =================================================
    # 3. DATABASE-SPECIFIC QUESTIONS
    # =================================================

    result = general_database_answer(
        question
    )

    if result:

        return result


    # =================================================
    # 4. FAQ
    # =================================================

    result = search_faq(
        question
    )

    if result:

        return result


    # =================================================
    # 5. PDF
    # =================================================

    result = search_pdf(
        question
    )

    if result:

        return result


    # =================================================
    # 6. WEB
    # =================================================

    result = search_web(
        question
    )

    if result:

        return result


    # =================================================
    # 7. NOTHING FOUND
    # =================================================

    return """
I couldn't find relevant information in the
INGRES database, uploaded PDF, or web search.
"""


# =====================================================
# CHAT INPUT
# =====================================================

if prompt := st.chat_input(
    "Ask your INGRES question..."
):

    if not prompt.strip():

        st.warning(
            "Please enter a valid question."
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
                f"Database error: {e}"
            )

        st.markdown(answer)


    # -------------------------------------------------
    # SAVE
    # -------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
          )
