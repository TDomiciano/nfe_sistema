import streamlit as st
import pandas as pd
import io
import zipfile

from modules.regras import carregar_regras, carregar_cfops
from modules.aliquotas import carregar_aliquotas
from modules.processador_xml import processar_xmls
from modules.sequencias import verificar_quebras
from modules.exportacao import gerar_excel
from modules.exportacao_entradas import gerar_excel_entradas
from modules.tela_entradas import mostrar_tela_entradas
from modules.processador_entradas import processar_entradas
from modules.auditoria_entradas import auditar_entradas

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Domiciano Auditor Fiscal",
    page_icon="📊",
    layout="wide"
)

# =========================
# CSS
# =========================
st.markdown("""
<style>

.block-container{
    padding-top:2.5rem;
    padding-left:2rem;
    padding-right:2rem;
}

.metric-card{
    background:white;
    padding:20px;
    border-radius:12px;
    text-align:center;
    box-shadow:0 1px 5px rgba(0,0,0,0.08);
}

.metric-value{
    font-size:32px;
    font-weight:bold;
}

.metric-title{
    color:#666;
    font-size:14px;
}

</style>
""", unsafe_allow_html=True)

# =========================
# SIDEBAR
# =========================
with st.sidebar:

    st.markdown("## Domiciano")
    st.caption("Auditor Fiscal")

    st.divider()

    tipo_auditoria = st.radio(
        "📂 Módulo",
        [
            "📤 Auditoria de Saídas",
            "📥 Auditoria de Entradas (Compras)"
        ]
    )

    st.divider()

    if tipo_auditoria == "📤 Auditoria de Saídas":

        st.success("📤 Módulo ativo")
        st.markdown("""
- ✅ Auditoria Fiscal
- ✅ DIFAL
- ✅ FCP
- ✅ Devoluções
- ✅ Sequência Numérica
- ✅ Notas Canceladas
""")
    else:
        st.success("📥 Módulo ativo")
        st.markdown("""
- ✅ Crédito de ICMS
- ✅ Crédito de IBS
- ✅ Crédito de CBS
- ✅ CFOP Esperado
- ✅ CST
- ✅ NCM
- ✅ XML Duplicado
""")
    st.divider()

    st.caption("Versão 2.0")

# =========================
# CABEÇALHO
# =========================
col_logo, col_titulo = st.columns([0.80, 5.8], gap="small")

with col_logo:
    st.image("logo1.png", width=660)
     
with col_titulo:

    st.markdown("""
    # Auditor Fiscal

    #### Plataforma Inteligente de Auditoria Tributária

    *Validação de NF-e • DIFAL • FCP • Sequência • Devoluções*
    """)


# =========================
# STATE
# =========================
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

# =========================
# CONFIGURAÇÕES
# =========================
regras, regras_st = carregar_regras()

tabela_icms, tabela_fcp = carregar_aliquotas()

cfops = carregar_cfops()

def carregar_cfops():

    df = pd.read_excel(
        "config.xlsx",
        sheet_name="CFOP"
    )

    df.columns = ["CFOP SAÍDA", "CFOP ENTRADA", "TIPO OPERAÇÃO", "DESCRIÇÃO"]

    return df

# =========================
# UPLOAD
# =========================
if tipo_auditoria == "📤 Auditoria de Saídas":
    st.markdown("## 📂 Envie os XML ou ZIP das NF-e de Saída")

else:
    st.markdown("## 📂 Envie os XML ou ZIP das NF-e de Entrada")

uploads = st.file_uploader(
    "",
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

            with zipfile.ZipFile(
                upload,
                "r"
            ) as zip_ref:

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

    if tipo_auditoria == "📤 Auditoria de Saídas":

        df = processar_xmls(
            arquivos,
            regras,
            regras_st,
            tabela_icms,
            tabela_fcp
        )

        df_quebras = verificar_quebras(df)

        df_canceladas = df[
            df["Status"] == "CANCELADA"
        ].copy()

    else:

        df = processar_entradas(
            arquivos,
            regras,
            regras_st,
            cfops
        )
    
        df = auditar_entradas(
            df,
            cfops
        )

        df_quebras = pd.DataFrame()
        df_canceladas = pd.DataFrame()
    
    # =========================
    # BOTÕES
    # =========================
    col1, col2 = st.columns([1, 1])

    with col1:

        if st.button("🔄 Nova Auditoria"):

            st.session_state.upload_key += 1
            st.rerun()

    with col2:

        if tipo_auditoria == "📤 Auditoria de Saídas":
            
            st.success(
                f"{len(df)} registros encontrados"
            )

        else:
            st.success(
                f"{df['Chave'].nunique()} notas encontradas"
            )

    st.divider()

    # =========================
    # CARDS
    # =========================
    if tipo_auditoria == "📤 Auditoria de Saídas":
    
        total_notas = df["Chave"].nunique()

        total_autorizadas = (
            df[df["Status"] == "AUTORIZADA"]["Chave"]
            .nunique()
        )

        total_canceladas = (
            df[df["Status"] == "CANCELADA"]["Chave"]
            .nunique()
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "📄 Total de Notas",
                total_notas
            )

        with col2:
            st.metric(
                "✅ Autorizadas",
                total_autorizadas
            )

        with col3:
            st.metric(
                "🚫 Canceladas",
                total_canceladas
            )
    else:
        total_notas = df["Chave"].nunique()

        total_fornecedores = (
            df["CNPJ EMITENTE"]
            .dropna()
            .nunique()
        )
    
    st.divider()

    # =========================
    # ABAS
    # =========================
    if tipo_auditoria == "📤 Auditoria de Saídas":
    
        tab1, tab2, tab3 = st.tabs([
            "📊 Auditoria",
            "🔎 Sequência",
            "📥 Exportação"
        ])

    # =========================
    # ABA AUDITORIA
    # =========================
        with tab1:

            st.markdown("### 🔍 Filtros")

            col1, col2 = st.columns(2)

            with col1:

                status_filtro = st.multiselect(
                    "Status",
                    options=sorted(df["Status"].dropna().unique()),
                    default=sorted(df["Status"].dropna().unique())
                )

            with col2:

                uf_filtro = st.multiselect(
                    "UF Destino",
                    options=sorted(
                        df["UF Destino"]
                        .dropna()
                        .unique()
                    ),
                    default=sorted(
                        df["UF Destino"]
                        .dropna()
                        .unique()
                    )
                )

            df_filtrado = df[
                (df["Status"].isin(status_filtro))
                &
                (df["UF Destino"].isin(uf_filtro))
            ]

            st.divider()

            st.dataframe(
                df_filtrado,
                use_container_width=True,
                hide_index=True
            )

    # =========================
    # ABA SEQUÊNCIA
    # =========================
        with tab2:

            if not df_quebras.empty:

                st.warning(
                   "⚠️ Quebras encontradas"
                )

                st.dataframe(
                    df_quebras,
                    use_container_width=True
                )
                
            else:

                st.success(
                    "✅ Nenhuma quebra encontrada"
                )

    # =========================
    # ABA EXPORTAÇÃO
    # =========================
        with tab3:

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
        mostrar_tela_entradas(df, cfops)