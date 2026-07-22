import pandas as pd


def verificar_quebras(df):

    df_seq = df[
        df["Status"].isin(
            ["AUTORIZADA", "CANCELADA", "DENEGADA"]
        )
    ].copy()

    df_seq["NF"] = pd.to_numeric(
        df_seq["NF"],
        errors="coerce"
    )

    quebras = []

    for serie in df_seq["SERIE"].dropna().unique():

        notas = sorted(
            df_seq[
                df_seq["SERIE"] == serie
            ]["NF"]
            .dropna()
            .astype(int)
            .unique()
        )

        if len(notas) > 1:

            menor = min(notas)
            maior = max(notas)

            todas = set(
                range(menor, maior + 1)
            )

            existentes = set(notas)

            faltantes = sorted(
                list(todas - existentes)
            )

            quebras.append({

                "SERIE": serie,
                "Menor NF": menor,
                "Maior NF": maior,
                "Qtd Quebras": len(faltantes),

                "Notas Faltantes":(
                    ", ".join(map(str, faltantes[:100]))
                    if faltantes
                    else "Nenhuma"
                )
            })

    return pd.DataFrame(quebras)