import pandas as pd
import xml.etree.ElementTree as ET

from modules.xml_utils import get_text, NS
from modules.difal import calcular_difal_base_dupla
from modules.canceladas import localizar_canceladas
from modules.aliquotas import (
    obter_aliquota_interestadual,
    obter_aliquota_interna,
    obter_fcp
)


def processar_xmls(
    arquivos,
    regras,
    regras_st,
    tabela_icms,
    tabela_fcp
):

    dados = []

    chaves_canceladas = localizar_canceladas(
        arquivos
    )

    for arq in arquivos:

        try:

            arq.seek(0)

            tree = ET.parse(arq)

            root = tree.getroot()

            if root.find(
                ".//nfe:infEvento",
                NS
            ) is not None:

                continue

            ide = root.find(
                ".//nfe:ide",
                NS
            )

            emit = root.find(
                ".//nfe:emit",
                NS
            )

            dest = root.find(
                ".//nfe:dest",
                NS
            )

            ender_emit = (
                emit.find(
                    "nfe:enderEmit",
                    NS
                )
                if emit is not None
                else None
            )

            ender_dest = (
                dest.find(
                    "nfe:enderDest",
                    NS
                )
                if dest is not None
                else None
            )

            uf_origem = get_text(
                ender_emit,
                "nfe:UF",
                NS
            )

            uf_destino = get_text(
                ender_dest,
                "nfe:UF",
                NS
            )

            cnpj = get_text(
                dest,
                "nfe:CNPJ",
                NS
            )

            cpf = get_text(
                dest,
                "nfe:CPF",
                NS
            )

            documento = cnpj if cnpj else cpf

            tipo_cliente = (
                "PJ"
                if cnpj
                else "PF"
            )

            ie_dest = ""

            if dest is not None:

                ie_tag = dest.find(
                    ".//nfe:IE",
                    NS
                )

                ie_dest = (
                    ie_tag.text
                    if ie_tag is not None
                    else ""
                )

            chave = ""

            inf_nfe = root.find(
                ".//nfe:infNFe",
                NS
            )

            if inf_nfe is not None:

                chave = (
                    inf_nfe.attrib
                    .get("Id", "")
                    .replace("NFe", "")
                )

            status = "AUTORIZADA"

            if chave in chaves_canceladas:

                status = "CANCELADA"

            itens = root.findall(
                ".//nfe:det",
                NS
            )

            for item in itens:

                prod = item.find(
                    "nfe:prod",
                    NS
                )

                imposto = item.find(
                    "nfe:imposto",
                    NS
                )

                icms = (
                    imposto.find(
                        ".//nfe:ICMS/*",
                        NS
                    )
                    if imposto is not None
                    else None
                )

                icms_ufdest = (
                    imposto.find(
                        ".//nfe:ICMSUFDest",
                        NS
                    )
                    if imposto is not None
                    else None
                )

                ncm = get_text(
                    prod,
                    "nfe:NCM",
                    NS
                )

                cfop_xml = get_text(
                    prod,
                    "nfe:CFOP",
                    NS
                )

                produto = get_text(
                    prod,
                    "nfe:xProd",
                    NS
                )

                valor_total = float(
                    get_text(
                        prod,
                        "nfe:vProd",
                        NS
                    ) or 0
                )

                difal_xml = float(
                    get_text(
                        icms_ufdest,
                        "nfe:vICMSUFDest",
                        NS
                    ) or 0
                )

                fcp_xml = float(
                    get_text(
                        icms_ufdest,
                        "nfe:vFCPUFDest",
                        NS
                    ) or 0
                )

                aliq_inter = obter_aliquota_interestadual(
                    tabela_icms,
                    uf_origem,
                    uf_destino
                )

                aliq_interna = obter_aliquota_interna(
                    tabela_icms,
                    uf_destino
                )

                fcp_calc = (
                    valor_total *
                    obter_fcp(
                        tabela_fcp,
                        uf_destino
                    )
                )

                difal_calc = calcular_difal_base_dupla(
                    valor_total,
                    aliq_inter,
                    aliq_interna
                )

                dados.append({

                    "NF": get_text(
                        ide,
                        "nfe:nNF",
                        NS
                    ),

                    "Serie": get_text(
                        ide,
                        "nfe:serie",
                        NS
                    ),

                    "Status": status,

                    "Chave": chave,

                    "CPF/CNPJ": documento,

                    "Produto": produto,

                    "NCM": ncm,

                    "CFOP": cfop_xml,

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Valor Produto Total": valor_total,

                    "DIFAL XML": difal_xml,

                    "DIFAL Calculado": difal_calc,

                    "FCP XML": fcp_xml,

                    "FCP Calculado": round(
                        fcp_calc,
                        2
                    )

                })

        except Exception:

            continue

    return pd.DataFrame(dados)