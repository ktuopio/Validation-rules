import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(
    page_title="Верификация номенклатуры",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🛠 Верификация номенклатуры по правилам")

# --- Вкладки ---
tab_nom, tab_rules = st.tabs(["Номенклатура", "Правила"])

df_nom = None
df_rules = None

# --- Вкладка Номенклатура ---
with tab_nom:
    st.header("📂 Файл номенклатуры")
    nomenclature_file = st.file_uploader("Загрузите Excel с номенклатурой", type=["xlsx"])
    if nomenclature_file:
        df_nom = pd.read_excel(nomenclature_file)
        st.success(f"Номенклатура загружена: {len(df_nom)} строк")
        st.dataframe(df_nom.head(10))

# --- Вкладка Правила ---
with tab_rules:
    st.header("📂 Файл правил")
    rules_file = st.file_uploader("Загрузите Excel с правилами", type=["xlsx"])
    if rules_file:
        df_rules = pd.read_excel(rules_file)
        st.success(f"Правила загружены: {len(df_rules)} правил")
        st.dataframe(df_rules.head(10))

# --- Функция верификации ---
def check_name_sequence(row, df_rules):
    manufacturer = row['Производитель']
    name = row['Наименование']

    rules_mf = df_rules[df_rules['Производитель'] == manufacturer].sort_values('Order')
    if rules_mf.empty:
        return "Неверифицированно"

    cursor = 0
    grouped = rules_mf.groupby('Order')['Code'].apply(list).to_dict()
    max_order = max(grouped.keys(), default=0)

    for order in range(1, max_order + 1):
        codes = grouped.get(order)
        if not codes:
            return "Неверифицированно"

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
            return "Неверифицированно"

    return "Верифицировано"

# --- Кнопка запуска ---
if st.button("🚀 Проверить номенклатуру"):
    if df_nom is None or df_rules is None:
        st.warning("Пожалуйста, загрузите оба файла: номенклатуру и правила.")
    else:
        with st.spinner("Идёт проверка..."):
            df_nom['Статус'] = df_nom.apply(lambda row: check_name_sequence(row, df_rules), axis=1)

        # --- Аналитика ---
        total = len(df_nom)
        verified = len(df_nom[df_nom['Статус'] == "Верифицировано"])
        not_verified = len(df_nom[df_nom['Статус'] == "Неверифицированно"])
        brands = df_nom['Производитель'].nunique()
        st.success("Проверка завершена!")

        st.subheader("📊 Общая аналитика")
        st.markdown(f"- Всего строк: **{total}**")
        st.markdown(f"- Верифицировано: **{verified}**")
        st.markdown(f"- Неверифицировано: **{not_verified}**")
        st.markdown(f"- Обработано брендов: **{brands}**")

        st.subheader("🔍 Детали по брендам")
        brand_stats = df_nom.groupby('Производитель')['Статус'].value_counts().unstack(fill_value=0)
        st.dataframe(brand_stats)

        # --- Сохранение файла ---
        towrite = BytesIO()
        df_nom.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="💾 Сохранить результат",
            data=towrite,
            file_name="Номенклатура_проверено.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
