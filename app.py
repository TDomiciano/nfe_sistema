import streamlit as st
import pandas as pd
import io
import zipfile

from modules.regras import carregar_regras
from modules.aliquotas import carregar_aliquotas
from modules.processador_xml import processar_xmls
from modules.sequencia import verificar_quebras
from modules.exportacao import gerar_excel

# =========================
# CONFIG
# =========================
st.set_page_config(
    layout="wide",
    page_title="Domiciano Auditor Fiscal"
)

# =========================
# CARREGA CONFIGURAÇÕES
# =========================
regras, regras_st = carregar_regras()

tabela_icms, tabela_fcp = carregar_aliquotas()

# =========================
# UPLOAD
# =========================
uploads = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

arquivos = []

if uploads:

    for upload in uploads:

        if upload.name.lower().endswith(".xml"):

            arquivos.append(upload)

        elif upload.name.lower().endswith(".zip"):

            with zipfile.ZipFile(upload, "r") as zip_ref:

                for nome in zip_ref.namelist():

                    if nome.lower().endswith(".xml"):

                        xml_file = io.BytesIO(
                            zip_ref.read(nome)
                        )

                        xml_file.name = nome

                        arquivos.append(xml_file)

# =========================
# PROCESSAMENTO
# =========================
if arquivos:

    df = processar_xmls(
        arquivos,
        regras,
        regras_st,
        tabela_icms,
        tabela_fcp
    )

    st.success(
        f"{len(df)} registros encontrados"
    )

    # Sequência
    df_quebras = verificar_quebras(df)

    # Canceladas
    df_canceladas = df[
        df["Status"] == "CANCELADA"
    ].copy()

    # Tabela principal
    st.dataframe(
        df,
        use_container_width=True
    )

    # Excel
    output = gerar_excel(
        df,
        df_quebras,
        df_canceladas
    )

    st.download_button(
        "⬇️ Baixar Excel",
        output,
        file_name="auditoria_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:

    st.info(
        "Envie XML ou ZIP"
    )