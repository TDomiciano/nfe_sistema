import io
import pandas as pd


def gerar_excel_entradas(df, df_notas):

    output = io.BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        # Resumo
        df_notas.to_excel(
            writer,
            sheet_name="Resumo",
            index=False
        )

        # Auditoria completa
        df.to_excel(
            writer,
            sheet_name="Auditoria Completa",
            index=False
        )

    output.seek(0)

    return output