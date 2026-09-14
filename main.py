import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from statsmodels.tsa.statespace.sarimax import SARIMAX
import os
import warnings

warnings.filterwarnings('ignore')

# ---------------------------------------------------------
# ESTILO PROFISSIONAL
# ---------------------------------------------------------

st.set_page_config(
    layout="wide",
    page_title="VigilIA - Painel de Vigilancia Epidemiologica",
    page_icon="🦟",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #f5f6f8; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    section[data-testid="stSidebar"] .stRadio label span {
        color: #ffffff !important;
        font-size: 0.9rem;
        padding: 8px 12px;
        border-radius: 8px;
        background: rgba(255,255,255,0.08);
        display: block;
        margin-bottom: 6px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    section[data-testid="stSidebar"] .stRadio label {
        background: transparent !important;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] .stCaption {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] label {
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] p {
        color: #ffffff !important;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    div[data-testid="stMetric"] label {
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #0f172a;
        font-size: 1.7rem;
        font-weight: 700;
    }

    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    h1 { color: #0f172a; font-weight: 700; }
    h2 { color: #0f172a; font-weight: 600; }
    h3 { color: #1e293b; font-weight: 600; }

    .risk-badge {
        display: inline-block;
        padding: 8px 22px;
        border-radius: 24px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }
    .risk-alto { background: #fef2f2; color: #991b1b; border: 2px solid #fca5a5; }
    .risk-medio { background: #fffbeb; color: #92400e; border: 2px solid #fcd34d; }
    .risk-baixo { background: #f0fdf4; color: #166534; border: 2px solid #86efac; }

    div[data-testid="stForm"] {
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 28px;
        background: #ffffff;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }

    .section-divider {
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 1.8rem 0;
    }

    .insight-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px 22px;
        margin-bottom: 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .insight-card h4 {
        margin: 0 0 8px 0;
        font-size: 0.9rem;
        font-weight: 600;
        color: #1e293b;
    }
    .insight-card p {
        margin: 0;
        font-size: 0.85rem;
        color: #64748b;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# DADOS
# ---------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    base = os.path.join(os.path.dirname(__file__), 'dados')

    df25 = pd.read_csv(os.path.join(base, 'DENGBR25.csv'), dtype={'ID_MUNICIP': str})
    df26 = pd.read_csv(os.path.join(base, 'DENGBR26.csv'), dtype={'ID_MUNICIP': str})
    df = pd.concat([df25, df26], ignore_index=True)

    mun = pd.read_csv(os.path.join(base, 'municipios.csv'), dtype={'codigo_ibge': str})
    mun['codigo_6'] = mun['codigo_ibge'].str[:6]
    mun_map = mun.drop_duplicates('codigo_6').set_index('codigo_6')
    df['NOME_MUNICIP'] = df['ID_MUNICIP'].map(mun_map['nome']).fillna('Desconhecido')
    df['LAT'] = df['ID_MUNICIP'].map(mun_map['latitude'])
    df['LON'] = df['ID_MUNICIP'].map(mun_map['longitude'])

    df['DT_NOTIFIC'] = pd.to_datetime(df['DT_NOTIFIC'], errors='coerce')
    df = df.dropna(subset=['DT_NOTIFIC'])

    df['GRAVE'] = (df['EVOLUCAO'] == 2).astype(int)
    df['MODERADO'] = ((df['GRAVE'] == 0) & (df['HOSPITALIZ'] == 1)).astype(int)
    df['LEVE'] = ((df['GRAVE'] == 0) & (df['MODERADO'] == 0)).astype(int)

    return df


@st.cache_data(ttl=600, show_spinner=False)
def build_daily(df):
    daily = (
        df.groupby([df['DT_NOTIFIC'].dt.normalize(), 'NOME_MUNICIP'])
        .size()
        .reset_index(name='casos')
    )
    daily.rename(columns={'DT_NOTIFIC': 'data'}, inplace=True)
    return daily


# ---------------------------------------------------------
# PREVISAO
# ---------------------------------------------------------

def _forecast(series, steps, seasonal=False):
    vals = series.values.astype(float)
    n = len(vals)
    if n < 10:
        return np.full(steps, vals.mean() if n > 0 else 0)
    if seasonal and n >= 13:
        med = np.median(vals[vals > 0]) if np.any(vals > 0) else 1
        weights = np.where(vals > med * 0.3, 1.0, 0.1)
        cal_months = series.index.month.values
        seasonal_pattern = {}
        for cm in range(1, 13):
            mask = cal_months == cm
            if mask.any():
                seasonal_pattern[cm] = np.average(vals[mask], weights=weights[mask])
        overall = np.average(vals, weights=weights)
        seasonal_idx = {cm: v / overall for cm, v in seasonal_pattern.items()}
        complete_mask = weights > 0.5
        if complete_mask.sum() >= 3:
            complete_x = np.where(complete_mask)[0].astype(float)
            complete_y = vals[complete_mask]
            slope = (np.mean(complete_x * complete_y) - np.mean(complete_x) * np.mean(complete_y)) / \
                    (np.mean(complete_x ** 2) - np.mean(complete_x) ** 2 + 1e-10)
        else:
            slope = 0
        fc = np.zeros(steps)
        last_complete_idx = np.where(complete_mask)[0][-1] if complete_mask.any() else n - 1
        for i in range(steps):
            future_date = series.index[-1] + pd.offsets.MonthBegin(1 + i)
            cm = future_date.month
            si = seasonal_idx.get(cm, 1.0)
            dist = i + 1
            trend_adj = 1 + (slope / (overall + 1)) * dist * 0.3
            trend_adj = max(trend_adj, 0.1)
            fc[i] = overall * si * trend_adj
        return fc
    try:
        model = SARIMAX(vals, order=(1, 1, 1),
                        enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        return np.maximum(model.forecast(steps), 0)
    except Exception:
        return np.full(steps, vals[-n // 4:].mean() if n > 0 else 0)


@st.cache_data(ttl=3600, show_spinner=False)
def forecast_diario(daily_df, days):
    agg = daily_df.groupby('data')['casos'].sum().sort_index()
    fc = _forecast(agg, days, seasonal=True)
    last_date = agg.index.max()
    future = pd.date_range(last_date + timedelta(days=1), periods=days, freq='D')
    return pd.DataFrame({'data': future, 'casos': np.round(fc, 1)})


@st.cache_data(ttl=3600, show_spinner=False)
def forecast_mensal(daily_df):
    tmp = daily_df.copy()
    tmp['mes'] = tmp['data'].dt.to_period('M')
    monthly = tmp.groupby('mes')['casos'].sum().sort_index()
    monthly.index = monthly.index.to_timestamp()
    if len(monthly) < 3:
        return pd.DataFrame()
    fc = _forecast(monthly, 12, seasonal=True)
    future = pd.date_range(monthly.index.max() + pd.offsets.MonthBegin(1), periods=12, freq='MS')
    return pd.DataFrame({'mes': future, 'casos': np.round(fc, 1)})


# ---------------------------------------------------------
# CLASSIFICACAO DE RISCO
# ---------------------------------------------------------

def classificar_risco(c):
    idade = c.get('idade', 30)
    dias = c.get('dias_sintomas', 3)
    sintomas = sum(c.get(k, 0) for k in [
        'febre', 'mialgia', 'cefaleia', 'exantema',
        'vomito', 'nausea', 'dor_retro'
    ])
    alarme = sum(c.get(k, 0) for k in ['petequia', 'leucopenia', 'laco'])
    comorb = sum(c.get(k, 0) for k in ['diabetes', 'hipertensao', 'renal', 'hepatopat'])

    pts = 0
    fatores = []

    if idade < 1 or idade > 65:
        pts += 2; fatores.append("Faixa etaria de risco")
    if c.get('gestante', 0) == 1:
        pts += 2; fatores.append("Gestante")
    if comorb > 0:
        pts += comorb; fatores.append(f"Comorbidades ({comorb})")
    if sintomas >= 4:
        pts += 1; fatores.append(f"Multiplos sintomas ({sintomas})")
    if alarme > 0:
        pts += 2; fatores.append("Sinais de alarme presentes")
    if dias > 7:
        pts += 1; fatores.append(f"Sintomas ha {dias} dias")

    if pts >= 6:
        return "ALTO", "#dc2626", pts, fatores, [
            "Procurar pronto-socorro imediatamente",
            "Hidratacao venosa provavelmente necessaria",
            "Monitorar hematoctrito e plaquetas a cada 6h",
            "Avaliar sinais de gravidade: sangramento e hipotensao",
            "Considerar internacao se piorar",
        ]
    elif pts >= 3:
        return "MEDIO", "#d97706", pts, fatores, [
            "Retornar a UBS em 48h se nao melhorar",
            "Hidratacao oral vigorosa (minimo 2L/dia)",
            "Paracetamol para febre (evitar AAS e AINEs)",
            "Monitorar sinais de alarme",
            "Repousar e manter alimentacao leve",
        ]
    else:
        return "BAIXO", "#16a34a", pts, fatores, [
            "Conduta domiciliar com hidratacao oral",
            "Paracetamol se febre acima de 38,5 graus Celsius",
            "Voltar se surgirem sinais de alarme",
            "Avaliacao clinica em 5 a 7 dias se persistir",
            "Orientacao sobre prevencao de focos",
        ]


# ---------------------------------------------------------
# GRAFICOS PADRONIZADOS
# ---------------------------------------------------------

COR_GRAVE = '#dc2626'
COR_MODERADO = '#f59e0b'
COR_LEVE = '#10b981'
COR_PRIMARIA = '#0f172a'
COR_ACCENT = '#6366f1'
COR_BG = '#ffffff'
PALETTE = ['#6366f1', '#06b6d4', '#f43f5e', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6']

CHART_LAYOUT = dict(
    font=dict(family='Inter, sans-serif', size=12, color='#334155'),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=20, r=20, t=50, b=20),
    xaxis=dict(gridcolor='#f1f5f9', zerolinecolor='#e2e8f0'),
    yaxis=dict(gridcolor='#f1f5f9', zerolinecolor='#e2e8f0'),
    hoverlabel=dict(bgcolor='#0f172a', font_size=12, font_family='Inter', font_color='white'),
)


def fmt_br(n):
    if isinstance(n, float):
        return f"{n:,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"{n:,}".replace(',', '.')


# ---------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------

with st.sidebar:
    st.markdown("<h1 style='text-align:center; font-size:2.4rem; font-weight:800; margin-bottom:0; color:#ffffff;'>VigilIA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#94a3b8; font-size:0.85rem; margin-top:4px;'>Painel de Vigilancia Epidemiologica</p>", unsafe_allow_html=True)
    st.markdown("---")
    aba = st.radio(
        "Navegacao",
        ["Painel Completo",
         "Avaliacao de Paciente", "Gestao de Recursos"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("v1.1 | Dados DENGBR 2025-2026")

df_raw = load_data()
daily = build_daily(df_raw)

st.markdown(f"### {aba}")

# ==================== PAINEL COMPLETO ====================
if aba == "Painel Completo":

    col_cfg, col_vis = st.columns([1, 3])

    with col_cfg:
        dias = st.slider("Dias no futuro", 1, 30, 14)

    if st.button("Gerar Analise", type="primary", key="btn_fc"):

        with st.spinner("Processando modelos..."):
            fc_dia = forecast_diario(daily, dias)
            fc_mes = forecast_mensal(daily)

        with col_vis:
            total_30 = fc_dia['casos'].sum()
            media_dia = fc_dia['casos'].mean()
            total_12m = fc_mes['casos'].sum() if not fc_mes.empty else 0
            data_base = daily['data'].max().strftime('%d/%m/%Y')

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(f"Total previsto ({dias} dias)", fmt_br(int(total_30)))
            m2.metric("Media diaria", fmt_br(media_dia))
            m3.metric("Projecao 12 meses", fmt_br(int(total_12m)))
            m4.metric("Dados atualizados ate", data_base)

            fig_dia = go.Figure(data=[go.Bar(
                x=fc_dia['data'], y=fc_dia['casos'],
                marker_color=COR_ACCENT,
                text=fc_dia['casos'].apply(lambda v: fmt_br(int(v))),
                textposition='outside',
                textfont=dict(size=10, family='Inter'),
            )])
            fig_dia.update_layout(**CHART_LAYOUT, height=380,
                                  title_text=f"Previsao Diaria ({dias} dias)",
                                  showlegend=False)
            fig_dia.update_xaxes(title_text="Data")
            fig_dia.update_yaxes(title_text="Casos")
            st.plotly_chart(fig_dia, use_container_width=True)

        # ---------- BARRAS MENSAL ----------
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        if not fc_mes.empty:
            fig_mes_bar = go.Figure(data=[go.Bar(
                x=fc_mes['mes'], y=fc_mes['casos'],
                marker_color=COR_ACCENT,
                text=fc_mes['casos'].apply(lambda v: fmt_br(int(v))),
                textposition='outside',
                textfont=dict(size=11, family='Inter'),
            )])
            fig_mes_bar.update_layout(**CHART_LAYOUT, height=380,
                                      title_text="Casos por Mes (projecao 12 meses)",
                                      showlegend=False)
            fig_mes_bar.update_xaxes(title_text="Mes")
            fig_mes_bar.update_yaxes(title_text="Casos")
            st.plotly_chart(fig_mes_bar, use_container_width=True)

        # ---------- CRITICIDADE ----------
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        n_graves = int(df_raw['GRAVE'].sum())
        n_mod = int(df_raw['MODERADO'].sum())
        n_leves = int(df_raw['LEVE'].sum())
        total_hist = n_graves + n_mod + n_leves
        n_hosp = int(df_raw['HOSPITALIZ'].sum())
        taxa_grave = (n_graves / total_hist * 100) if total_hist > 0 else 0

        st.markdown("#### Criticidade dos Casos")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total de Casos", fmt_br(total_hist))
        k2.metric("Graves", fmt_br(n_graves), f"{taxa_grave:.1f}%")
        k3.metric("Moderados", fmt_br(n_mod))
        k4.metric("Hospitalizados", fmt_br(n_hosp))

        col_pie1, col_pie2 = st.columns(2)

        with col_pie1:
            fig_pie = go.Figure(data=[go.Pie(
                labels=['Graves', 'Moderados', 'Leves'],
                values=[n_graves, n_mod, n_leves],
                hole=0.55,
                marker=dict(colors=[COR_GRAVE, COR_MODERADO, COR_LEVE]),
                textfont=dict(size=13, family='Inter'),
                textposition='inside',
            )])
            fig_pie.update_layout(**CHART_LAYOUT, height=380, showlegend=True,
                                  title_text="Distribuicao de Gravidade",
                                  legend=dict(x=0.02, y=0.5, xanchor='left', yanchor='middle', font=dict(size=13)))
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_pie2:
            evol_labels = {0: 'Ignorado', 1: 'Cura', 2: 'Obito', 9: 'Ignorado'}
            evol_counts = df_raw['EVOLUCAO'].value_counts().rename(index=evol_labels)
            fig_evol = go.Figure(data=[go.Pie(
                labels=evol_counts.index.astype(str),
                values=evol_counts.values,
                hole=0.55,
                marker=dict(colors=['#64748b', '#10b981', '#dc2626', '#94a3b8']),
                textfont=dict(size=13, family='Inter'),
                textposition='inside',
            )])
            fig_evol.update_layout(**CHART_LAYOUT, height=380, showlegend=True,
                                   title_text="Evolucao dos Casos",
                                   legend=dict(x=0.02, y=0.5, xanchor='left', yanchor='middle', font=dict(size=13)))
            st.plotly_chart(fig_evol, use_container_width=True)

        # MAPA DE CALOR
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown("#### Mapa de Casos por Municipio")
        mun_geo = (
            df_raw.groupby(['NOME_MUNICIP', 'LAT', 'LON'])
            .agg(casos=('NOME_MUNICIP', 'size'), graves=('GRAVE', 'sum'))
            .reset_index()
            .dropna(subset=['LAT', 'LON'])
        )

        fig_map = px.scatter_mapbox(
            mun_geo,
            lat='LAT', lon='LON',
            size='casos',
            color='graves',
            color_continuous_scale='YlOrRd',
            size_max=30,
            hover_name='NOME_MUNICIP',
            hover_data={'casos': True, 'graves': True, 'LAT': False, 'LON': False},
            mapbox_style='carto-positron',
            zoom=3,
            center=dict(lat=-14.2, lon=-51.9),
        )
        fig_map.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0),
                              coloraxis_colorbar=dict(title="Graves"),
                              font=dict(family='Inter, sans-serif', size=12, color='#334155'),
                              paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # CASOS POR UF
        st.markdown("#### Casos por Estado")
        uf_map = {11:'RO',12:'AC',13:'AM',14:'RR',15:'PA',16:'AP',17:'TO',
                  21:'MA',22:'PI',23:'CE',24:'RN',25:'PB',26:'PE',27:'AL',28:'SE',29:'BA',
                  31:'MG',32:'ES',33:'RJ',35:'SP',41:'PR',42:'SC',43:'RS',50:'MS',51:'MT',
                  52:'GO',53:'DF'}
        uf_counts = df_raw['SG_UF_NOT'].value_counts().head(15)
        uf_counts.index = pd.to_numeric(uf_counts.index, errors='coerce').fillna(0).astype(int)
        uf_counts.index = uf_counts.index.map(lambda x: uf_map.get(x, str(x)))
        fig_uf = go.Figure(data=[go.Bar(
            x=uf_counts.index, y=uf_counts.values,
            marker_color=COR_ACCENT, text=uf_counts.values,
            textposition='outside', textfont=dict(size=11, family='Inter'),
        )])
        fig_uf.update_layout(**CHART_LAYOUT, height=340, showlegend=False)
        fig_uf.update_xaxes(title_text="Estado")
        fig_uf.update_yaxes(title_text="Casos")
        st.plotly_chart(fig_uf, use_container_width=True)

        # TOP 10 MUNICIPIOS
        st.markdown("#### Top 10 Municipios")
        top = (
            df_raw.groupby('NOME_MUNICIP')
            .agg(casos=('NOME_MUNICIP', 'size'), graves=('GRAVE', 'sum'))
            .sort_values('casos', ascending=False)
            .head(10)
            .reset_index()
        )
        fig_top = go.Figure(data=[go.Bar(
            x=top['NOME_MUNICIP'], y=top['casos'],
            marker_color=COR_ACCENT, text=top['casos'],
            textposition='outside', textfont=dict(size=11, family='Inter'),
            name='Total',
        )])
        fig_top.add_trace(go.Bar(
            x=top['NOME_MUNICIP'], y=top['graves'],
            marker_color=COR_GRAVE, text=top['graves'],
            textposition='outside', textfont=dict(size=11, family='Inter'),
            name='Graves',
        ))
        fig_top.update_layout(**CHART_LAYOUT, height=380, barmode='group',
                              legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
        fig_top.update_xaxes(title_text="Municipio")
        fig_top.update_yaxes(title_text="Casos")
        st.plotly_chart(fig_top, use_container_width=True)


# ==================== AVALIACAO DE PACIENTE ====================
elif aba == "Avaliacao de Paciente":

    st.markdown("Preencha os dados do paciente para classificacao de risco e orientacao de conduta.")

    with st.form(key="form_paciente"):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("**Dados Gerais**")
            idade = st.number_input("Idade (anos)", 0, 120, 30)
            gestante = st.selectbox("Gestante", ["Nao", "Sim"])
            dias_sint = st.number_input("Dias com sintomas", 0, 60, 3)

        with c2:
            st.markdown("**Sintomas**")
            febre = st.selectbox("Febre", ["Nao", "Sim"])
            mialgia = st.selectbox("Mialgia", ["Nao", "Sim"])
            cefaleia = st.selectbox("Cefaleia", ["Nao", "Sim"])
            exantema = st.selectbox("Exantema", ["Nao", "Sim"])
            vomito = st.selectbox("Vomito", ["Nao", "Sim"])
            nausea = st.selectbox("Nausea", ["Nao", "Sim"])
            dor_retro = st.selectbox("Dor retroorbital", ["Nao", "Sim"])

        with c3:
            st.markdown("**Sinais de Alarme / Comorbidades**")
            petequia = st.selectbox("Petequias", ["Nao", "Sim"])
            leucopenia = st.selectbox("Leucopenia", ["Nao", "Sim"])
            laco = st.selectbox("Laco (prova do laco)", ["Nao", "Sim"])
            diabetes = st.selectbox("Diabetes", ["Nao", "Sim"])
            hipertensao = st.selectbox("Hipertensao", ["Nao", "Sim"])
            renal = st.selectbox("Doenca renal", ["Nao", "Sim"])
            hepatopat = st.selectbox("Hepatopatia", ["Nao", "Sim"])

        enviado = st.form_submit_button("Classificar Risco", type="primary")

    if enviado:
        campos = {
            'idade': idade, 'dias_sintomas': dias_sint, 'gestante': 1 if gestante == "Sim" else 0,
            'febre': 1 if febre == "Sim" else 0, 'mialgia': 1 if mialgia == "Sim" else 0,
            'cefaleia': 1 if cefaleia == "Sim" else 0, 'exantema': 1 if exantema == "Sim" else 0,
            'vomito': 1 if vomito == "Sim" else 0, 'nausea': 1 if nausea == "Sim" else 0,
            'dor_retro': 1 if dor_retro == "Sim" else 0, 'petequia': 1 if petequia == "Sim" else 0,
            'leucopenia': 1 if leucopenia == "Sim" else 0, 'laco': 1 if laco == "Sim" else 0,
            'diabetes': 1 if diabetes == "Sim" else 0, 'hipertensao': 1 if hipertensao == "Sim" else 0,
            'renal': 1 if renal == "Sim" else 0, 'hepatopat': 1 if hepatopat == "Sim" else 0,
        }

        nivel, cor, pts, fatores, recomendacoes = classificar_risco(campos)

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        rc1, rc2 = st.columns([1, 2])

        with rc1:
            badge_cls = f"risk-{nivel.lower()}"
            st.markdown(
                f'<div style="text-align:center; margin-top:8px;">'
                f'<span class="risk-badge {badge_cls}">{nivel}</span>'
                f'<br><span style="font-size:2.8rem; font-weight:700; color:{cor};">{pts} pts</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        with rc2:
            st.markdown("**Fatores identificados:**")
            if fatores:
                for f in fatores:
                    st.markdown(f"- {f}")
            else:
                st.markdown("- Nenhum fator de risco adicional identificado")

            st.markdown("**Conduta recomendada:**")
            for i, r in enumerate(recomendacoes, 1):
                st.markdown(f"{i}. {r}")


# ==================== GESTAO DE RECURSOS ====================
elif aba == "Gestao de Recursos":

    if st.button("Gerar Analise Completa", type="primary", key="btn_gestao"):
        with st.spinner("Processando..."):
            fc30 = forecast_diario(daily, 30)
            total_prev = fc30['casos'].sum()

            n_graves = int(df_raw['GRAVE'].sum())
            n_mod = int(df_raw['MODERADO'].sum())
            n_leves = int(df_raw['LEVE'].sum())
            total_hist = n_graves + n_mod + n_leves
            n_hosp = int(df_raw['HOSPITALIZ'].sum())
            taxa_grave = (n_graves / total_hist * 100) if total_hist > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Casos previstos (30d)", fmt_br(int(total_prev)))
        k2.metric("Graves (historico)", fmt_br(n_graves), f"{taxa_grave:.1f}%")
        k3.metric("Moderados", fmt_br(n_mod))
        k4.metric("Hospitalizados", fmt_br(n_hosp))

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        st.markdown("#### Distribuicao de Gravidade")
        g1, g2 = st.columns(2)

        with g1:
            fig_pie = go.Figure(data=[go.Pie(
                labels=['Graves', 'Moderados', 'Leves'],
                values=[n_graves, n_mod, n_leves],
                hole=0.55,
                marker=dict(colors=[COR_GRAVE, COR_MODERADO, COR_LEVE]),
                textfont=dict(size=13, family='Inter'),
                textposition='inside',
            )])
            fig_pie.update_layout(**CHART_LAYOUT, height=380, showlegend=True,
                                  legend=dict(x=0.02, y=0.5, xanchor='left', yanchor='middle', font=dict(size=13)))
            st.plotly_chart(fig_pie, use_container_width=True)

        with g2:
            evol_labels = {0: 'Ignorado', 1: 'Cura', 2: 'Obito', 9: 'Ignorado'}
            evol_counts = df_raw['EVOLUCAO'].value_counts().rename(index=evol_labels)
            fig_evol = go.Figure(data=[go.Pie(
                labels=evol_counts.index.astype(str),
                values=evol_counts.values,
                hole=0.55,
                marker=dict(colors=['#64748b', '#10b981', '#dc2626', '#94a3b8']),
                textfont=dict(size=13, family='Inter'),
                textposition='inside',
            )])
            fig_evol.update_layout(**CHART_LAYOUT, height=380, showlegend=True,
                                   title_text="Evolucao dos Casos",
                                   legend=dict(x=0.02, y=0.5, xanchor='left', yanchor='middle', font=dict(size=13)))
            st.plotly_chart(fig_evol, use_container_width=True)

        # RECURSOS ESTIMADOS
        st.markdown("#### Recursos Estimados (30 dias)")
        est_graves = int(total_prev * (taxa_grave / 100)) if taxa_grave > 0 else int(total_prev * 0.15)

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Leitos Enfermaria", fmt_br(int(est_graves * 0.7)))
        r2.metric("Leitos UTI", fmt_br(int(est_graves * 0.3)))
        r3.metric("Kits Sorologia", fmt_br(int(total_prev * 0.8)))
        r4.metric("Fluidos IV", fmt_br(int(est_graves * 2)))

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # MUNICIPIOS MAIS CRITICOS
        st.markdown("#### Municipios Mais Criticos")
        mun_crit = (
            df_raw.groupby('NOME_MUNICIP')
            .agg(
                casos=('NOME_MUNICIP', 'size'),
                graves=('GRAVE', 'sum'),
                hospitalizados=('HOSPITALIZ', lambda x: (x == 1).sum()),
            )
            .assign(taxa_grave=lambda x: (x['graves'] / x['casos'] * 100).round(1))
            .sort_values('graves', ascending=False)
            .head(10)
            .reset_index()
        )

        col_tbl, col_plan = st.columns([3, 2])

        with col_tbl:
            st.dataframe(
                mun_crit.rename(columns={
                    'NOME_MUNICIP': 'Municipio',
                    'casos': 'Casos',
                    'graves': 'Graves',
                    'hospitalizados': 'Internacoes',
                    'taxa_grave': 'Taxa Grave %',
                }),
                use_container_width=True,
                height=380,
                hide_index=True,
            )

        with col_plan:
            st.markdown("**Planos de Acao Recomendados:**")
            planos = []
            for _, row in mun_crit.head(5).iterrows():
                nome = row['NOME_MUNICIP']
                tx = row['taxa_grave']
                g = int(row['graves'])
                h = int(row['hospitalizados'])
                if tx > 5:
                    plano = f"**{nome}** — Risco alto ({tx:.1f}% grave). "
                    if h > 10:
                        plano += "Expandir leitos hospitalares e enviar equipe de reforco."
                    else:
                        plano += "Reforcar vigilancia e acionar CPA."
                elif h > 20:
                    plano = f"**{nome}** — Alta demanda de internacao ({h} pacientes). "
                    plano += "Preparar leitos extras e fluidos intravenosos."
                else:
                    plano = f"**{nome}** — Monitorar evolucao. "
                    plano += "Manter busca ativa e orientacao a populacao."
                planos.append(plano)

            for i, p in enumerate(planos, 1):
                st.markdown(f"{i}. {p}")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # RECOMENDACOES
        st.markdown("#### Recomendacoes")
        if taxa_grave > 20:
            st.markdown(
                '<div class="insight-card"><h4>Atencao: Alta Taxa de Gravidade</h4>'
                f'<p>Taxa de {taxa_grave:.1f}% de casos graves. '
                'Reforcar prontos-socorros e UTIs nas areas criticas.</p></div>',
                unsafe_allow_html=True,
            )
        if n_hosp > total_hist * 0.1:
            st.markdown(
                '<div class="insight-card"><h4>Capacidade Hospitalar</h4>'
                '<p>Alta demanda por internacao. Avaliar expansao temporaria de leitos.</p></div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="insight-card"><h4>Prevencao</h4>'
            '<p>Intensificar combate a focos do <em>Aedes aegypti</em> '
            'nos municipios com maior incidencia prevista.</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="insight-card"><h4>Campanha de Orientacao</h4>'
            '<p>Distribuir material educativo sobre sinais de alarme, '
            'hidratacao oral e quando procurar atendimento.</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="insight-card"><h4>Vigilancia Ativa</h4>'
            '<p>Reforcar busca ativa de casos em areas com incidencia acima da media historica.</p></div>',
            unsafe_allow_html=True,
        )
