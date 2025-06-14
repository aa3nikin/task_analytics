import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re

# Define sanitization function
def sanitize_str(s):
    s = s.strip().capitalize()
    s = re.sub(r'\s{2,}', ' ', s)
    if s in col_name_mapping:
        s = col_name_mapping[s]
    return s

# Define discount function for inflation adjustment
def discount(year_from, year_to, amount):
    result = amount
    for year in range(year_from, year_to, -1):
        if year in infl.index:
            result /= 1.0 + infl.loc[year] / 100.0
        else:
            st.error(f"Inflation data missing for year {year}")
            return None
    return result

# Data loading and preprocessing function
@st.cache_data
def load_data():
    try:
        new_data = pd.read_excel('Tab3_zpl_2024.xlsx', sheet_name='с 2017 г.', header=4)
        old_data = pd.read_excel('Tab3_zpl_2024.xlsx', sheet_name='2000-2016 гг.', header=2)
        infl = pd.read_excel('inflation.xlsx', index_col='Год')
        infl = infl['Всего'].iloc[1:].sort_index()
        infl.name = 'Инфляция'
    except FileNotFoundError as e:
        st.error(f"Не удалось загрузить файл: {e}")
        return None, None

    # Set column names
    new_data.columns = ['Отрасль'] + [str(x) for x in range(2017, 2025)]
    old_data.columns = ['Отрасль'] + [str(x) for x in range(2000, 2017)]

    # Drop rows with any NaN values
    new_data = new_data.dropna(how='any')
    old_data = old_data.dropna(how='any')

    # Calculate average salaries
    new_avg = pd.DataFrame([['Средняя'] + new_data.iloc[:, 1:].mean().tolist()], columns=new_data.columns)
    old_avg = pd.DataFrame([['Средняя'] + old_data.iloc[:, 1:].mean().tolist()], columns=old_data.columns)

    # Append averages
    new_data = pd.concat([new_data, new_avg], ignore_index=True)
    old_data = pd.concat([old_data, old_avg], ignore_index=True)

    # Industry name mapping
    global col_name_mapping
    col_name_mapping = {
        'Рыболовство, рыбоводство': 'Рыболовство и рыбоводство',
        'Производство кожи, изделий из кожи и производство обуви': 'Производство кожи и изделий из кожи',
        'Производство резиновых и пластмассовых изделий': 'Производство резиновых и пластмассовых изделий',
        'Торговля оптовая и розничная; ремонт автотранспортных средств и мотоциклов': 'Оптовая и розничная торговля; ремонт автотранспортных средств, мотоциклов, бытовых изделий и предметов личного пользования',
        'Деятельность финансовая и страховая': 'Финансовая деятельность',
        'Государственное управление и обеспечение военной безопасности; социальное обеспечение': 'Государственное управление и обеспечение военной безопасности; социальное страхование',
        'Деятельность в области здравоохранения и социальных услуг': 'Здравоохранение и предоставление социальных услуг',
    }

    # Sanitize industry names
    new_data['Отрасль'] = new_data['Отрасль'].apply(sanitize_str)
    old_data['Отрасль'] = old_data['Отрасль'].apply(sanitize_str)

    # Merge datasets
    data = old_data.merge(new_data, on='Отрасль', how='inner')
    data = data.set_index('Отрасль')

    return data, infl

# Load data
data, infl = load_data()
if data is None or infl is None:
    st.stop()

# Calculate real salaries (in 2000 rubles)
years = [str(year) for year in range(2000, 2024)]
data_2000 = pd.DataFrame(index=data.index)
for year in years:
    data_2000[year] = data[year].apply(lambda x: discount(int(year), 2000, x))

# Calculate yearly percentage changes
changes = pd.DataFrame(index=data.index)
for year in range(2001, 2024):
    prev_year = year - 1
    if str(year) in data_2000.columns and str(prev_year) in data_2000.columns:
        changes[str(year)] = (data_2000[str(year)] / data_2000[str(prev_year)] - 1) * 100
    else:
        changes[str(year)] = np.nan

# Streamlit app layout
st.title("Анализ зарплат в России с учетом инфляции")

# Sidebar for industry selection
st.sidebar.header("Настройки")
industries = data.index.unique().tolist()
selected_industries = st.sidebar.multiselect(
    "Выберите отрасли",
    industries,
    default=["Образование", "Рыболовство и рыбоводство", "Строительство", "Средняя"]
)

# Data display
with st.expander("Просмотреть исходные данные"):
    st.subheader("Данные по зарплатам")
    st.dataframe(data)
    st.subheader("Данные по инфляции")
    st.dataframe(infl)

if not selected_industries:
    st.warning("Пожалуйста, выберите хотя бы одну отрасль для анализа.")
else:
    # Nominal salaries plot
    st.subheader("Номинальные зарплаты по годам")
    fig, ax = plt.subplots(figsize=(12, 7))
    for idx, industry in enumerate(selected_industries):
        ax.plot(years, data.loc[industry, years], label=industry, color=plt.cm.tab10(idx))
    ax.set_title("Номинальные зарплаты")
    ax.set_xlabel("Год")
    ax.set_ylabel("Зарплата, руб.")
    ax.legend()
    ax.grid(True)
    ax.set_xticks(years[::3])
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

    st.markdown("""
    **Выводы:**
    - Номинальные зарплаты демонстрируют устойчивый рост с 2000 по 2023 год во всех отраслях.
    - Рыболовство и рыбоводство с 2015 года обгоняет среднюю зарплату, в то время как образование и строительство остаются ниже среднего.
    """)

    # Real salaries plot
    st.subheader("Реальные зарплаты (в рублях 2000 года)")
    fig, ax = plt.subplots(figsize=(12, 7))
    for idx, industry in enumerate(selected_industries):
        ax.plot(years, data_2000.loc[industry, years], label=industry, color=plt.cm.tab10(idx))
    ax.set_title("Реальные зарплаты с учетом инфляции")
    ax.set_xlabel("Год")
    ax.set_ylabel("Зарплата, руб. (2000)")
    ax.set_yscale('log')
    ax.legend()
    ax.grid(True)
    ax.set_xticks(years[::3])
    ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig)

    st.markdown("""
    **Выводы:**
    - Реальные зарплаты растут, но темпы роста различаются: строительство и рыболовство показывают более быстрый рост, образование отстает.
    - Кризисные периоды (2009, 2014-2015) видны как замедление роста или падение.
    """)

    # Yearly changes plot
    st.subheader("Годовые изменения реальных зарплат (%)")
    fig, ax = plt.subplots(figsize=(14, 7))
    bar_width = 0.15
    change_years = [str(y) for y in range(2001, 2024)]
    for idx, industry in enumerate(selected_industries):
        y_values = changes.loc[industry, change_years].values
        positions = np.arange(2001, 2024) + (idx - len(selected_industries)/2) * bar_width
        colors = ['#2ca02c' if v >= 0 else '#d62728' for v in y_values]
        ax.bar(positions, y_values, width=bar_width, color=colors, label=industry)
    ax.set_title("Годовые изменения реальных зарплат")
    ax.set_xlabel("Год")
    ax.set_ylabel("Изменение, %")
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.grid(True, axis='y')
    ax.set_xticks(np.arange(2001, 2024))
    ax.tick_params(axis='x', rotation=45)
    ax.legend()
    st.pyplot(fig)

    st.markdown("""
    **Выводы:**
    - Рыболовство: высокая волатильность (пики до +25%, падения до -15%).
    - Строительство: чувствительность к кризисам (падения в 2009, 2015).
    - Образование: стабильная, но низкая динамика изменений.
    - Кризис 2009 года: сильное падение во всех отраслях, восстановление в 2010-2011.
    - 2020 год: отсутствие значительного падения несмотря на пандемию.
    """)
