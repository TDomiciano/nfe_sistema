import streamlit as st
import pandas as pd

from modules.exportacao_entradas import gerar_excel_entradas


def mostrar_tela_entradas(df, cfops):

    # =========================
    # CARDS
    # =========================
    total_notas = df["Chave"].nunique()

    total_fornecedores = (
        df["CNPJ EMITENTE"]
        .dropna()
        .nunique()
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "📄 Total de Notas",
            total_notas
        )

    with col2:
        st.metric(
            "🏭 Fornecedores",
            total_fornecedores
        )

    st.divider()

    # =========================
    # ABAS
    # =========================
    tab1, tab2 = st.tabs([
        "📊 Auditoria",
        "📥 Exportação"
    ])

    # =========================
    # ABA AUDITORIA
    # =========================
    with tab1:

        st.markdown("### 🔍 Filtros")

        col1, col2 = st.columns(2)

        with col1:

            fornecedor = st.multiselect(
                "Fornecedor",
                options=sorted(df["EMITENTE"].dropna().unique()),
                default=sorted(df["EMITENTE"].dropna().unique())
            )

        with col2:

            cfop = st.multiselect(
                "CFOP Nota",
                options=sorted(df["CFOP NOTA"].dropna().unique()),
                default=sorted(df["CFOP NOTA"].dropna().unique())
            )

        df_filtrado = df[
            (df["EMITENTE"].isin(fornecedor))
            &
            (df["CFOP NOTA"].isin(cfop))
        ]

        # =========================
        # RESUMO POR NOTA
        # =========================
        df_notas = (
            df_filtrado
            .groupby("Chave", as_index=False)
            .agg({
                "NF": "first",
                "EMISSÃO": "first",
                "EMITENTE": "first",
                "VALOR NF": "first",
                "CFOP NOTA": "first",
                "TIPO OPERAÇÃO": "first",
                "CFOP ENTRADA": "first",
                "DESCRIÇÃO": "first"
            })
        )

        st.divider()

        # =========================
        # TABELA EDITÁVEL
        # =========================
        if "df_notas" not in st.session_state:
            st.session_state.df_notas = df_notas.copy()
        
        st.session_state.df_notas = st.data_editor(
            st.session_state.df_notas,
            key="editor_entradas",
            use_container_width=True,
            hide_index=True,
            column_config={
                "TIPO OPERAÇÃO": st.column_config.SelectboxColumn(
                    "Finalidade da Compra",
                    options=sorted(
                        cfops["TIPO OPERAÇÃO"]
                        .dropna()
                        .unique()
                    )
                )
            },
            disabled=[
                "NF",
                "EMISSÃO",
                "EMITENTE",
                "VALOR NF",
                "CFOP NOTA",
                "CFOP ENTRADA",
                "DESCRIÇÃO"
            ]
        )

        for i, nota in st.session_state.df_notas.iterrows():
            
            regra = cfops[
                (cfops["CFOP SAÍDA"].astype(str).str.strip() == str(nota["CFOP NOTA"]).strip())
                &
                (cfops["TIPO OPERAÇÃO"] == nota["TIPO OPERAÇÃO"])
            ]
            
            if not regra.empty:

                novo_cfop = regra.iloc[0]["CFOP ENTRADA"]
                descricao = regra.iloc[0]["DESCRIÇÃO"]

                st.session_state.df_notas.at[i, "CFOP ENTRADA"] = novo_cfop
                st.session_state.df_notas.at[i, "DESCRIÇÃO"] = descricao
            if (
                st.session_state.df_notas.at[i, "CFOP ENTRADA"] != novo_cfop
                or
                st.session_state.df_notas.at[i, "DESCRIÇÃO"] != descricao
            ):
           
                st.rerun()

    # =========================
    # EXPORTAÇÃO
    # =========================
    with tab2:
        
        output = gerar_excel_entradas(
            df,
            st.session_state.df_notas
        )

        st.download_button(
            "⬇️ Baixar Auditoria",
            output,
            file_name="Auditoria_Entradas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    return df