import pandas as pd
import xml.etree.ElementTree as ET

from modules.xml_utils import get_text, NS


def identificar_status(root, chaves_canceladas, chave):

    # =========================
    # CANCELAMENTO
    # =========================
    if chave in chaves_canceladas:
        return "CANCELADA"

    # =========================
    # PROTOCOLO DA NF-e
    # =========================
    prot_nfe = root.find(
        ".//nfe:protNFe/nfe:infProt",
        NS
    )

    if prot_nfe is not None:

        c_stat = get_text(
            prot_nfe,
            "nfe:cStat",
            NS
        )

        if c_stat == "100":
            return "AUTORIZADA"

        if c_stat in ["101", "151"]:
            return "CANCELADA"

        if c_stat == "110":
            return "DENEGADA"

        return f"STATUS {c_stat}"

    return "SEM PROTOCOLO"


def processar_entradas(
    arquivos,
    regras,
    regras_st,
    cfops
):

    # =========================
    # PADRONIZA CFOPS
    # =========================
    cfops = cfops.copy()

    registros = []

    # =========================
    # BUSCAR CANCELAMENTOS
    # =========================
    chaves_canceladas = set()

    for arquivo in arquivos:

        try:

            arquivo.seek(0)

            tree = ET.parse(arquivo)
            root = tree.getroot()

            inf_evento = root.find(
                ".//nfe:infEvento",
                NS
            )

            if inf_evento is None:
                continue

            tp_evento = get_text(
                inf_evento,
                "nfe:tpEvento",
                NS
            )

            # 110111 = cancelamento
            if tp_evento != "110111":
                continue

            ret_evento = root.find(
                ".//nfe:retEvento/nfe:infEvento",
                NS
            )

            c_stat_evento = get_text(
                ret_evento,
                "nfe:cStat",
                NS
            )

            chave_evento = get_text(
                ret_evento,
                "nfe:chNFe",
                NS
            )

            if not chave_evento:

                chave_evento = get_text(
                    inf_evento,
                    "nfe:chNFe",
                    NS
                )

            # 135 = evento registrado e vinculado
            if (
                chave_evento
                and c_stat_evento == "135"
            ):

                chaves_canceladas.add(
                    chave_evento
                )

        except Exception:
            continue

    # =========================
    # PROCESSAR NF-e
    # =========================
    for arquivo in arquivos:

        try:

            arquivo.seek(0)

            tree = ET.parse(arquivo)
            root = tree.getroot()

            # =========================
            # NF-e
            # =========================
            inf_nfe = root.find(
                ".//nfe:infNFe",
                NS
            )

            if inf_nfe is None:
                continue

            # =========================
            # CHAVE
            # =========================
            chave = (
                inf_nfe.attrib
                .get("Id", "")
                .replace("NFe", "")
            )

            # =========================
            # STATUS
            # =========================
            status = identificar_status(
                root,
                chaves_canceladas,
                chave
            )

            # =========================
            # DADOS DA NOTA
            # =========================
            ide = inf_nfe.find(
                "nfe:ide",
                NS
            )

            emit = inf_nfe.find(
                "nfe:emit",
                NS
            )

            dest = inf_nfe.find(
                "nfe:dest",
                NS
            )

            total = inf_nfe.find(
                "nfe:total/nfe:ICMSTot",
                NS
            )

            valor_nf = float(
                get_text(
                    total,
                    "nfe:vNF",
                    NS
                ) or 0
            )

            nf = get_text(
                ide,
                "nfe:nNF",
                NS
            )

            serie = get_text(
                ide,
                "nfe:serie",
                NS
            )

            emissao = (
                get_text(
                    ide,
                    "nfe:dhEmi",
                    NS
                )
                or
                get_text(
                    ide,
                    "nfe:dEmi",
                    NS
                )
            )

            # =========================
            # EMITENTE
            # =========================
            emit_cnpj = get_text(
                emit,
                "nfe:CNPJ",
                NS
            )

            emit_ie = get_text(
                emit,
                "nfe:IE",
                NS
            )

            emit_nome = get_text(
                emit,
                "nfe:xNome",
                NS
            )

            emit_uf = get_text(
                emit,
                "nfe:enderEmit/nfe:UF",
                NS
            )

            # =========================
            # DESTINATÁRIO
            # =========================
            dest_cnpj = (
                get_text(
                    dest,
                    "nfe:CNPJ",
                    NS
                )
                or
                get_text(
                    dest,
                    "nfe:CPF",
                    NS
                )
            )

            dest_ie = get_text(
                dest,
                "nfe:IE",
                NS
            )

            dest_uf = get_text(
                dest,
                "nfe:enderDest/nfe:UF",
                NS
            )

            # =========================
            # ITENS
            # =========================
            for det in inf_nfe.findall(
                "nfe:det",
                NS
            ):

                prod = det.find(
                    "nfe:prod",
                    NS
                )

                imposto = det.find(
                    "nfe:imposto",
                    NS
                )

                # =========================
                # PRODUTO
                # =========================
                c_prod = get_text(
                    prod,
                    "nfe:cProd",
                    NS
                )

                x_prod = get_text(
                    prod,
                    "nfe:xProd",
                    NS
                )

                ncm = get_text(
                    prod,
                    "nfe:NCM",
                    NS
                )

                cfop = get_text(
                    prod,
                    "nfe:CFOP",
                    NS
                )

                valor_prod = float(
                    get_text(
                        prod,
                        "nfe:vProd",
                        NS
                    ) or 0
                )

                desconto = float(
                    get_text(
                        prod,
                        "nfe:vDesc",
                        NS
                    ) or 0
                )

                # =========================
                # ICMS
                # =========================
                cst_icms = ""
                base_icms = 0.0
                valor_icms = 0.0
                aliquota_icms = 0.0
                base_st = 0.0
                valor_st = 0.0

                if imposto is not None:

                    icms = imposto.find(
                        "nfe:ICMS",
                        NS
                    )

                    if (
                        icms is not None
                        and len(icms) > 0
                    ):

                        icms_tag = list(icms)[0]

                        cst_icms = (
                            get_text(
                                icms_tag,
                                "nfe:CST",
                                NS
                            )
                            or
                            get_text(
                                icms_tag,
                                "nfe:CSOSN",
                                NS
                            )
                        )

                        base_icms = float(
                            get_text(
                                icms_tag,
                                "nfe:vBC",
                                NS
                            ) or 0
                        )

                        valor_icms = float(
                            get_text(
                                icms_tag,
                                "nfe:vICMS",
                                NS
                            ) or 0
                        )

                        aliquota_icms = float(
                            get_text(
                                icms_tag,
                                "nfe:pICMS",
                                NS
                            ) or 0
                        )

                        base_st = float(
                            get_text(
                                icms_tag,
                                "nfe:vBCST",
                                NS
                            ) or 0
                        )

                        valor_st = float(
                            get_text(
                                icms_tag,
                                "nfe:vICMSST",
                                NS
                            ) or 0
                        )

                # =========================
                # DIFAL
                # =========================

                difal = 0.0

                if imposto is not None:

                    icms_ufdest = imposto.find(
                        ".//nfe:ICMSUFDest",
                        NS
                    )

                    if icms_ufdest is not None:

                        difal = float(
                            get_text(
                                icms_ufdest,
                                "nfe:vICMSUFDest",
                                NS
                            ) or 0
                        )

                # =========================
                # IBS / CBS
                # =========================
                ibs = 0.0
                cbs = 0.0

                if imposto is not None:

                    ibs = float(
                        get_text(
                            imposto,
                            ".//nfe:vIBS",
                            NS
                        ) or 0
                    )

                    cbs = float(
                        get_text(
                            imposto,
                            ".//nfe:vCBS",
                            NS
                        ) or 0
                    )

                # =========================
                # CFOP ESPERADO
                # =========================
                tipo_operacao = ""
                cfop_entrada = ""
                descricao = ""

                regra = cfops.loc[
                    cfops[
                        "CFOP SAÍDA"
                    ]
                    .astype(str)
                    .str.replace(
                        ".0",
                        "",
                        regex=False
                    )
                    .str.strip()
                    ==
                    str(cfop)
                    .replace(".0", "")
                    .strip()
                ]

                if not regra.empty:

                    tipo_operacao = (
                        regra.iloc[0][
                            "TIPO OPERAÇÃO"
                        ]
                    )

                    cfop_entrada = (
                        regra.iloc[0][
                            "CFOP ENTRADA"
                        ]
                    )

                    descricao = (
                        regra.iloc[0][
                            "DESCRIÇÃO"
                        ]
                    )

                # =========================
                # REGISTRO
                # =========================
                registros.append({

                    "Chave": chave,

                    "NF": nf,

                    "SERIE": serie,

                    "EMISSÃO": emissao,

                    "CNPJ EMITENTE": emit_cnpj,

                    "IE EMITENTE": emit_ie,

                    "EMITENTE": emit_nome,

                    "UF EMITENTE": emit_uf,

                    "CPF/CNPJ DESTINO": dest_cnpj,

                    "IE DESTINO": dest_ie,

                    "UF DESTINO": dest_uf,

                    "CÓDIGO DO PRODUTO": c_prod,

                    "PRODUTO": x_prod,

                    "NCM": ncm,

                    "CFOP NOTA": cfop,

                    "CFOP SAÍDA": cfop,

                    "VALOR DO PRODUTO": valor_prod,

                    "DESCONTO": desconto,

                    "VALOR NF": valor_nf,

                    "CST ICMS": cst_icms,

                    "BASE ICMS": base_icms,

                    "ALIQUOTA ICMS": aliquota_icms,

                    "ICMS": valor_icms,

                    "BASE ST": base_st,

                    "ICMS ST": valor_st,

                    "IBS": ibs,

                    "CBS": cbs,

                    "DIFAL": difal,

                    "Status": status,

                    "TIPO OPERAÇÃO": tipo_operacao,

                    "CFOP ENTRADA": cfop_entrada,

                    "DESCRIÇÃO": descricao,

                    "ANALISE": ""
                })

        except Exception as e:

            print(
                f"Erro ao processar arquivo: "
                f"{getattr(arquivo, 'name', 'arquivo')}"
            )

            import traceback
            traceback.print_exc()

            continue

    # =========================
    # DATAFRAME FINAL
    # =========================
    return pd.DataFrame(registros)