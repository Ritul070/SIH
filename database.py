import sqlite3


DB_NAME = "ingres.db"


# =====================================================
# CREATE DATABASE
# =====================================================

def create_database():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -------------------------------------------------
    # ASSESSMENTS TABLE
    # -------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        state TEXT,
        district TEXT,
        block TEXT,
        year INTEGER,
        recharge_bcm REAL,
        extractable_bcm REAL,
        extraction_bcm REAL,
        stage_percent REAL,
        category TEXT
    )
    """)

    # -------------------------------------------------
    # FAQ TABLE
    # -------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    )
    """)

    # -------------------------------------------------
    # INSERT DATA ONLY IF TABLE IS EMPTY
    # -------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) FROM assessments"
    )

    assessment_count = cursor.fetchone()[0]

    if assessment_count == 0:

        data = [

            (
                "Gujarat",
                "Anand",
                "Anand",
                2024,
                0.62,
                0.55,
                0.29,
                52.7,
                "Safe"
            ),

            (
                "Gujarat",
                "Kheda",
                "Nadiad",
                2024,
                0.74,
                0.66,
                0.48,
                72.7,
                "Semi-Critical"
            ),

            (
                "Gujarat",
                "Mehsana",
                "Mehsana",
                2024,
                0.81,
                0.73,
                0.76,
                104.1,
                "Over-Exploited"
            ),

            (
                "Gujarat",
                "Ahmedabad",
                "Daskroi",
                2024,
                0.91,
                0.82,
                0.68,
                82.9,
                "Critical"
            ),

            (
                "Gujarat",
                "Vadodara",
                "Savli",
                2024,
                0.76,
                0.69,
                0.41,
                59.4,
                "Safe"
            ),

            (
                "Rajasthan",
                "Jaipur",
                "Sanganer",
                2024,
                0.51,
                0.46,
                0.43,
                93.5,
                "Critical"
            ),

            (
                "Rajasthan",
                "Jodhpur",
                "Luni",
                2024,
                0.42,
                0.38,
                0.41,
                107.9,
                "Over-Exploited"
            ),

            (
                "Madhya Pradesh",
                "Indore",
                "Depalpur",
                2024,
                0.69,
                0.63,
                0.34,
                54.0,
                "Safe"
            )
        ]

        cursor.executemany("""
        INSERT INTO assessments (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)


    # -------------------------------------------------
    # FAQ DATA
    # -------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) FROM faq"
    )

    faq_count = cursor.fetchone()[0]

    if faq_count == 0:

        faq_data = [

            (
                "What is Stage of Extraction?",
                "Stage of Extraction is the percentage of groundwater extraction compared with the annual extractable groundwater resource."
            ),

            (
                "What does Safe mean?",
                "Safe indicates that groundwater extraction is within a sustainable level."
            ),

            (
                "What does Semi-Critical mean?",
                "Semi-Critical indicates that groundwater development requires careful management."
            ),

            (
                "What does Critical mean?",
                "Critical indicates a high level of groundwater development requiring groundwater management."
            ),

            (
                "What does Over-Exploited mean?",
                "Over-Exploited indicates that groundwater extraction has exceeded the annual extractable groundwater resource."
            ),

            (
                "What is groundwater recharge?",
                "Groundwater recharge is the process through which water enters and replenishes underground aquifers."
            )
        ]

        cursor.executemany("""
        INSERT INTO faq (
            question,
            answer
        )
        VALUES (?, ?)
        """, faq_data)


    conn.commit()
    conn.close()


# =====================================================
# RUN DATABASE CREATION
# =====================================================

create_database()


# =====================================================
# DATABASE QUERY FUNCTION
# =====================================================

def query_database(sql_query):

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:

        # Security: only SELECT
        if not sql_query.strip().lower().startswith("select"):

            return "Only SELECT queries are allowed."

        cursor.execute(sql_query)

        rows = cursor.fetchall()

        columns = [
            description[0]
            for description in cursor.description
        ]

        if not rows:

            return ""

        result = ""

        for row in rows:

            for column, value in zip(columns, row):

                result += f"{column}: {value}\n"

            result += "\n"

        return result

    except Exception as e:

        return f"Database error: {e}"

    finally:

        conn.close()
