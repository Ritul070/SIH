import streamlit as st
import google.generativeai as genai
import requests
import json


# =====================================================
# CONFIGURATION
# =====================================================

API_KEY = st.secrets["API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")


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
# CHAT HISTORY
# =====================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# =====================================================
# PDF UPLOAD
# =====================================================

st.sidebar.header("📚 PDF Knowledge Base")

uploaded_file = st.sidebar.file_uploader(
    "Upload PDF",
    type=["pdf"]
)

if uploaded_file is not None:

    st.sidebar.success(
        f"PDF uploaded: {uploaded_file.name}"
    )

    # IMPORTANT:
    # This keeps PDF handling separate from
    # your built-in database.py.
    #
    # search_knowledge() should use this uploaded
    # PDF when searching.
    #
    # If your existing search_knowledge() already
    # handles uploaded PDFs, leave it as it is.


# =====================================================
# WEB SEARCH
# =====================================================

def search_web(query):

    try:

        url = "https://api.tavily.com/search"

        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5,
            "include_answer": True
        }

        response = requests.post(
            url,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        combined_text = ""

        if data.get("answer"):

            combined_text += (
                "Summary:\n"
                + data["answer"]
                + "\n\n"
            )

        if data.get("results"):

            combined_text += "Sources:\n\n"

            for result in data["results"]:

                combined_text += (
                    f"Title: {result.get('title', '')}\n"
                    f"URL: {result.get('url', '')}\n"
                    f"Content: {result.get('content', '')}\n\n"
                )

        return combined_text

    except Exception as e:

        return ""


# =====================================================
# CHECK IF DATABASE RESULT IS ACTUALLY RELEVANT
# =====================================================

def check_database_relevance(
    question,
    database_result
):

    if not database_result:
        return False

    relevance_prompt = f"""
You are checking whether the following
INGRES database result actually answers
the user's question.

USER QUESTION:
{question}

DATABASE RESULT:
{database_result}

Reply ONLY:

YES

if the database result contains enough
information to answer the question.

Reply ONLY:

NO

if the result is unrelated or insufficient.
"""

    try:

        response = model.generate_content(
            relevance_prompt
        )

        result = response.text.strip().upper()

        return result == "YES"

    except Exception:

        return False


# =====================================================
# CHECK PDF RELEVANCE
# =====================================================

def check_pdf_relevance(
    question,
    pdf_context
):

    if not pdf_context:
        return False

    relevance_prompt = f"""
You are checking whether the following
uploaded PDF information answers the
user's question.

USER QUESTION:
{question}

PDF INFORMATION:
{pdf_context}

Reply ONLY:

YES

if the PDF information contains enough
information to answer the question.

Reply ONLY:

NO

if the information is unrelated or insufficient.
"""

    try:

        response = model.generate_content(
            relevance_prompt
        )

        result = response.text.strip().upper()

        return result == "YES"

    except Exception:

        return False


# =====================================================
# ANSWER FROM DATABASE
# =====================================================

def answer_from_database(
    question,
    database_result
):

    prompt = f"""
You are an AI assistant for the INGRES project.

Answer the user's question using ONLY the
provided INGRES database information.

DATABASE INFORMATION:

{database_result}

USER QUESTION:

{question}

Rules:

- Use the database information.
- Do not invent facts.
- Give a clear and direct answer.
- Do not mention that you are using a database
  unless necessary.
"""

    response = model.generate_content(prompt)

    return response.text.strip()


# =====================================================
# ANSWER FROM PDF
# =====================================================

def answer_from_pdf(
    question,
    pdf_context
):

    prompt = f"""
You are an AI assistant for INGRES.

Answer the user's question using ONLY the
retrieved information from the uploaded PDF.

RETRIEVED PDF INFORMATION:

{pdf_context}

USER QUESTION:

{question}

Rules:

- Use the retrieved PDF information.
- Do not invent facts.
- Give a clear and direct answer.
- If the information genuinely isn't present,
  say that the uploaded document does not
  contain enough information.
"""

    response = model.generate_content(prompt)

    return response.text.strip()


# =====================================================
# NORMAL TOOL ROUTER
# =====================================================

def run_other_tools(prompt):

    system_prompt = f"""
You are an AI assistant.

The built-in INGRES database and uploaded PDF
knowledge base have already been checked.

Neither contains enough information to answer
the user's question.

Choose the appropriate tool.

Available tools:

1. calculator
2. word_counter
3. database
4. web_search
5. none

Return ONLY valid JSON.

Examples:

Calculator:
{{
    "tool": "calculator",
    "input": "25 * 10"
}}

Word counter:
{{
    "tool": "word_counter",
    "input": "This is some text"
}}

Database:
{{
    "tool": "database",
    "input": "SELECT * FROM students"
}}

Web:
{{
    "tool": "web_search",
    "input": "latest information about ..."
}}

Normal answer:
{{
    "tool": "none",
    "input": ""
}}

USER QUESTION:

{prompt}
"""

    response = model.generate_content(
        system_prompt
    )

    ai_thought = response.text.strip()


    # Remove ```json ... ```
    if ai_thought.startswith("```"):

        lines = ai_thought.split("\n")

        ai_thought = "\n".join(
            lines[1:-1]
        ).strip()


    try:

        command = json.loads(ai_thought)

        tool_name = command.get("tool")

        tool_input = command.get(
            "input",
            ""
        )


        # =============================================
        # CALCULATOR
        # =============================================

        if tool_name == "calculator":

            return calculate_math(
                tool_input
            )


        # =============================================
        # WORD COUNTER
        # =============================================

        elif tool_name == "word_counter":

            return count_words(
                tool_input
            )


        # =============================================
        # SQL DATABASE
        # =============================================

        elif tool_name == "database":

            sql_query = tool_input.strip()

            if not sql_query.lower().startswith(
                "select"
            ):

                return (
                    "Database security error: "
                    "only SELECT queries are allowed."
                )

            return query_database(
                sql_query
            )


        # =============================================
        # WEB SEARCH
        # =============================================

        elif tool_name == "web_search":

            web_context = search_web(
                tool_input
            )

            if not web_context:

                return (
                    "I could not perform the "
                    "web search right now."
                )

            web_prompt = f"""
You are a research assistant.

WEB RESEARCH:

{web_context}

USER QUESTION:

{prompt}

Answer clearly and accurately using
the provided research.
"""

            response = model.generate_content(
                web_prompt
            )

            return response.text.strip()


        # =============================================
        # NORMAL GEMINI
        # =============================================

        else:

            response = model.generate_content(
                prompt
            )

            return response.text.strip()


    except Exception:

        response = model.generate_content(
            prompt
        )

        return response.text.strip()


# =====================================================
# MAIN QUESTION PROCESSING
# =====================================================

def process_question(prompt):

    # =================================================
    # STEP 1 — BUILT-IN DATABASE FIRST
    # =================================================

    with st.spinner(
        "🔎 Checking INGRES database..."
    ):

        try:

            database_result = query_database(
                prompt
            )

        except Exception:

            database_result = None


    # Check whether database actually answers it
    if database_result:

        database_has_answer = (
            check_database_relevance(
                prompt,
                database_result
            )
        )

    else:

        database_has_answer = False


    # =================================================
    # DATABASE HAS ANSWER
    # =================================================

    if database_has_answer:

        with st.spinner(
            "🤖 Answering from INGRES database..."
        ):

            return answer_from_database(
                prompt,
                database_result
            )


    # =================================================
    # STEP 2 — CHECK UPLOADED PDF
    # =================================================

    with st.spinner(
        "📄 Checking uploaded PDF..."
    ):

        try:

            pdf_context = search_knowledge(
                prompt
            )

        except Exception:

            pdf_context = ""


    # Check PDF relevance
    if pdf_context:

        pdf_has_answer = check_pdf_relevance(
            prompt,
            pdf_context
        )

    else:

        pdf_has_answer = False


    # =================================================
    # PDF HAS ANSWER
    # =================================================

    if pdf_has_answer:

        with st.spinner(
            "🤖 Answering from PDF..."
        ):

            return answer_from_pdf(
                prompt,
                pdf_context
            )


    # =================================================
    # STEP 3 — NOTHING FOUND
    # =================================================

    with st.spinner(
        "🧠 Choosing the next tool..."
    ):

        return run_other_tools(
            prompt
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


    # =================================================
    # SHOW USER MESSAGE
    # =================================================

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)


    # =================================================
    # GENERATE ANSWER
    # =================================================

    with st.chat_message("assistant"):

        try:

            answer = process_question(
                prompt
            )

        except Exception as e:

            answer = (
                f"An error occurred: {e}"
            )

        st.markdown(answer)


    # =================================================
    # SAVE ANSWER
    # =================================================

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
                            )


