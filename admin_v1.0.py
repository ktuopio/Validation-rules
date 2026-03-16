import streamlit as st
import pandas as pd
import re
from io import BytesIO
import psycopg2
from sqlalchemy import create_engine

# -----------------------------
# STREAMLIT SETTINGS
# -----------------------------

st.set_page_config(
    page_title="Верификация номенклатуры",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛠 Верификация номенклатуры по правилам")

# -----------------------------
# DATABASE SETTINGS
# -----------------------------

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "electronic_components_db"
DB_USER = "betehtina"
DB_PASSWORD = "cg6p8lh4"

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# -----------------------------
# TABS
# -----------------------------

tab_nom, tab_rules = st.tabs(["Номенклатура", "Правила"])

df_nom = None
df_rules = None

# -----------------------------
# NOMENCLATURE TAB
# -----------------------------

with tab_nom:

    st.header("📂 Номенклатура")

    source_nom = st.radio(
        "Источник номенклатуры",
        ["Excel файл", "PostgreSQL"]
    )

    if source_nom == "Excel файл":

        nomenclature_file = st.file_uploader(
            "Загрузите Excel с номенклатурой",
            type=["xlsx"]
        )

        if nomenclature_file:
            df_nom = pd.read_excel(nomenclature_file)
            st.success(f"Номенклатура загружена: {len(df_nom)} строк")
            st.dataframe(df_nom.head(10))

    if source_nom == "PostgreSQL":

        query = """
        SELECT
            id,
            mpn AS "Наименование",
            manufacturer_code AS "Производитель",
            verified
        FROM item_list
        """

        df_nom = pd.read_sql(query, engine)

        st.success(f"Загружено из PostgreSQL: {len(df_nom)} строк")
        st.dataframe(df_nom.head(10))

# -----------------------------
# RULES TAB
# -----------------------------

with tab_rules:

    st.header("📂 Правила")

    source_rules = st.radio(
        "Источник правил",
        ["Excel файл", "PostgreSQL"]
    )

    if source_rules == "Excel файл":

        rules_file = st.file_uploader(
            "Загрузите Excel с правилами",
            type=["xlsx"]
        )

        if rules_file:
            df_rules = pd.read_excel(rules_file)
            st.success(f"Правила загружены: {len(df_rules)}")
            st.dataframe(df_rules.head(10))

    if source_rules == "PostgreSQL":

        query = """
        SELECT *
        FROM item_rules
        """

        df_rules = pd.read_sql(query, engine)

        st.success(f"Правила загружены из PostgreSQL: {len(df_rules)}")
        st.dataframe(df_rules.head(10))

# -----------------------------
# VERIFICATION FUNCTION
# -----------------------------

def check_name_sequence(row, df_rules):

    manufacturer = row['Производитель']
    name = row['Наименование']

    rules_mf = df_rules[df_rules['Производитель'] == manufacturer].sort_values('Order')

    if rules_mf.empty:
        return "Неверифицировано"

    cursor = 0
    grouped = rules_mf.groupby('Order')['Code'].apply(list).to_dict()
    max_order = max(grouped.keys(), default=0)

    for order in range(1, max_order + 1):

        codes = grouped.get(order)

        if not codes:
            return "Неверифицировано"

        found = False

        for code in codes:

            code = str(code).strip()

            if not code or pd.isna(code):
                continue

            if re.fullmatch(r'1x\d+', code):

                match = re.match(r'1x\d+', name[cursor:])

                if match:
                    cursor += match.end()
                    found = True
                    break

            else:

                pos = name.find(code, cursor)

                if pos == cursor:
                    cursor += len(code)
                    found = True
                    break

        if not found:
            return "Неверифицировано"

    return "Верифицировано"


# -----------------------------
# RUN VERIFICATION
# -----------------------------

if st.button("🚀 Проверить номенклатуру"):

    if df_nom is None or df_rules is None:

        st.warning("Пожалуйста, загрузите номенклатуру и правила.")

    else:

        with st.spinner("Идёт проверка..."):

            df_nom['Статус'] = df_nom.apply(
                lambda row: check_name_sequence(row, df_rules),
                axis=1
            )

        st.success("Проверка завершена!")

        # -----------------------------
        # ANALYTICS
        # -----------------------------

        total = len(df_nom)
        verified = len(df_nom[df_nom['Статус'] == "Верифицировано"])
        not_verified = len(df_nom[df_nom['Статус'] == "Неверифицировано"])
        brands = df_nom['Производитель'].nunique()

        st.subheader("📊 Общая аналитика")

        st.markdown(f"Всего строк: **{total}**")
        st.markdown(f"Верифицировано: **{verified}**")
        st.markdown(f"Неверифицировано: **{not_verified}**")
        st.markdown(f"Брендов: **{brands}**")

        # -----------------------------
        # BRAND ANALYTICS
        # -----------------------------

        st.subheader("🔍 Детали по брендам")

        brand_stats = (
            df_nom.groupby('Производитель')['Статус']
            .value_counts()
            .unstack(fill_value=0)
        )

        st.dataframe(brand_stats)

        # -----------------------------
        # SAVE TO EXCEL
        # -----------------------------

        towrite = BytesIO()

        df_nom.to_excel(
            towrite,
            index=False,
            engine='openpyxl'
        )

        towrite.seek(0)

        st.download_button(
            label="💾 Скачать результат",
            data=towrite,
            file_name="Номенклатура_проверено.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # -----------------------------
        # UPDATE DATABASE
        # -----------------------------

        if st.button("⬆️ Обновить verified в PostgreSQL"):

            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )

            cursor = conn.cursor()

            updated = 0

            for _, row in df_nom.iterrows():

                verified_value = row["Статус"] == "Верифицировано"

                cursor.execute(
                    """
                    UPDATE item_list
                    SET verified = %s
                    WHERE id = %s
                    """,
                    (verified_value, row["id"])
                )

                updated += 1

            conn.commit()
            cursor.close()
            conn.close()

            st.success(f"Обновлено строк в базе: {updated}")
