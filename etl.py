from pathlib import Path

import pandas as pd
import yfinance as yf

TICKERS = [
    "WEGE3.SA", "EMBJ3.SA", "VALE3.SA", "GGBR4.SA",
    "KLBN11.SA", "PETR4.SA", "PRIO3.SA", "EGIE3.SA",
    "ITUB4.SA", "BBDC4.SA", "ABEV3.SA", "RENT3.SA",
]

COLUNAS_NUMERICAS = [
    "abertura", "maxima", "minima", "fechamento",
    "fechamento_ajustado", "volume_acoes",
]
COLUNAS_OBRIGATORIAS = ["data", "ticker", *COLUNAS_NUMERICAS]


def obter_tabela_do_ativo(dados: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extrai as colunas de um ticker, inclusive quando a ordem dos níveis muda."""
    if not isinstance(dados.columns, pd.MultiIndex):
        if len(TICKERS) != 1:
            raise KeyError(f"Colunas sem níveis por ticker para {ticker}.")
        return dados.copy()

    nivel_tickers = [
        nivel for nivel in range(dados.columns.nlevels)
        if ticker in dados.columns.get_level_values(nivel)
    ]
    if not nivel_tickers:
        raise KeyError(ticker)
    return dados.xs(ticker, axis=1, level=nivel_tickers[0], drop_level=True).copy()


def main() -> None:
    # A data final é exclusiva; 01/01/2024 inclui os pregões até 31/12/2023.
    dados = yf.download(
        TICKERS,
        start="2021-01-01",
        end="2024-01-01",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=False,
    )
    if dados.empty:
        raise ValueError("O download não retornou dados. Verifique a conexão e os símbolos.")

    tabelas = []
    falhas = []
    campos_fonte = {
        "Date": "data",
        "Open": "abertura",
        "High": "maxima",
        "Low": "minima",
        "Close": "fechamento",
        "Adj Close": "fechamento_ajustado",
        "Volume": "volume_acoes",
    }

    for ticker_fonte in TICKERS:
        try:
            tabela = obter_tabela_do_ativo(dados, ticker_fonte).reset_index()
            if "Date" not in tabela.columns and "index" in tabela.columns:
                tabela = tabela.rename(columns={"index": "Date"})

            ausentes = [coluna for coluna in campos_fonte if coluna not in tabela.columns]
            if ausentes:
                raise ValueError(f"Colunas ausentes: {ausentes}")

            tabela = tabela[list(campos_fonte)].rename(columns=campos_fonte)
            tabela["ticker"] = (
                "EMBR3" if ticker_fonte == "EMBJ3.SA"
                else ticker_fonte.removesuffix(".SA")
            )
            tabela["data"] = pd.to_datetime(tabela["data"], errors="coerce")

            # Força conversão numérica; valores inválidos viram nulos e são tratados abaixo.
            for coluna in COLUNAS_NUMERICAS:
                tabela[coluna] = pd.to_numeric(tabela[coluna], errors="coerce")

            tabelas.append(tabela)
        except (KeyError, ValueError) as erro:
            falhas.append((ticker_fonte, str(erro)))

    if falhas:
        detalhes = "; ".join(f"{ticker}: {erro}" for ticker, erro in falhas)
        raise ValueError(f"Falha na extração de um ou mais ativos: {detalhes}")
    if not tabelas:
        raise ValueError("Nenhum ativo retornou dados utilizáveis.")

    df = pd.concat(tabelas, ignore_index=True)
    linhas_antes = len(df)
    df = df.dropna(subset=COLUNAS_OBRIGATORIAS)
    linhas_removidas = linhas_antes - len(df)

    df["volume_financeiro_estimado"] = df["fechamento"] * df["volume_acoes"]
    df = (
        df.drop_duplicates(subset=["data", "ticker"])
        .sort_values(["ticker", "data"])
        .reset_index(drop=True)
    )

    ativos_encontrados = set(df["ticker"].unique())
    ativos_esperados = {ticker.removesuffix(".SA") for ticker in TICKERS}
    ativos_esperados.discard("EMBJ3")
    ativos_esperados.add("EMBR3")
    ausentes = sorted(ativos_esperados - ativos_encontrados)
    if ausentes:
        raise ValueError(f"A base final não contém todos os ativos esperados: {ausentes}")

    # Indicadores calculados com fechamento ajustado para incorporar os ajustes da fonte.
    df = df.sort_values(["ticker", "data"]).reset_index(drop=True)
    grupo_preco = df.groupby("ticker")["fechamento_ajustado"]
    df["retorno_diario"] = grupo_preco.pct_change()
    df["base_100"] = grupo_preco.transform("first").rdiv(df["fechamento_ajustado"]) * 100
    df["sma_21"] = grupo_preco.transform(lambda serie: serie.rolling(21, min_periods=21).mean())
    df["sma_50"] = grupo_preco.transform(lambda serie: serie.rolling(50, min_periods=50).mean())
    df["pico_historico"] = grupo_preco.cummax()
    df["drawdown"] = df["fechamento_ajustado"] / df["pico_historico"] - 1
    df["ano"] = df["data"].dt.year

    resumos = []
    for ticker, grupo in df.groupby("ticker"):
        retornos = grupo["retorno_diario"].dropna()
        desvio_diario = retornos.std()
        sharpe = (
            retornos.mean() / desvio_diario * (252 ** 0.5)
            if pd.notna(desvio_diario) and desvio_diario != 0
            else float("nan")
        )
        resumos.append({
            "ticker": ticker,
            "retorno_acumulado_pct": (
                grupo["fechamento_ajustado"].iloc[-1]
                / grupo["fechamento_ajustado"].iloc[0] - 1
            ) * 100,
            "volatilidade_anualizada_pct": desvio_diario * (252 ** 0.5) * 100,
            "sharpe_rf_zero": sharpe,
            "drawdown_maximo_pct": grupo["drawdown"].min() * 100,
            "assimetria_retorno_diario": retornos.skew(),
            "curtose_excesso_retorno_diario": retornos.kurt(),
        })

    pasta_saida = Path(__file__).resolve().parent / "data"
    pasta_saida.mkdir(parents=True, exist_ok=True)
    df.to_csv(pasta_saida / "indicadores_diarios_2021_2023.csv", index=False, encoding="utf-8")
    df[COLUNAS_OBRIGATORIAS + ["volume_financeiro_estimado"]].to_csv(
        pasta_saida / "precos_acoes_2021_2023.csv", index=False, encoding="utf-8"
    )
    resumo = pd.DataFrame(resumos).sort_values("retorno_acumulado_pct", ascending=False)
    resumo.to_csv(pasta_saida / "resumo_ativos_2021_2023.csv", index=False, encoding="utf-8")

    print(f"Arquivo salvo em: {pasta_saida}")
    print(f"Linhas válidas: {len(df):,}; registros removidos por campos inválidos: {linhas_removidas}")
    print(f"Ativos: {sorted(df['ticker'].unique())}")
    print("Duplicatas data/ativo:", df.duplicated(subset=["data", "ticker"]).sum())
    print("Nulos nos campos obrigatórios:\n", df[COLUNAS_OBRIGATORIAS].isna().sum().to_string())
    print("\nResumo de risco e retorno:\n", resumo.to_string(index=False))


if __name__ == "__main__":
    main()
