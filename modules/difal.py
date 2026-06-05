def calcular_difal_base_dupla(
    valor,
    aliq_inter,
    aliq_interna
):

    if aliq_inter is None:
        return 0

    if aliq_interna is None:
        return 0

    icms_origem = valor * aliq_inter

    base_dupla = (
        valor - icms_origem
    ) / (
        1 - aliq_interna
    )

    icms_destino = (
        base_dupla * aliq_interna
    )

    return round(
        icms_destino - icms_origem,
        2
    )