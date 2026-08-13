import streamlit as st
import pandas as pd

from modules.exportacao_entradas import gerar_excel_entradas


def atualizar_regra_editor(cfops):

    estado_editor = st.session_state.get(
        "editor_entradas",
        {}
    )

    alteracoes = estado_editor.get(
        "edited_rows",
        {}
    )

    if not alteracoes:
        return

    df_notas = st.session_state.df_notas

    # =====================================================
    # MAPA DAS REGRAS
    # =====================================================

    regras_cfop = {}

    for _, regra in cfops.iterrows():

        cfop_saida = str(
            regra["CFOP SAÍDA"]
        ).strip()

        tipo_operacao = str(
            regra["TIPO OPERAÇÃO"]
        ).strip()

        regras_cfop[
            (cfop_saida, tipo_operacao)
        ] = {
            "CFOP ENTRADA": str(
                regra["CFOP ENTRADA"]
            ).strip(),

            "DESCRIÇÃO": str(
                regra["DESCRIÇÃO"]
            ).strip()
        }

    # =====================================================
    # PROCESSA SOMENTE AS LINHAS ALTERADAS
    # =====================================================

    for indice, alteracao in alteracoes.items():

        if "TIPO OPERAÇÃO" not in alteracao:
            continue

        # CFOP da nota continua sendo o original
        cfop_nota = str(
            df_notas.at[
                indice,
                "CFOP NOTA"
            ]
        ).strip()

        # Nova finalidade escolhida
        tipo_operacao = str(
            alteracao["TIPO OPERAÇÃO"]
        ).strip()

        # Procura a regra
        regra = regras_cfop.get(
            (
                cfop_nota,
                tipo_operacao
            )
        )

        if regra:

            df_notas.at[
                indice,
                "CFOP ENTRADA"
            ] = regra["CFOP ENTRADA"]

            df_notas.at[
                indice,
                "DESCRIÇÃO"
            ] = regra["DESCRIÇÃO"]

        else:

            df_notas.at[
                indice,
                "CFOP ENTRADA"
            ] = ""

            df_notas.at[
                indice,
                "DESCRIÇÃO"
            ] = ""

    st.session_state.df_notas = df_notas


def mostrar_tela_entradas(df, cfops):

    # =====================================================
    # CARDS
    # =====================================================

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

    # =====================================================
    # ABAS
    # =====================================================

    tab1, tab2 = st.tabs([
        "📊 Auditoria",
        "📥 Exportação"
    ])

    # =====================================================
    # ABA AUDITORIA
    # =====================================================

    with tab1:

        st.markdown("### 🔍 Filtros")

        col1, col2 = st.columns(2)

        # -------------------------------------------------
        # FILTRO FORNECEDOR
        # -------------------------------------------------

        with col1:

            fornecedor = st.multiselect(
                "Fornecedor",

                options=sorted(
                    df["EMITENTE"]
                    .dropna()
                    .unique()
                ),

                default=sorted(
                    df["EMITENTE"]
                    .dropna()
                    .unique()
                ),

                key="filtro_fornecedor_entradas"
            )

        # -------------------------------------------------
        # FILTRO CFOP
        # -------------------------------------------------

        with col2:

            cfop = st.multiselect(
                "CFOP Nota",

                options=sorted(
                    df["CFOP NOTA"]
                    .dropna()
                    .unique()
                ),

                default=sorted(
                    df["CFOP NOTA"]
                    .dropna()
                    .unique()
                ),

                key="filtro_cfop_entradas"
            )

        # =================================================
        # FILTRO
        # =================================================

        df_filtrado = df[
            (df["EMITENTE"].isin(fornecedor))
            &
            (df["CFOP NOTA"].isin(cfop))
        ]

        # =================================================
        # RESUMO POR NOTA
        # =================================================

        df_notas = (
            df_filtrado
            .groupby(
                "Chave",
                as_index=False
            )
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

        # =================================================
        # SESSION STATE
        # =================================================

        if "df_notas" not in st.session_state:

            st.session_state.df_notas = (
                df_notas
                .copy()
                .astype(object)
            )

        # =================================================
        # EDITOR RESUMIDO
        # =================================================

        st.data_editor(

            st.session_state.df_notas,

            key="editor_entradas",

            on_change=atualizar_regra_editor,

            args=(cfops,),

            use_container_width=True,

            hide_index=True,

            column_config={

                "TIPO OPERAÇÃO":
                    st.column_config.SelectboxColumn(

                        "Finalidade da Compra",

                        options=sorted(
                            cfops[
                                "TIPO OPERAÇÃO"
                            ]
                            .dropna()
                            .astype(str)
                            .str.strip()
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

    # =====================================================
    # ABA EXPORTAÇÃO
    # =====================================================

    with tab2:

        output = gerar_excel_entradas(
            df,
            st.session_state.df_notas
        )

        st.download_button(

            "⬇️ Baixar Auditoria",

            output,

            file_name="Auditoria_Entradas.xlsx",

            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            )
        )