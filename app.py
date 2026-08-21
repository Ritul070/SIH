import streamlit as st
import google.generativeai as genai
import json
import sqlite3
import chromadb

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer




API_KEY = st.secrets["API_KEY"]

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")




chroma_client = chromadb.PersistentClient(
    path="chroma_data"
)

collection = chroma_client.get_or_create_collection(
    name="ingres_knowledge"
)



@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


embedding_model = load_embedding_model()




uploaded_file = st.sidebar.file_uploader(
    "Upload INGRES PDF",
    type=["pdf"]
)

if uploaded_file is not None:

    if st.sidebar.button("Add PDF to Knowledge Base"):

        try:

            # Read PDF
            reader = PdfReader(uploaded_file)

            full_text = ""

            for page in reader.pages:

                text = page.extract_text()

                if text:
                    full_text += text + "\n"

            

            chunk_size = 1000
            overlap = 200

            chunks = []

            start = 0

            while start < len(full_text):

                end = start + chunk_size

                chunk = full_text[start:end].strip()

                if chunk:
                    chunks.append(chunk)

                start += chunk_size - overlap

           

            embeddings = embedding_model.encode(
                chunks
            ).tolist()

      

            ids = [
                f"{uploaded_file.name}_{i}"
                for i in range(len(chunks))
            ]

         

            collection.upsert(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=[
                    {
                        "source": uploaded_file.name
                    }
                    for _ in chunks
                ]
            )

            st.sidebar.success(
                f"PDF added successfully! "
                f"{len(chunks)} chunks stored."
            )

        except Exception as e:

            st.sidebar.error(
                f"PDF Error: {e}"
            )




def calculate_math(expression):

    try:
        return str(eval(expression))

    except Exception as e:
        return f"Math Error: {e}"


def count_words(text):

    return str(len(text.split()))




def query_database(sql_query):

    try:

        conn = sqlite3.connect("ingres.db")

        cursor = conn.cursor()

        cursor.execute(sql_query)

        rows = cursor.fetchall()

        conn.close()

        if not rows:
            return "No matching data found."

        return str(rows)

    except Exception as e:

        return f"Database Error: {e}"



def search_knowledge(question):

    try:

        # Convert question into embedding
        question_embedding = embedding_model.encode(
            [question]
        ).tolist()

        # Search ChromaDB
        results = collection.query(
            query_embeddings=question_embedding,
            n_results=5
        )

        documents = results.get(
            "documents",
            [[]]
        )[0]

        if not documents:

            return "No relevant information found."

        # Combine retrieved chunks
        context = "\n\n".join(documents)

        return context

    except Exception as e:

        return f"ChromaDB Error: {e}"



st.title("🤖 INGRES AI Virtual Assistant")

st.write(
    "I can answer INGRES questions using "
    "the database and uploaded PDF documents."
)



if "messages" not in st.session_state:

    st.session_state.messages = []


for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])




prompt = st.chat_input(
    "Ask me anything..."
)


if prompt:



    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)




    system_prompt = """

You are an AI routing agent for the INGRES
(India Ground Water Resource Estimation System)
virtual assistant.

Your job is to understand the user's question
and select the correct tool.

You MUST reply ONLY with a JSON object.

Do not write any explanation outside JSON.


AVAILABLE TOOLS:


1. calculator

Use this for mathematical calculations.

Example:

{
    "tool": "calculator",
    "input": "45 * 32"
}


2. word_counter

Use this when the user asks to count words.

Example:

{
    "tool": "word_counter",
    "input": "hello world"
}


3. database

Use this when the user asks about structured
INGRES groundwater data.

The SQLite database contains:

assessments(
    id,
    state,
    district,
    block,
    year,
    recharge_bcm,
    extractable_bcm,
    extraction_bcm,
    stage_percent,
    category
)

Example:

User:
Which areas in Gujarat are over-exploited?

Output:

{
    "tool": "database",
    "input": "SELECT state, district, block, stage_percent, category FROM assessments WHERE state='Gujarat' AND category='Over-Exploited'"
}


User:
What is the groundwater extraction stage of Anand?

Output:

{
    "tool": "database",
    "input": "SELECT district, block, stage_percent, category FROM assessments WHERE district='Anand'"
}


4. knowledge_base

Use this when the user asks about information
that may be contained inside uploaded PDF documents.

Example:

User:
What does the uploaded INGRES report say about groundwater recharge?

Output:

{
    "tool": "knowledge_base",
    "input": "groundwater recharge"
}


5. none

Use this for normal conversation or greetings.

Example:

{
    "tool": "none",
    "input": "Hello! How can I help you?"
}


IMPORTANT:

For database queries, ONLY generate SELECT queries.

Never generate:

INSERT
UPDATE
DELETE
DROP
ALTER

Reply ONLY with valid JSON.


User Input:
"""




    full_prompt = system_prompt + prompt

    response = model.generate_content(
        full_prompt
    )

    ai_thought = response.text.strip()


   

    if ai_thought.startswith("```"):

        lines = ai_thought.split("\n")

        ai_thought = "\n".join(
            lines[1:-1]
        ).strip()



    try:

        command = json.loads(ai_thought)

        tool_name = command.get("tool")

        tool_input = command.get("input")




        if tool_name == "calculator":

            final_answer = calculate_math(
                tool_input
            )




        elif tool_name == "word_counter":

            final_answer = count_words(
                tool_input
            )




        elif tool_name == "database":

            sql_query = tool_input.strip()

            # Security check
            if not sql_query.lower().startswith("select"):

                final_answer = (
                    "Database security error: "
                    "only SELECT queries are allowed."
                )

            else:

                final_answer = query_database(
                    sql_query
                )




        elif tool_name == "knowledge_base":

            context = search_knowledge(
                tool_input
            )



            answer_prompt = f"""

You are an AI assistant for INGRES.

Answer the user's question using the
retrieved information from the uploaded
PDF documents.

Do not make up information.

If the retrieved information does not
contain the answer, clearly say that
the uploaded documents do not contain
enough information.

Retrieved PDF Context:

{context}


User Question:

{prompt}


Give a clear and helpful answer.
"""

            answer_response = model.generate_content(
                answer_prompt
            )

            final_answer = answer_response.text




        else:

            final_answer = tool_input


    except Exception as e:

        final_answer = (
            f"Agent failed.\n\n"
            f"AI raw output:\n{ai_thought}\n\n"
            f"Error: {e}"
        )




    with st.chat_message("assistant"):

        st.markdown(final_answer)



    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": final_answer
        }
    )