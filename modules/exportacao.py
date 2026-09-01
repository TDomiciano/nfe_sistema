import io
import pandas as pd
from openpyxl.styles import Font

from modules.supabase_db import buscar_vendas_historico_lote

def gerar_excel(
    df,
    df_quebras,
    df_canceladas
):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        # =========================
        # AUDITORIA FISCAL
        # =========================
        if "Status" in df.columns:
            df = df[
                df["Status"]
                .astype(str)
                .str.upper()
                .eq("AUTORIZADA")
            ].copy()      

        colunas_auditoria = [

            "NF",
            "SERIE",
            "CPF/CNPJ",
            "IE DESTINO",
            "EMISSÃO",
            "UF Origem",
            "UF Destino",
            "CÓDIGO DO PRODUTO",
            "PRODUTO",
            "VALOR DO PRODUTO",
            "DESCONTO",
            "CFOP",
            "NCM",
            "CST ICMS",
            "ALIQUOTA ICMS",
            "BASE ICMS",
            "ICMS",
            "DIFAL XML",
            "DIFAL CALCULADO",
            "PIS",
            "CST PIS",
            "COFINS",
            "CST COFINS",
            "FCP XML",
            "FCP Calculado",
            "IBS",
            "CBS",
            "ANALISE",
            "Chave"
            

        ]

        df_exportar = df.copy()

        for col in colunas_auditoria:
            if col not in df_exportar.columns:
                df_exportar[col] = None
        df_exportar = df_exportar[colunas_auditoria]

        cfops_excluir = (
            "1202", "1411", "2202", "2411"
        )

        df_exportar = df_exportar[
            ~df_exportar["CFOP"]
                .astype(str)
                .isin(cfops_excluir)
        ]

        df_exportar["ANÁLISE BASE ICMS"] = ""

        for idx, linha in df_exportar.iterrows():

            observacoes = []

            analise_existente = str(linha["ANALISE"] or "").strip()

            if analise_existente:
                observacoes.append(analise_existente)

            valor = float(linha["VALOR DO PRODUTO"] or 0)
            desconto = float(linha["DESCONTO"] or 0)
            base = float(linha["BASE ICMS"] or 0)
            aliquota = float(linha["ALIQUOTA ICMS"] or 0)
            icms = float(linha["ICMS"] or 0)

            base_esperada = round(valor - desconto, 2)

            if abs(base - base_esperada) > 0.05:
                observacoes.append(
                    f"Base divergente (Esperado: R$ {base_esperada:.2f} | XML: R$ {base:.2f})"
                )

            if str(linha["CST ICMS"]) == "00" and base > 0 and aliquota > 0:

                icms_esperado = round(
                    base * (aliquota / 100),
                    2
                )

                if abs(icms - icms_esperado) > 0.05:
                    observacoes.append(
                        f"ICMS divergente (Esperado: R$ {icms_esperado:.2f} | XML: R$ {icms:.2f})"
                    )

            fcp_xml = float(linha["FCP XML"] or 0)
            fcp_calc = float(linha["FCP Calculado"] or 0)

            if abs(fcp_xml - fcp_calc) > 0.05:
                observacoes.append(
                    f"FCP divergente (Calculado: R$ {fcp_calc:.2f} | XML: R$ {fcp_xml:.2f})"
                )

            df_exportar.at[idx, "ANALISE"] = " | ".join(observacoes)

        df_exportar.to_excel(
            writer,
            index=False,
            sheet_name="Auditoria Fiscal"
        )

        # =========================
        # QUEBRAS
        # =========================
        if not df_quebras.empty:

            df_quebras.to_excel(
                writer,
                index=False,
                sheet_name="Quebra Sequencia"
            )

        # =========================
        # CANCELADAS
        # =========================
        if not df_canceladas.empty:

            df_canceladas.to_excel(
                writer,
                index=False,
                sheet_name="NF Canceladas"
            )

        # =========================
        # DIFAL POR NOTA
        # =========================
        if not df.empty:

            df_difal_base = df[
                (
                    df["CFOP"]
                    .astype(str)
                    .str.startswith(("6", "7"))
                )
                &
                (
                    df["UF Origem"] != df["UF Destino"]
                )                 
                &
                (
                    df["IE DESTINO"]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .eq("")
                )
                
            ].copy()

            df_difal = (
                df_difal_base.groupby(
                    "Chave",
                    as_index=False
                )
                .agg({
                    "NF": "first",
                    "SERIE": "first",
                    "EMISSÃO": "first",
                    "CPF/CNPJ": "first",
                    "RAZÃO SOCIAL": "first",
                    "UF Destino": "first",
                    "MUNICÍPIO DESTINO": "first",
                    "DIFAL XML": "sum",
                    "DIFAL CALCULADO": "sum",
                    "FCP XML": "sum",
                    "FCP Calculado": "sum"
                })
            )

            df_difal["DIFAL DIFERENÇA"] = (
                df_difal["DIFAL XML"]
                - df_difal["DIFAL CALCULADO"]
            ).round(2)

            df_difal = df_difal[
                [
                    "Chave",
                    "NF",
                    "SERIE",
                    "EMISSÃO",
                    "CPF/CNPJ",
                    "RAZÃO SOCIAL",
                    "UF Destino",
                    "MUNICÍPIO DESTINO",
                    "DIFAL XML",
                    "DIFAL CALCULADO",
                    "DIFAL DIFERENÇA",
                    "FCP XML",
                    "FCP Calculado"
                ]
            ]

            df_difal.to_excel(
                writer,
                index=False,
                sheet_name="DIFAL"
            )

        # =========================
        # DEVOLUÇÕES
        # =========================
        cfops_devolucao = (
            "1201", "1202",
            "1410", "1411",
            "2201", "2202",
            "2410", "2411"
        )

        df_dev_base = df[
            df["CFOP"]
            .astype(str)
            .isin(cfops_devolucao)
        ].copy()

        if not df_dev_base.empty:

            df_dev = (
                df_dev_base.groupby(
                    "Chave",
                    as_index=False
                )
                .agg({
                    "NF": "first",
                    "SERIE": "first",
                    "EMISSÃO": "first",
                    "CPF/CNPJ": "first",
                    "RAZÃO SOCIAL": "first",
                    "UF Origem": "first",
                    "UF Destino": "first",
                    "CHAVE REFERENCIADA": "first",
                    "VALOR DO PRODUTO": "sum",
                    "ICMS": "sum",
                    "DIFAL XML": "sum",
                    "IBS": "sum",
                    "CBS": "sum"
                })
            )

            df_dev["OBSERVAÇÃO"] = ""

            vendas = (
                df.groupby("Chave", as_index=False)
                  .agg({
                      "NF": "first",
                      "CPF/CNPJ": "first",
                      "RAZÃO SOCIAL": "first",
                      "UF Destino": "first",
                      "VALOR DO PRODUTO": "sum",
                      "ICMS": "sum",
                      "DIFAL XML": "sum",
                      "IBS": "sum",
                      "CBS": "sum"
                })
                .set_index("Chave")
            )

            # ==========================================
            # BUSCA VENDAS HISTÓRICAS EM LOTE
            # ==========================================

            chaves_historico = []

            for chave_ref in df_dev["CHAVE REFERENCIADA"]:

                if pd.isna(chave_ref):
                    continue

                chave_ref = str(chave_ref).strip()

                if not chave_ref:
                    continue

                # Só consulta o banco se a venda
                # não estiver nos XMLs carregados
                if chave_ref not in vendas.index:
                    chaves_historico.append(chave_ref)

            # Remove chaves repetidas
            chaves_historico = list(set(chaves_historico))

            historico_por_chave = {}

            if chaves_historico:

                historico_lote = buscar_vendas_historico_lote(
                    chaves_historico
                )

                if historico_lote:

                    historico_df_lote = pd.DataFrame(
                        historico_lote
                    )

                    for chave, grupo in historico_df_lote.groupby(
                        "chave"
                    ):

                        historico_por_chave[
                            str(chave).strip()
                        ] = grupo.copy()

            # ==========================================
            # ANALISA CADA DEVOLUÇÃO
            # ==========================================

            for idx, linha in df_dev.iterrows():

                observacoes = []

                chave_ref = linha["CHAVE REFERENCIADA"]

                venda = None

                # ======================================
                # SEM CHAVE REFERENCIADA
                # ======================================

                if (
                    pd.isna(chave_ref)
                    or str(chave_ref).strip() == ""
                ):

                    observacoes.append(
                        "NF sem chave referenciada"
                    )

                else:

                    chave_ref = str(chave_ref).strip()

                    # ==================================
                    # VENDA ESTÁ NOS XMLs CARREGADOS
                    # ==================================

                    if chave_ref in vendas.index:

                        venda = vendas.loc[chave_ref]

                    # ==================================
                    # PROCURA NO HISTÓRICO DO SUPABASE
                    # ==================================

                    else:

                        historico_df = historico_por_chave.get(
                            chave_ref
                        )

                        if (
                            historico_df is not None
                            and not historico_df.empty
                        ):

                            venda = pd.Series({

                                "NF":
                                    historico_df["nf"].iloc[0],

                                "CPF/CNPJ":
                                    historico_df[
                                        "cpf_cnpj"
                                    ].iloc[0],

                                "RAZÃO SOCIAL":
                                    historico_df[
                                        "razao_social"
                                    ].iloc[0],

                                "UF Destino":
                                    historico_df[
                                        "uf_destino"
                                    ].iloc[0],

                                "VALOR DO PRODUTO":
                                    historico_df[
                                        "valor_produto"
                                    ]
                                    .fillna(0)
                                    .astype(float)
                                    .sum(),

                                "ICMS":
                                    historico_df[
                                        "icms"
                                    ]
                                    .fillna(0)
                                    .astype(float)
                                    .sum(),

                                "DIFAL XML":
                                    historico_df[
                                        "difal"
                                    ]
                                    .fillna(0)
                                    .astype(float)
                                    .sum(),

                                "IBS":
                                    historico_df[
                                        "ibs"
                                    ]
                                    .fillna(0)
                                    .astype(float)
                                    .sum(),

                                "CBS":
                                    historico_df[
                                        "cbs"
                                    ]
                                    .fillna(0)
                                    .astype(float)
                                    .sum()
                            })

                # ======================================
                # VENDA NÃO LOCALIZADA
                # ======================================

                if venda is None:

                    if not observacoes:
                        observacoes.append(
                            "Venda original não encontrada"
                        )

                else:

                    # ==================================
                    # CLIENTE
                    # ==================================

                    if (
                        str(venda["CPF/CNPJ"]).strip()
                        != str(linha["CPF/CNPJ"]).strip()
                    ):
                        observacoes.append(
                            "Cliente diferente da venda original"
                        )

                    # ==================================
                    # UF
                    # ==================================

                    if (
                        str(venda["UF Destino"]).strip()
                        != str(linha["UF Destino"]).strip()
                    ):
                        observacoes.append(
                            "UF diferente da venda original"
                        )

                    # ==================================
                    # VALOR
                    # ==================================

                    valor_venda = float(
                        venda["VALOR DO PRODUTO"] or 0
                    )

                    valor_devolucao = float(
                        linha["VALOR DO PRODUTO"] or 0
                    )

                    if valor_devolucao > valor_venda + 0.05:

                        observacoes.append(
                            f"Valor devolvido maior que a venda "
                            f"(Venda: R$ {valor_venda:.2f} | "
                            f"Devolução: R$ {valor_devolucao:.2f})"
                        )

                    elif valor_devolucao < valor_venda - 0.05:

                        observacoes.append(
                            f"Devolução parcial "
                            f"(Venda: R$ {valor_venda:.2f} | "
                            f"Devolução: R$ {valor_devolucao:.2f})"
                        )

                    # ==================================
                    # ICMS
                    # ==================================

                    icms_venda = float(
                        venda["ICMS"] or 0
                    )

                    icms_devolucao = float(
                        linha["ICMS"] or 0
                    )

                    if abs(
                        icms_devolucao - icms_venda
                    ) > 0.05:

                        observacoes.append(
                            f"ICMS divergente "
                            f"(Venda: R$ {icms_venda:.2f} | "
                            f"Devolução: R$ {icms_devolucao:.2f})"
                        )

                    # ==================================
                    # DIFAL
                    # ==================================

                    difal_venda = float(
                        venda["DIFAL XML"] or 0
                    )

                    difal_devolucao = float(
                        linha["DIFAL XML"] or 0
                    )

                    if difal_venda > 0:

                        if abs(
                            difal_devolucao - difal_venda
                        ) <= 0.05:

                            observacoes.append(
                                "DIFAL OK"
                            )

                        else:

                            observacoes.append(
                                f"DIFAL divergente "
                                f"(Venda: R$ {difal_venda:.2f} | "
                                f"Devolução: R$ {difal_devolucao:.2f})"
                            )

                    # ==================================
                    # IBS
                    # ==================================

                    ibs_venda = float(
                        venda["IBS"] or 0
                    )

                    ibs_devolucao = float(
                        linha["IBS"] or 0
                    )

                    if abs(
                        ibs_devolucao - ibs_venda
                    ) > 0.05:

                        observacoes.append(
                            f"IBS divergente "
                            f"(Venda: R$ {ibs_venda:.2f} | "
                            f"Devolução: R$ {ibs_devolucao:.2f})"
                        )

                    # ==================================
                    # CBS
                    # ==================================

                    cbs_venda = float(
                        venda["CBS"] or 0
                    )

                    cbs_devolucao = float(
                        linha["CBS"] or 0
                    )

                    if abs(
                        cbs_devolucao - cbs_venda
                    ) > 0.05:

                        observacoes.append(
                            f"CBS divergente "
                            f"(Venda: R$ {cbs_venda:.2f} | "
                            f"Devolução: R$ {cbs_devolucao:.2f})"
                        )

                    # ==================================
                    # TUDO OK
                    # ==================================

                    if not observacoes:

                        observacoes.append(
                            f"Devolução OK - Venda localizada "
                            f"(NF {venda['NF']})"
                        )

                df_dev.at[
                    idx,
                    "OBSERVAÇÃO"
                ] = " | ".join(observacoes)
                    

            df_dev = df_dev[
                [
                    "Chave",
                    "NF",
                    "SERIE",
                    "EMISSÃO",
                    "CPF/CNPJ",
                    "RAZÃO SOCIAL",
                    "UF Origem",
                    "UF Destino",
                    "VALOR DO PRODUTO",
                    "ICMS",
                    "IBS",
                    "CBS",
                    "CHAVE REFERENCIADA",
                    "OBSERVAÇÃO"
                ]
            ]

            df_dev.to_excel(
                writer,
                index=False,
                sheet_name="DEVOLUÇÃO DE VENDA"

            )


        # =========================
        # FORMATAÇÃO
        # =========================
        workbook = writer.book

        for aba in workbook.worksheets:

            # Congela cabeçalho
            aba.freeze_panes = "A2"

            # Filtro
            aba.auto_filter.ref = aba.dimensions

            # Cabeçalho em negrito
            for cell in aba[1]:
                cell.font = Font(
                    bold=True
                )

            # Ajusta largura
            for coluna in aba.columns:

                tamanho = max(
                    len(str(cell.value))
                    if cell.value is not None
                    else 0
                    for cell in coluna
                )

                aba.column_dimensions[
                    coluna[0].column_letter
                ].width = min(
                    tamanho + 3,
                    50
                )

    output.seek(0)

    return output