import streamlit as st
import pandas as pd
import io
import zipfile

from modules.regras import carregar_regras
from modules.aliquotas import carregar_aliquotas
from modules.processador_xml import processar_xmls
from modules.sequencias import verificar_quebras
from modules.exportacao import gerar_excel

# =========================
# CONFIG
# =========================
st.set_page_config(
    layout="wide",
    page_title="Domiciano Auditor Fiscal"
)

# =========================
# STATE (OBRIGATÓRIO)
# =========================
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

# =========================
# CONFIGS
# =========================
regras, regras_st = carregar_regras()
tabela_icms, tabela_fcp = carregar_aliquotas()

# =========================
# UPLOAD
# =========================
uploads = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True,
    key=f"upload_xmls_{st.session_state.upload_key}"
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

                        xml_file = io.BytesIO(zip_ref.read(nome))
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

    # =========================
    # BOTÕES (LAYOUT ANTIGO)
    # =========================
    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🔄 Nova Auditoria"):
            st.session_state.upload_key += 1
            st.rerun()

    with col2:
        st.success(f"✅ {len(df)} registros encontrados")

    st.divider()

    # =========================
    # RESUMO
    # =========================
    col1, col2, col3 = st.columns(3)

    col1.metric("Registros", len(df))

    col2.metric(
        "Canceladas",
        len(df[df["Status"] == "CANCELADA"])
    )

    df_quebras = verificar_quebras(df)

    col3.metric(
        "Quebras",
        len(df_quebras) if not df_quebras.empty else 0
    )

    st.divider()

    # =========================
    # AUDITORIA SEQUÊNCIA
    # =========================
    st.subheader("🔎 Auditoria Sequência NF")

    if not df_quebras.empty:
        st.warning("⚠️ Quebras encontradas")
        st.dataframe(df_quebras, use_container_width=True)
    else:
        st.success("✅ Nenhuma quebra encontrada")

    st.divider()

    # =========================
    # CANCELADAS
    # =========================
    st.subheader("🚫 NF Canceladas")

    df_canceladas = df[df["Status"] == "CANCELADA"].copy()

    if not df_canceladas.empty:
        st.dataframe(df_canceladas, use_container_width=True)
    else:
        st.success("✅ Nenhuma NF cancelada")

    st.divider()

    # =========================
    # DOWNLOAD
    # =========================
    output = gerar_excel(df, df_quebras, df_canceladas)

    st.download_button(
        "⬇️ Baixar Excel",
        output,
        file_name="auditoria_fiscal.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    # =========================
    # TABELA PRINCIPAL
    # =========================
    st.subheader("📊 Auditoria Fiscal")

    st.dataframe(df, use_container_width=True)

else:

    st.info("Envie XML ou ZIP")