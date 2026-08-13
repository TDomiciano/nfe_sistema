import pandas as pd
import streamlit as st

@st.cache_data
def carregar_regras():

    regras = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config Fiscal"
    )

    regras_st = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config ST"
    )

    regras.columns = (
        regras.columns
        .str.strip()
        .str.lower()
    )

    regras_st.columns = (
        regras_st.columns
        .str.strip()
        .str.lower()
    )

    return regras, regras_st

@st.cache_data
def carregar_cfops():

    df = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="CFOP",
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df