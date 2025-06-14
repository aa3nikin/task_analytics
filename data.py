import os
import math
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import numpy as np
from sqlalchemy import create_engine
from plotly.subplots import make_subplots

@st.cache_data
def _get_salary_data(_engine):
    query = '''select b."name" as "Отрасль"'''
    for x in range(2000, 2023+1):
        query += f''', (select sd2.salary from salary_data sd2 where sd2.branch_id = b.id and sd2."year" = {x}) as "{x}"'''
    
    query += '''from branch b'''
    return pd.read_sql(query, con=_engine)

@st.cache_data
def _get_inflation_data(_engine):
    query = 'select "year" as "Год", rate as "Всего" from inflation'
    infl = pd.read_sql(query, con=_engine, index_col='Год')
    infl = infl['Всего']
    infl.name = 'Инфляция'
    return infl.sort_index()

def _get_real_data(data, infl):
    data_real = data.copy()
    for col in data_real.columns[1:]:
        year = int(col)
        if year == 2000:
            continue
        # Приведение к ценам 2000 года
        for y in range(2001, year + 1):
            if y in infl.index:
                data_real[col] = data_real[col] / (1 + infl.loc[y]/100)
    return data_real

@st.cache_data
def _get_new_data(_engine):
    query = 'select * from new_data'
    return pd.read_sql(query, con=_engine)

def _get_line(data, name):
    line = data[data['Отрасль'] == name].drop(['Отрасль'], axis=1)
    line = line.squeeze()
    line.index = line.index.map(int)
    return line.sort_index()

def _filter_data(data, branches, year_from, year_to):
    cols = ['Отрасль'] + [str(year) for year in range(year_from, year_to + 1)]
    data = data[cols]
    return data[data['Отрасль'].isin(branches)]

class SalaryService:
    def __init__(self):
        self._data = pd.DataFrame()
        self._infl = pd.Series(dtype=float)
        self._data_real = pd.DataFrame()
        self._data_filtered = pd.DataFrame()
        self._infl_filtered = pd.Series(dtype=float)
        self._data_real_filtered = pd.DataFrame()
        self._branches_filtered = []
        self._new_data = pd.DataFrame()

    # Перевод в цены целевого года (наращивание)
    def _compound(self, year_from, year_to, sum_val):
        result = sum_val
        if year_from < year_to:
            for y in range(year_from + 1, year_to + 1):
                if y in self._infl.index:
                    result *= (1 + self._infl.loc[y]/100)
        return result

    # Перевод в цены базового года (дисконтирование)
    def _discount(self, year_from, year_to, sum_val):
        result = sum_val
        if year_from > year_to:
            for y in range(year_from, year_to, -1):
                if y in self._infl.index:
                    result /= (1 + self._infl.loc[y]/100)
        return result

    def reload_data(self):
        def _get_conn_str():
            user = os.environ['DB_USER']
            password = os.environ['DB_PASSWORD']
            host = os.environ['DB_HOST']
            name = os.environ['DB_NAME']
            return f'postgresql://{user}:{password}@{host}/{name}?sslmode=require'
        
        try:
            engine = create_engine(_get_conn_str())
            self._data = _get_salary_data(engine)
            self._infl = _get_inflation_data(engine)
            self._new_data = _get_new_data(engine)
            self._data_real = _get_real_data(self._data, self._infl)
        finally:
            if engine:
                engine.dispose()

    def set_filter(self, branches, year_from, year_to):
        self._branches_filtered = branches
        self._data_filtered = _filter_data(self._data, branches, year_from, year_to)
        self._data_real_filtered = _filter_data(self._data_real, branches, year_from, year_to)
        self._infl_filtered = self._infl.loc[year_from:year_to]

    def get_branches(self):
        return self._data['Отрасль'].tolist()
    
    def get_data(self):
        return self._data_filtered
    
    def get_data_real(self):
        return self._data_real_filtered
    
    def get_infl(self):
        return self._infl_filtered
    
    def get_salary_plot(self, show_infl):
        data = self._data_filtered
        data_real = self._data_real_filtered
        fig = go.Figure()
        
        for name in self._branches_filtered:
            dt = _get_line(data, name)
            
            if show_infl:
                dt_real = _get_line(data_real, name)
                fig.add_trace(go.Scatter(
                    x=dt_real.index,
                    y=dt_real.values,
                    name=f"{name} (реальная)",
                    line=dict(dash='solid')
                ))
                fig.add_trace(go.Scatter(
                    x=dt.index,
                    y=dt.values,
                    name=f"{name} (номинальная)",
                    line=dict(dash='dash')
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=dt.index,
                    y=dt.values,
                    name=name
                ))
                
        fig.update_layout(
            title='Динамика заработной платы',
            xaxis_title='Год',
            yaxis_title='Зарплата, руб.',
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=20, r=10, t=60, b=20)
        )
        return fig
    
    def get_salary_discount_plot(self, year_from, year_to):
        data_start = self._data_real_filtered.copy()
        data_end = self._data_real_filtered.copy()
        
        for col in data_start.columns[1:]:
            year = int(col)
            data_start[col] = data_start[col].apply(
                lambda x: self._compound(2000, year_from, x) if not pd.isna(x) else x
            )
            data_end[col] = data_end[col].apply(
                lambda x: self._compound(2000, year_to, x) if not pd.isna(x) else x
            )
        
        titles = [
            f'В ценах {year_from} года',
            f'В ценах {year_to} года'
        ]
        
        fig = make_subplots(rows=1, cols=2, subplot_titles=titles)
        
        for name in self._branches_filtered:
            # Левая панель (цены year_from)
            dt_start = _get_line(data_start, name)
            fig.add_trace(go.Scatter(
                x=dt_start.index,
                y=dt_start.values,
                name=name,
                showlegend=True
            ), row=1, col=1)
            
            # Правая панель (цены year_to)
            dt_end = _get_line(data_end, name)
            fig.add_trace(go.Scatter(
                x=dt_end.index,
                y=dt_end.values,
                name=name,
                showlegend=False
            ), row=1, col=2)
            
        fig.update_layout(
            title='Сравнение реальных зарплат в разных ценах',
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=20, r=10, t=80, b=20)
        )
        return fig
    
    def get_salary_change_plots(self):
        # Рассчитываем процентные изменения
        changes = self._data_real_filtered.copy().set_index('Отрасль').T
        changes = changes.pct_change() * 100
        changes = changes.iloc[1:]  # Удаляем первую строку с NaN
        
        # Создаем subplots
        rows = math.ceil(len(self._branches_filtered) / 2)
        fig = make_subplots(
            rows=rows,
            cols=2,
            subplot_titles=self._branches_filtered,
            vertical_spacing=0.1
        )
        
        for i, industry in enumerate(self._branches_filtered):
            row = i // 2 + 1
            col = i % 2 + 1
            
            # Фильтруем данные для отрасли
            industry_data = changes[industry].dropna()
            
            # Создаем столбцы с цветами
            colors = ['green' if val >= 0 else 'red' for val in industry_data]
            
            fig.add_trace(go.Bar(
                x=industry_data.index,
                y=industry_data.values,
                name=industry,
                marker_color=colors,
                showlegend=False
            ), row=row, col=col)
            
            # Добавляем линию нуля
            fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="black", row=row, col=col)
            
        fig.update_layout(
            height=400 * rows,
            title_text="Годовые изменения реальных зарплат",
            margin=dict(l=20, r=10, t=80, b=20)
        )
        return fig
    
    def get_min_max_salary_plot(self):
        # Фильтруем данные за 2023 год
        minmax = self._new_data[['Отрасль', '2023']].copy()
        minmax.columns = ['Отрасль', '2023']
        
        # Удаляем строку со средним значением
        minmax = minmax[minmax['Отрасль'] != 'Средняя']
        
        # Сортируем по значению
        minmax = minmax.sort_values('2023')
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=minmax['2023'],
            y=minmax['Отрасль'],
            orientation='h',
            marker_color='skyblue'
        ))
        
        fig.update_layout(
            title='Зарплаты по отраслям в 2023 году',
            xaxis_title='Зарплата, руб.',
            yaxis_title='Отрасль',
            margin=dict(l=150, r=20, t=60, b=20)
        )
        return fig