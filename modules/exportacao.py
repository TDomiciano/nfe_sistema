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
            "CHAVE"
            

        ]

        df_exportar = df[
            [c for c in colunas_auditoria if c in df.columns]
        ]

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