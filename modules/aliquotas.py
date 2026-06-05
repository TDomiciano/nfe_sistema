import pandas as pd
import streamlit as st


@st.cache_data
def carregar_aliquotas():

    tabela_icms = pd.read_excel(
        "aliquotas.xlsx",
        sheet_name="ICMS_DIFAL",
        index_col=0
    )

    tabela_fcp = pd.read_excel(
        "aliquotas.xlsx",
        sheet_name="FCP"
    )

    tabela_icms.index = (
        tabela_icms.index.astype(str)
        .str.upper()
        .str.strip()
    )

    tabela_icms.columns = (
        tabela_icms.columns.astype(str)
        .str.upper()
        .str.strip()
    )

    tabela_fcp["UF"] = (
        tabela_fcp["UF"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    return tabela_icms, tabela_fcp


def obter_aliquota_interestadual(
    tabela_icms,
    uf_origem,
    uf_destino
):

    try:

        return float(
            tabela_icms.loc[
                uf_origem.upper().strip(),
                uf_destino.upper().strip()
            ]
        ) / 100

    except Exception:

        return 0


def obter_aliquota_interna(
    tabela_icms,
    uf_destino
):

    try:

        return float(
            tabela_icms.loc[
                uf_destino.upper().strip(),
                uf_destino.upper().strip()
            ]
        ) / 100

    except Exception:

        return 0


def obter_fcp(
    tabela_fcp,
    uf_destino
):

    try:

        linha = tabela_fcp[
            tabela_fcp["UF"]
            ==
            uf_destino.upper().strip()
        ]

        if not linha.empty:

            return float(
                linha.iloc[0]["FCP"]
            ) / 100

    except:
        pass

    return 0