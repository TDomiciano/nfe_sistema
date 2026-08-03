import pandas as pd

def auditar_entradas(df, cfops):

    df = df.copy()

    for idx, linha in df.iterrows():

        observacoes = []

        analise_existente = str(
            linha.get("ANALISE", "")
        ).strip()

        if analise_existente:
            observacoes.append(analise_existente)

        if not linha["CFOP ENTRADA"]:

            observacoes.append(
                f"CFOP {linha['CFOP SAÍDA']} não configurado."
            )

        else:

            observacoes.append(
                f"CFOP Entrada: {linha['CFOP ENTRADA']} | Tipo: {linha['TIPO OPERAÇÃO']}"
            )

        df.at[idx, "ANALISE"] = " | ".join(observacoes)

    return df