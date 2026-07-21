import io
import pandas as pd
from openpyxl.styles import Font


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
                      "IBS": "sum",
                      "CBS": "sum"
                })
                .set_index("Chave")
            )

            for idx, linha in df_dev.iterrows():

                observacoes = []

                chave_ref = linha["CHAVE REFERENCIADA"]

                if pd.isna(chave_ref) or str(chave_ref).strip() == "":
                    observacoes.append("NF sem chave referenciada")
                
                elif chave_ref not in vendas.index:
                    observacoes.append("Venda original não encontrada")
                
                else:
                    venda = vendas.loc[chave_ref]
                    if venda["CPF/CNPJ"] != linha["CPF/CNPJ"]:
                        observacoes.append("Cliente diferente da venda original")
                    
                    if venda["UF Destino"] != linha["UF Destino"]:
                        observacoes.append("UF diferente da venda original")

                    if linha["VALOR DO PRODUTO"] > venda["VALOR DO PRODUTO"]:
                        observacoes.append(
                            f"Valor devolvido maior que a venda (Venda: R$ {venda['VALOR DO PRODUTO']:.2f} | Devolução: R$ {linha['VALOR DO PRODUTO']:.2f})")
                    
                    elif linha["VALOR DO PRODUTO"] < venda["VALOR DO PRODUTO"]:
                        observacoes.append(
                            f"Devolução parcial (Venda: R$ {venda['VALOR DO PRODUTO']:.2f} | Devolução: R$ {linha['VALOR DO PRODUTO']:.2f})")
                    if abs(linha["ICMS"] - venda["ICMS"]) > 0.05:
                        observacoes.append(
                            f"ICMS divergente (Venda: R$ {venda['ICMS']:.2f} | Devolução: R$ {linha['ICMS']:.2f})")
                    
                    if abs(linha["IBS"] - venda["IBS"]) > 0.05:
                        observacoes.append(
                            f"IBS divergente (Venda: R$ {venda['IBS']:.2f} | Devolução: R$ {linha['IBS']:.2f})")

                    if abs(linha["CBS"] - venda["CBS"]) > 0.05:
                        observacoes.append(
                            f"CBS divergente (Venda: R$ {venda['CBS']:.2f} | Devolução: R$ {linha['CBS']:.2f})")

                    if not observacoes:
                        observacoes.append(
                            f"Devolução OK - Venda localizada (NF {venda['NF']})")

                df_dev.at[idx, "OBSERVAÇÃO"] = " | ".join(observacoes)

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
                sheet_name="DEVOLUÇÕES"

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