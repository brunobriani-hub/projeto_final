from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="B3 | Análise de desempenho",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1550px;
      }

      [data-testid="stSidebar"] {
        background: #F0F5F2;
        border-right: 1px solid #DCE8E1;
      }

      [data-testid="stSidebar"] h1 {
        color: #173B3B;
        font-size: 1.45rem;
      }

      [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #E1EAE5;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 3px 12px rgba(27, 66, 59, 0.05);
      }

      [data-testid="stMetricLabel"] p {
        color: #59716A;
        font-size: 0.88rem;
      }

      [data-testid="stMetricValue"] {
        color: #173B3B;
      }

      [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #DCE8E1;
      }

      button[role="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 0.65rem 1rem;
      }

      [data-testid="stPlotlyChart"] {
        border-radius: 14px;
      }

      .hero-card {
        background: linear-gradient(
          115deg,
          #EAF3EE 0%,
          #F5F8F5 58%,
          #E8F1F1 100%
        );
        border: 1px solid #DCE8E1;
        border-radius: 20px;
        padding: 26px 30px;
        margin: 0 0 18px 0;
      }

      .hero-kicker {
        color: #438078;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 8px;
      }

      .hero-title {
        color: #173B3B;
        font-size: 2.1rem;
        font-weight: 700;
        line-height: 1.15;
        margin: 0 0 8px 0;
      }

      .hero-subtitle {
        color: #526B65;
        font-size: 1rem;
        margin: 0;
      }

      @media (max-width: 800px) {
        .block-container {
          padding-top: 1rem;
        }

        .hero-card {
          padding: 20px;
        }

        .hero-title {
          font-size: 1.65rem;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO_CSV = (
    PASTA_PROJETO / "data" / "indicadores_diarios_2021_2023.csv"
)

# Agrupamentos analíticos adotados no projeto.
# São simplificações e não substituem a classificação oficial da B3.
SETOR_POR_ATIVO = {
    "ABEV3": "Consumo e serviços",
    "RENT3": "Consumo e serviços",
    "EMBR3": "Indústria",
    "WEGE3": "Indústria",
    "GGBR4": "Commodities",
    "KLBN11": "Commodities",
    "VALE3": "Commodities",
    "PETR4": "Energia",
    "PRIO3": "Energia",
    "EGIE3": "Energia",
    "BBDC4": "Financeiro",
    "ITUB4": "Financeiro",
}

TODOS_ATIVOS = list(SETOR_POR_ATIVO)
SETORES = ["Todos"] + sorted(set(SETOR_POR_ATIVO.values()))
CORES_ATIVOS = px.colors.qualitative.Dark24


@st.cache_data(ttl=3600)
def carregar_dados():
    """Tenta consultar PostgreSQL; se falhar, usa o CSV do projeto."""
    try:
        conexao = st.connection("postgresql", type="sql")
        df = conexao.query(
            "SELECT * FROM indicadores_diarios_2021_2023",
            ttl=3600,
        )

        if df.empty:
            df = None
            origem = "CSV do repositório (fallback)"
        else:
            origem = "PostgreSQL"

    except Exception:
        df = None
        origem = "CSV do repositório (fallback)"

    if df is None:
        df = pd.read_csv(ARQUIVO_CSV)

    df.columns = [str(col).strip().lower() for col in df.columns]
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    colunas_numericas = [
        "fechamento_ajustado",
        "volume_financeiro_estimado",
        "sma_21",
        "sma_50",
        "drawdown",
    ]

    for coluna in colunas_numericas:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df = (
        df.dropna(
            subset=["data", "ticker", "fechamento_ajustado"]
        )
        .drop_duplicates(subset=["data", "ticker"])
        .sort_values(["ticker", "data"])
        .reset_index(drop=True)
    )

    return df, origem


try:
    dados, origem = carregar_dados()
except Exception as erro:
    st.error(f"Não foi possível carregar a base: {erro}")
    st.stop()

dados = dados[dados["ticker"].isin(TODOS_ATIVOS)].copy()

if dados.empty:
    st.error("A base não contém os ativos esperados para este projeto.")
    st.stop()

data_inicial = dados["data"].min().date()
data_final = dados["data"].max().date()


def ativos_do_setor():
    setor = st.session_state.get("setor", "Todos")

    if setor == "Todos":
        st.session_state["ativos"] = TODOS_ATIVOS.copy()
    else:
        st.session_state["ativos"] = [
            ativo
            for ativo, nome_setor in SETOR_POR_ATIVO.items()
            if nome_setor == setor
        ]


def resetar_filtros():
    st.session_state["setor"] = "Todos"
    st.session_state["ativos"] = TODOS_ATIVOS.copy()
    st.session_state["periodo"] = (data_inicial, data_final)


if "setor" not in st.session_state:
    st.session_state["setor"] = "Todos"

if "ativos" not in st.session_state:
    st.session_state["ativos"] = TODOS_ATIVOS.copy()

if "periodo" not in st.session_state:
    st.session_state["periodo"] = (data_inicial, data_final)


with st.sidebar:
    st.title("Explorar carteira")
    st.caption("Ajuste os filtros para personalizar a análise.")

    st.selectbox(
        "Grupo setorial",
        SETORES,
        key="setor",
        on_change=ativos_do_setor,
    )

    if st.session_state["setor"] == "Todos":
        ativos_disponiveis = TODOS_ATIVOS
    else:
        ativos_disponiveis = [
            ativo
            for ativo, setor in SETOR_POR_ATIVO.items()
            if setor == st.session_state["setor"]
        ]

    st.multiselect(
        "Ativos",
        options=ativos_disponiveis,
        key="ativos",
        placeholder="Selecione um ou mais ativos",
    )

    st.date_input(
        "Período de análise",
        min_value=data_inicial,
        max_value=data_final,
        key="periodo",
    )

    st.button(
        "Restaurar filtros",
        on_click=resetar_filtros,
        use_container_width=True,
    )

    st.divider()
    st.caption("Janela histórica disponível: 2021–2023")


periodo_selecionado = st.session_state["periodo"]

if (
    isinstance(periodo_selecionado, (tuple, list))
    and len(periodo_selecionado) == 2
):
    inicio, fim = periodo_selecionado
else:
    inicio = fim = periodo_selecionado

ativos_selecionados = st.session_state["ativos"]

if not ativos_selecionados:
    st.warning("Selecione pelo menos um ativo na barra lateral.")
    st.stop()

# Calcula os retornos antes de aplicar o filtro de datas.
dados_ativos = dados[
    dados["ticker"].isin(ativos_selecionados)
].copy()

dados_ativos = dados_ativos.sort_values(["ticker", "data"])

dados_ativos["retorno_diario"] = (
    dados_ativos.groupby("ticker")["fechamento_ajustado"]
    .pct_change()
)

filtro_data = dados_ativos["data"].dt.date.between(inicio, fim)
df = dados_ativos.loc[filtro_data].copy()

if df.empty:
    st.warning("Não há dados para os filtros selecionados.")
    st.stop()

df = df.sort_values(["ticker", "data"]).reset_index(drop=True)
df["setor"] = df["ticker"].map(SETOR_POR_ATIVO)

# Base 100 a partir do primeiro pregão visível de cada ativo.
df["base_100_periodo"] = (
    df["fechamento_ajustado"]
    / df.groupby("ticker")["fechamento_ajustado"].transform("first")
    * 100
)

df["retorno_diario_pct"] = df["retorno_diario"] * 100

# Resumo de risco e retorno no período selecionado.
linhas_resumo = []

for ticker, grupo_ativo in df.groupby("ticker"):
    retornos = grupo_ativo["retorno_diario"].dropna()
    desvio_diario = retornos.std()

    retorno_acumulado = (
        grupo_ativo["fechamento_ajustado"].iloc[-1]
        / grupo_ativo["fechamento_ajustado"].iloc[0]
        - 1
    )

    volatilidade = desvio_diario * (252 ** 0.5)

    sharpe = (
        retornos.mean() / desvio_diario * (252 ** 0.5)
        if pd.notna(desvio_diario) and desvio_diario != 0
        else float("nan")
    )

    if "volume_financeiro_estimado" in grupo_ativo.columns:
        giro_medio = grupo_ativo["volume_financeiro_estimado"].mean()
    else:
        giro_medio = float("nan")

    if "drawdown" in grupo_ativo.columns:
        drawdown_maximo = grupo_ativo["drawdown"].min() * 100
    else:
        drawdown_maximo = float("nan")

    linhas_resumo.append(
        {
            "ticker": ticker,
            "setor": SETOR_POR_ATIVO[ticker],
            "retorno_acumulado_pct": retorno_acumulado * 100,
            "volatilidade_anualizada_pct": volatilidade * 100,
            "sharpe_rf_zero": sharpe,
            "drawdown_maximo_pct": drawdown_maximo,
            "volume_financeiro_medio": giro_medio,
        }
    )

resumo = pd.DataFrame(linhas_resumo)

retorno_medio = resumo["retorno_acumulado_pct"].mean()
volatilidade_media = resumo["volatilidade_anualizada_pct"].mean()
volatilidade_mediana = resumo["volatilidade_anualizada_pct"].median()

melhor = resumo.loc[resumo["retorno_acumulado_pct"].idxmax()]
pior = resumo.loc[resumo["retorno_acumulado_pct"].idxmin()]

# Retorno anual entre o primeiro e o último pregão visível de cada ano.
df["ano"] = df["data"].dt.year

retorno_anual = (
    df.sort_values(["ticker", "data"])
    .groupby(["ticker", "setor", "ano"], as_index=False)
    .agg(
        preco_inicio_ano=("fechamento_ajustado", "first"),
        preco_fim_ano=("fechamento_ajustado", "last"),
    )
)

retorno_anual["retorno_anual_pct"] = (
    retorno_anual["preco_fim_ano"]
    / retorno_anual["preco_inicio_ano"]
    - 1
) * 100

# Retorno setorial: média simples dos retornos anuais dos ativos.
retorno_setorial = (
    retorno_anual.groupby(["setor", "ano"], as_index=False)
    .agg(
        retorno_medio_pct=("retorno_anual_pct", "mean"),
        quantidade_ativos=("ticker", "nunique"),
    )
)

# Correlação de Pearson sobre retornos diários.
matriz_retornos = df.pivot(
    index="data",
    columns="ticker",
    values="retorno_diario",
)

matriz_correlacao = matriz_retornos.corr(min_periods=20)

# Cabeçalho do painel.
st.markdown(
    """
    <section class="hero-card">
      <div class="hero-kicker">Painel de mercado • B3</div>
      <div class="hero-title">Carteira em foco</div>
      <p class="hero-subtitle">
        Desempenho, risco e comportamento de 12 ações brasileiras
        em uma leitura clara e interativa.
      </p>
    </section>
    """,
    unsafe_allow_html=True,
)

st.caption(
    f"Janela: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} "
    f"· {len(ativos_selecionados)} ativo(s) selecionado(s) "
    f"· Fonte: {origem}"
)

with st.container(border=True):
    st.markdown("#### Leitura do período")
    st.markdown(
        f"**{melhor['ticker']}** liderou o retorno acumulado "
        f"(**{melhor['retorno_acumulado_pct']:.2f}%**); "
        f"**{pior['ticker']}** apresentou o menor resultado "
        f"(**{pior['retorno_acumulado_pct']:.2f}%**). "
        "Os números descrevem o intervalo selecionado e "
        "não demonstram causalidade."
    )

c1, c2, c3, c4 = st.columns(4)

with c1.container(border=True):
    st.metric(
        "Retorno médio dos ativos",
        f"{retorno_medio:.2f}%",
        delta=f"{retorno_medio:+.2f} p.p. em relação a 0%",
    )

with c2.container(border=True):
    st.metric(
        "Maior retorno",
        melhor["ticker"],
        delta=f"{melhor['retorno_acumulado_pct']:+.2f}% no período",
    )

with c3.container(border=True):
    st.metric(
        "Menor retorno",
        pior["ticker"],
        delta=f"{pior['retorno_acumulado_pct']:+.2f}% no período",
    )

with c4.container(border=True):
    st.metric(
        "Volatilidade anualizada média",
        f"{volatilidade_media:.2f}%",
        delta=(
            f"{volatilidade_media - volatilidade_mediana:+.2f} "
            "p.p. vs. mediana"
        ),
    )

aba_visao, aba_anual_setor, aba_risco, aba_tendencia, aba_dados = st.tabs(
    [
        "Visão geral",
        "Retorno anual e setores",
        "Risco e correlação",
        "Tendência",
        "Dados",
    ]
)


with aba_visao:
    st.subheader("Desempenho acumulado — Base 100")
    st.caption(
        "Cada ativo começa em 100 no primeiro pregão visível. "
        "O fechamento ajustado considera ajustes históricos informados pela fonte."
    )

    fig_base100 = px.line(
        df,
        x="data",
        y="base_100_periodo",
        color="ticker",
        color_discrete_sequence=CORES_ATIVOS,
        labels={
            "data": "Data",
            "base_100_periodo": "Índice (base 100)",
            "ticker": "Ativo",
        },
        template="plotly_white",
    )

    fig_base100.add_hline(
        y=100,
        line_dash="dash",
        line_color="#7B8794",
    )

    fig_base100.update_layout(
        height=520,
        legend_title_text="Ativo",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.2,
            "xanchor": "left",
            "x": 0,
        },
        margin={"l": 10, "r": 10, "t": 25, "b": 70},
        hovermode="x unified",
    )

    st.plotly_chart(fig_base100, use_container_width=True)

    st.subheader("Risco e retorno no período")

    fig_risco_retorno = px.scatter(
        resumo,
        x="volatilidade_anualizada_pct",
        y="retorno_acumulado_pct",
        color="setor",
        color_discrete_sequence=px.colors.qualitative.Set2,
        size="volume_financeiro_medio",
        size_max=32,
        hover_name="ticker",
        hover_data={
            "sharpe_rf_zero": ":.2f",
            "drawdown_maximo_pct": ":.2f",
            "volume_financeiro_medio": ":,.0f",
        },
        labels={
            "volatilidade_anualizada_pct": "Volatilidade anualizada (%)",
            "retorno_acumulado_pct": "Retorno acumulado (%)",
            "volume_financeiro_medio": "Giro financeiro estimado médio (R$)",
            "setor": "Grupo setorial",
        },
        template="plotly_white",
    )

    fig_risco_retorno.add_hline(
        y=0,
        line_dash="dash",
        line_color="#7B8794",
    )

    fig_risco_retorno.update_layout(
        height=440,
        margin={"l": 10, "r": 10, "t": 25, "b": 20},
    )

    st.plotly_chart(fig_risco_retorno, use_container_width=True)


with aba_anual_setor:
    st.subheader("Retorno anual por ativo")
    st.caption(
        "Retorno entre o primeiro e o último pregão disponível de cada ano "
        "no intervalo selecionado. Se as datas filtradas não cobrirem o ano "
        "inteiro, o resultado representa um período parcial."
    )

    fig_anual = px.bar(
        retorno_anual,
        x="ticker",
        y="retorno_anual_pct",
        color="ano",
        barmode="group",
        color_discrete_sequence=px.colors.qualitative.Set2,
        text_auto=".1f",
        labels={
            "ticker": "Ativo",
            "retorno_anual_pct": "Retorno anual (%)",
            "ano": "Ano",
        },
        template="plotly_white",
    )

    fig_anual.add_hline(
        y=0,
        line_color="#7B8794",
        line_dash="dash",
    )

    fig_anual.update_layout(
        height=480,
        margin={"l": 10, "r": 10, "t": 25, "b": 20},
    )

    st.plotly_chart(fig_anual, use_container_width=True)

    st.subheader("Comparação por grupo setorial")
    st.caption(
        "Cada grupo recebe o mesmo peso. O retorno é a média simples dos "
        "retornos dos ativos disponíveis. A classificação setorial é uma "
        "simplificação analítica documentada no projeto."
    )

    fig_setores = px.bar(
        retorno_setorial,
        x="setor",
        y="retorno_medio_pct",
        color="ano",
        barmode="group",
        text_auto=".1f",
        color_discrete_sequence=px.colors.qualitative.Set2,
        hover_data={"quantidade_ativos": True},
        labels={
            "setor": "Grupo setorial do projeto",
            "retorno_medio_pct": "Retorno anual médio (%)",
            "ano": "Ano",
            "quantidade_ativos": "Número de ativos",
        },
        template="plotly_white",
    )

    fig_setores.add_hline(
        y=0,
        line_color="#7B8794",
        line_dash="dash",
    )

    fig_setores.update_layout(
        height=440,
        margin={"l": 10, "r": 10, "t": 25, "b": 20},
    )

    st.plotly_chart(fig_setores, use_container_width=True)

    st.dataframe(
        retorno_setorial.sort_values(
            ["ano", "retorno_medio_pct"],
            ascending=[True, False],
        ),
        use_container_width=True,
        hide_index=True,
    )


with aba_risco:
    st.subheader("Correlação entre retornos diários")
    st.caption(
        "Correlação de Pearson calculada sobre retornos diários. Valores "
        "próximos de 1 indicam movimentos historicamente semelhantes; "
        "valores próximos de 0 indicam associação linear fraca. "
        "Correlação não implica causalidade."
    )

    if matriz_correlacao.shape[0] >= 2:
        fig_corr = px.imshow(
            matriz_correlacao,
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
            text_auto=".2f",
            aspect="auto",
            labels={
                "x": "Ativo",
                "y": "Ativo",
                "color": "Correlação",
            },
            template="plotly_white",
        )

        fig_corr.update_layout(
            height=650,
            margin={"l": 10, "r": 10, "t": 25, "b": 20},
        )

        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("Selecione pelo menos dois ativos para calcular a correlação.")

    st.subheader("Distribuição dos retornos diários")
    retornos_grafico = df.dropna(subset=["retorno_diario_pct"])

    if not retornos_grafico.empty:
        fig_hist = px.histogram(
            retornos_grafico,
            x="retorno_diario_pct",
            color="ticker",
            color_discrete_sequence=CORES_ATIVOS,
            marginal="box",
            barmode="overlay",
            opacity=0.5,
            labels={
                "retorno_diario_pct": "Retorno diário (%)",
                "ticker": "Ativo",
            },
            template="plotly_white",
        )

        fig_hist.update_layout(
            height=480,
            margin={"l": 10, "r": 10, "t": 25, "b": 20},
        )

        st.plotly_chart(fig_hist, use_container_width=True)

    st.subheader("Drawdown ao longo do período")

    if "drawdown" in df.columns:
        fig_drawdown = px.area(
            df,
            x="data",
            y="drawdown",
            color="ticker",
            color_discrete_sequence=CORES_ATIVOS,
            labels={
                "data": "Data",
                "drawdown": "Drawdown",
                "ticker": "Ativo",
            },
            template="plotly_white",
        )

        fig_drawdown.update_yaxes(tickformat=".0%")
        fig_drawdown.update_layout(
            height=450,
            margin={"l": 10, "r": 10, "t": 25, "b": 20},
        )

        st.plotly_chart(fig_drawdown, use_container_width=True)


with aba_tendencia:
    st.subheader("Preço e médias móveis")

    ativo_tendencia = st.selectbox(
        "Ativo para analisar",
        options=ativos_selecionados,
        key="ativo_tendencia",
    )

    df_ativo = df[df["ticker"] == ativo_tendencia].copy()

    colunas_sma = [
        coluna
        for coluna in ["fechamento_ajustado", "sma_21", "sma_50"]
        if coluna in df_ativo.columns
    ]

    if len(colunas_sma) >= 2:
        linhas = df_ativo.melt(
            id_vars="data",
            value_vars=colunas_sma,
            var_name="serie",
            value_name="preco",
        )

        linhas["serie"] = linhas["serie"].map(
            {
                "fechamento_ajustado": "Fechamento ajustado",
                "sma_21": "SMA 21",
                "sma_50": "SMA 50",
            }
        )

        fig_sma = px.line(
            linhas,
            x="data",
            y="preco",
            color="serie",
            labels={
                "data": "Data",
                "preco": "Preço (R$)",
                "serie": "Série",
            },
            title=f"{ativo_tendencia}: fechamento e médias móveis",
            color_discrete_sequence=["#174A7E", "#2A9D8F", "#E9A23B"],
            template="plotly_white",
        )

        fig_sma.update_layout(
            height=500,
            margin={"l": 10, "r": 10, "t": 50, "b": 20},
        )

        st.plotly_chart(fig_sma, use_container_width=True)
    else:
        st.warning(
            "A base precisa conter fechamento ajustado e ao menos uma SMA."
        )


with aba_dados:
    st.subheader("Base filtrada")
    st.caption(
        f"{len(df):,} registros para "
        f"{len(ativos_selecionados)} ativo(s)."
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    csv_filtrado = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Baixar dados filtrados em CSV",
        data=csv_filtrado,
        file_name="acoes_b3_filtradas.csv",
        mime="text/csv",
    )

    st.caption(
        "O Sharpe assume taxa livre de risco igual a zero. O giro financeiro "
        "é estimado por fechamento × volume de ações e não representa o valor "
        "oficial negociado no pregão. Os grupos setoriais são simplificações "
        "analíticas."
    )