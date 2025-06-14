import streamlit as st

st.set_page_config('Среднемесячная начисленная заработная плата', layout='wide', initial_sidebar_state='auto')

from data import SalaryService
service = SalaryService()
service.reload_data()

# --------------------------------------------------------------------------

default_select = ['Образование', 'Рыболовство и рыбыводство', 'Строительство', 'Средняя']

st.sidebar.header('Фильтр')

branches = st.sidebar.multiselect('Отрасли:', service.get_branches(), default_select)
years = st.sidebar.slider('За период:', min_value=2000, max_value=2023, value=(2000, 2023))
show_infl = st.sidebar.checkbox('С учетом инфляции', value=True)
#show_discount = st.sidebar.checkbox('Рассчитать дисконтирование', value=True)
#show_change = st.sidebar.checkbox('Показать изменение з/п', value=True)

service.set_filter(branches, years[0], years[1])

st.markdown("####Среднемесячная номинальной начисленной заработной плате по выбранным отраслям:")
st.table(service.get_data())

fig = service.get_salary_plot(show_infl)
st.plotly_chart(fig, use_container_width=True)

fig = service.get_min_max_salary_plot()
st.plotly_chart(fig, use_container_width=True)

fig = service.get_salary_discount_plot(years[0], years[1])
st.plotly_chart(fig, use_container_width=True)

st.markdown('#### Реальные зарплаты с учетом инфляции (в рублях 2000 года)'')
st.markdown('Годовое изменение реальных зарплат (%)')

fig = service.get_salary_change_plots()
st.plotly_chart(fig, use_container_width=True)

