from pathlib import Path

import pandas as pd
import yfinance as yf

tickers = [
    "WEGE3.SA", "EMBJ3.SA", "VALE3.SA", "GGBR4.SA",
    "KLBN11.SA", "PETR4.SA", "PRIO3.SA", "EGIE3.SA",
    "ITUB4.SA", "BBDC4.SA", "ABEV3.SA", "RENT3.SA",
]

# A data final é exclusiva: 2024-01-01 inclui os pregões até 31/12/2023.
dados = yf.download(
    tickers,
    start="2021-01-01",
    end="2024-01-01",
    auto_adjust=False,
    group_by="ticker",
    progress=False,
    threads=False,
)

if dados.empty:
    raise ValueError("O download não retornou dados. Verifique a conexão e os tickers.")

lista_dfs = []

for ticker in tickers:
    try:
        # Com vários ativos, o yfinance costuma organizar as colunas por ticker.
        if isinstance(dados.columns, pd.MultiIndex):
            if ticker in dados.columns.get_level_values(0):
                df_ticker = dados[ticker].copy()
            else:
                raise KeyError(ticker)
        else:
            df_ticker = dados.copy()

        df_ticker = df_ticker.reset_index()

        # Alguns tickers podem não retornar todas as colunas esperadas.
        colunas_necessarias = [
            "Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"
        ]
        faltantes = [col for col in colunas_necessarias if col not in df_ticker.columns]
        if faltantes:
            print(f"{ticker}: sem as colunas {faltantes}; ativo ignorado.")
            continue

        df_ticker = df_ticker[colunas_necessarias].rename(columns={
            "Date": "data",
            "Open": "abertura",
            "High": "maxima",
            "Low": "minima",
            "Close": "fechamento",
            "Adj Close": "fechamento_ajustado",
            "Volume": "volume_acoes",
        })

        df_ticker["ticker"] = (
    "EMBR3" if ticker == "EMBJ3.SA" else ticker.replace(".SA", "")
)
        df_ticker["data"] = pd.to_datetime(df_ticker["data"], errors="coerce")

        # Estimativa de giro financeiro, não o valor oficial negociado no pregão.
        df_ticker["volume_financeiro_estimado"] = (
            df_ticker["fechamento"] * df_ticker["volume_acoes"]
        )

        lista_dfs.append(df_ticker)

    except KeyError:
        print(f"{ticker}: dados não encontrados; ativo ignorado.")

if not lista_dfs:
    raise ValueError("Nenhum ativo retornou dados utilizáveis.")

df_b3 = pd.concat(lista_dfs, ignore_index=True)

df_b3 = (
    df_b3
    .dropna(subset=["data", "fechamento_ajustado"])
    .drop_duplicates(subset=["data", "ticker"])
    .sort_values(["data", "ticker"])
    .reset_index(drop=True)
)

pasta_saida = Path("data")
pasta_saida.mkdir(parents=True, exist_ok=True)
arquivo_saida = pasta_saida / "precos_acoes_2021_2023.csv"

df_b3.to_csv(arquivo_saida, index=False, encoding="utf-8")

print(f"Arquivo salvo em: {arquivo_saida}")
print(f"Linhas: {len(df_b3):,}")
print(f"Ativos encontrados: {sorted(df_b3['ticker'].unique())}")
print(df_b3.head())


#== Validação dos dados baixados =#
print("\nResumo por ativo:")
print(
    df_b3.groupby("ticker").agg(
        registros=("data", "size"),
        inicio=("data", "min"),
        fim=("data", "max"),
    )
)

print("\nDuplicatas de data e ativo:",
      df_b3.duplicated(subset=["data", "ticker"]).sum())

print("\nValores ausentes por coluna:")
print(df_b3.isna().sum())

# Indicadores diários por ativo
df_analise = df_b3.copy()
df_analise.columns.name = None
df_analise = df_analise.sort_values(["ticker", "data"]).reset_index(drop=True)

grupo_preco = df_analise.groupby("ticker")["fechamento_ajustado"]

df_analise["retorno_diario"] = grupo_preco.pct_change()

preco_inicial = grupo_preco.transform("first")
df_analise["base_100"] = (
    df_analise["fechamento_ajustado"] / preco_inicial * 100
)

df_analise["sma_21"] = grupo_preco.transform(
    lambda serie: serie.rolling(21, min_periods=21).mean()
)
df_analise["sma_50"] = grupo_preco.transform(
    lambda serie: serie.rolling(50, min_periods=50).mean()
)

df_analise["pico_historico"] = grupo_preco.transform("cummax")
df_analise["drawdown"] = (
    df_analise["fechamento_ajustado"] / df_analise["pico_historico"] - 1
)

# Resumo de risco e retorno
resumo_ativos = []

for ticker, grupo in df_analise.groupby("ticker"):
    retornos = grupo["retorno_diario"].dropna()
    desvio_diario = retornos.std()

    retorno_acumulado = (
        grupo["fechamento_ajustado"].iloc[-1]
        / grupo["fechamento_ajustado"].iloc[0]
        - 1
    )
    volatilidade_anualizada = desvio_diario * (252 ** 0.5)
    sharpe_rf_zero = (
        retornos.mean() / desvio_diario * (252 ** 0.5)
        if desvio_diario != 0 else float("nan")
    )

    resumo_ativos.append({
        "ticker": ticker,
        "retorno_acumulado_pct": retorno_acumulado * 100,
        "volatilidade_anualizada_pct": volatilidade_anualizada * 100,
        "sharpe_rf_zero": sharpe_rf_zero,
        "drawdown_maximo_pct": grupo["drawdown"].min() * 100,
    })

resumo = pd.DataFrame(resumo_ativos)

df_analise.to_csv(
    pasta_saida / "indicadores_diarios_2021_2023.csv",
    index=False,
    encoding="utf-8",
)
resumo.to_csv(
    pasta_saida / "resumo_ativos_2021_2023.csv",
    index=False,
    encoding="utf-8",
)

print("\nResumo de desempenho por ativo:")
print(resumo.sort_values("retorno_acumulado_pct", ascending=False).to_string(index=False))

print(
    "\nRetorno médio da carteira igualmente ponderada: "
    f"{resumo['retorno_acumulado_pct'].mean():.2f}%"
)
print(
    "Volatilidade anualizada média: "
    f"{resumo['volatilidade_anualizada_pct'].mean():.2f}%"
)
