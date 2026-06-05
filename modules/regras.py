import pandas as pd
import streamlit as st

@st.cache_data
def carregar_regras():

    regras = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config ST"
    )

    regras_st = pd.read_excel (
        "conf_fiscais.xlxs",
        sheet_name="Config ST"
    )

    return regras, regras_st
    