    
import streamlit as st
import google.generativeai as genai
import requests
import json


# =====================================================
# CONFIGURATION
# =====================================================

API_KEY = st.secrets["API_KEY"]

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

st.sidebar.header("📚 Knowledge Base")

uploaded_file = st.sidebar.file_uploader(
    "Upload PDF",
    type=["pdf"]
)


if uploaded_file is not None:

    if st.sidebar.button("Add PDF to Knowledge Base"):

        try:

            # Your existing PDF/database function
            from database import add_pdf

            with st.spinner("Processing PDF..."):

                chunks = add_pdf(uploaded_file)

            st.sidebar.success(
                f"PDF added successfully. "
                f"{chunks} chunks stored."
            )

        except Exception as e:

            st.sidebar.error(
                f"PDF error: {e}"
            )


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
                "Summary:\n"
                + data["answer"]
                + "\n\n"
            )

        for item in data.get("results", []):

            result += (
                f"Title: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"Content: {item.get('content', '')}\n\n"
            )

        return result

    except Exception:

        return ""


# =====================================================
# MAIN AI TOOL SYSTEM
# =====================================================

def process_question(prompt):

    # -------------------------------------------------
    # IMPORTANT:
    # FIRST CHECK THE KNOWLEDGE BASE
    # -------------------------------------------------

    try:

        context = search_knowledge(prompt)

    except Exception:

        context = ""


    # -------------------------------------------------
    # IF PDF DATABASE HAS INFORMATION
    # -------------------------------------------------

    if context and context.strip():

        database_prompt = f"""
You are an AI assistant for the INGRES project.

The user has asked a question.

The following information was retrieved
from the uploaded PDF knowledge base:

-------------------------
PDF CONTEXT
-------------------------

{context}

-------------------------
USER QUESTION
-------------------------

{prompt}

-------------------------
INSTRUCTIONS
-------------------------

Answer the user's question using the retrieved
PDF information.

Rules:

1. Use the PDF context as the primary source.
2. Do not invent information.
3. Do not ignore information present in the context.
4. Give a direct and helpful answer.
5. You may combine information from different
   retrieved sections.
6. If the context genuinely does not contain
   the answer, say that the uploaded documents
   do not contain enough information.

Answer the user now.
"""

        response = model.generate_content(
            database_prompt
        )

        return response.text.strip()


    # -------------------------------------------------
    # DATABASE DID NOT HAVE RELEVANT INFORMATION
    # -------------------------------------------------

    system_prompt = f"""
You are an AI assistant for the INGRES project.

You have access to these tools:

1. calculator
2. word_counter
3. database
4. knowledge_base
5. web_search

The knowledge_base was already checked for this
question and did not contain relevant information.

Choose the correct tool.

Return ONLY valid JSON.

Examples:

For mathematics:
{{
    "tool": "calculator",
    "input": "25 * 5"
}}

For word counting:
{{
    "tool": "word_counter",
    "input": "text here"
}}

For structured project database:
{{
    "tool": "database",
    "input": "SELECT ..."
}}

For current/latest information:
{{
    "tool": "web_search",
    "input": "search query"
}}

If no tool is required:
{{
    "tool": "none",
    "input": ""
}}

User question:

{prompt}
"""


    response = model.generate_content(
        system_prompt
    )

    ai_thought = response.text.strip()


    # -------------------------------------------------
    # REMOVE MARKDOWN CODE BLOCK
    # -------------------------------------------------

    if ai_thought.startswith("```"):

        lines = ai_thought.split("\n")

        ai_thought = "\n".join(
            lines[1:-1]
        ).strip()


    # -------------------------------------------------
    # PARSE JSON
    # -------------------------------------------------

    try:

        command = json.loads(ai_thought)

        tool_name = command.get("tool")

        tool_input = command.get(
            "input",
            ""
        )


    except Exception:

        # If router fails, simply ask Gemini
        response = model.generate_content(
            prompt
        )

        return response.text.strip()


    # =================================================
    # CALCULATOR
    # =================================================

    if tool_name == "calculator":

        return calculate_math(
            tool_input
        )


    # =================================================
    # WORD COUNTER
    # =================================================

    elif tool_name == "word_counter":

        return count_words(
            tool_input
        )


    # =================================================
    # SQL DATABASE
    # =================================================

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


    # =================================================
    # KNOWLEDGE BASE
    # =================================================

    elif tool_name == "knowledge_base":

        context = search_knowledge(
            tool_input
        )

        if not context or not context.strip():

            return (
                "I could not find relevant "
                "information in the uploaded "
                "documents."
            )


        answer_prompt = f"""

You are an AI assistant for INGRES.

Answer the user's question using the
retrieved information from the uploaded
PDF documents.

IMPORTANT:

- Use the retrieved PDF information.
- Do not make up information.
- Answer directly and clearly.
- Do not claim information is missing if
  it is present in the retrieved context.
- If the answer genuinely is not present,
  say that the uploaded documents do not
  contain enough information.

Retrieved PDF Context:

{context}

User Question:

{prompt}

Give a clear and helpful answer.
"""


        answer_response = model.generate_content(
            answer_prompt
        )

        return answer_response.text.strip()


    # =================================================
    # WEB SEARCH
    # =================================================

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

Answer the user's question using the
web research below.

WEB RESEARCH:

{web_context}

USER QUESTION:

{prompt}

Give a clear and accurate answer.
"""

        response = model.generate_content(
            web_prompt
        )

        return response.text.strip()


    # =================================================
    # NORMAL GEMINI
    # =================================================

    else:

        response = model.generate_content(
            prompt
        )

        return response.text.strip()


# =====================================================
# CHAT INPUT
# =====================================================

if prompt := st.chat_input(
    "Ask something..."
):

    # -------------------------------------------------
    # SAVE USER MESSAGE
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
    # GENERATE RESPONSE
    # -------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner(
            "Thinking..."
        ):

            try:

                answer = process_question(
                    prompt
                )

            except Exception as e:

                answer = (
                    f"Error while processing "
                    f"your question: {e}"
                )


        st.markdown(answer)


    # -------------------------------------------------
    # SAVE ASSISTANT MESSAGE
    # -------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )


