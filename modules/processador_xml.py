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
        arquivos,
        NS
    )
    print("CHAVES CANCELADAS:", chaves_canceladas)

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

            emissao = get_text(
                ide,
                "nfe:dhEmi",
                NS
            )

            if emissao:
                emissao = emissao[:10]
            
            emit = root.find(
                ".//nfe:emit",
                NS
            )

            dest = root.find(
                ".//nfe:dest",
                NS
            )

            razao_social = get_text(
                dest,
                "nfe:xNome",
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

            uf_origem = ""
            uf_destino = ""

            if ender_emit is not None:
                uf_origem = get_text(ender_emit, "nfe:UF", NS) or ""

            if ender_dest is not None:
                uf_destino = get_text(ender_dest, "nfe:UF", NS) or ""

                municipio_destino = get_text(
                    ender_dest,
                    "nfe:xMun",
                    NS
                ) or ""
            
            if not uf_origem or not uf_destino:
                continue

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

            pj_com_ie = (
                cnpj
                and str(ie_dest).strip()
                and str(ie_dest).upper() != "ISENTO"
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
                
                print("CHAVE NF:", repr(chave))

            status = "AUTORIZADA"

            if chave in chaves_canceladas:

                status = "CANCELADA"

            print("STATUS:", status)
            print("CHAVE EXISTE:", chave in chaves_canceladas)

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

                cst_icms = ""
                
                for tag in [
                    "nfe:CST",
                    "nfe:CSOSN"
                ]:
                    valor = get_text(
                        icms,
                        tag,
                        NS
                    )

                    if valor:
                        cst_icms = valor
                        break

                icms_ufdest = (
                    imposto.find(
                        ".//nfe:ICMSUFDest",
                        NS
                    )
                    if imposto is not None
                    else None
                )

                aliquota_icms = float(
                    get_text(
                        icms,
                        "nfe:pICMS",
                        NS
                    ) or 0
                )
                
                base_icms = float(
                    get_text(
                        icms,
                        "nfe:vBC",
                        NS
                    ) or 0
                )
                
                valor_icms = float(
                    get_text(
                        icms,
                        "nfe:vICMS",
                        NS
                    ) or 0
                )

                pis = item.find(
                    ".//nfe:PIS/*",
                    NS
                )
                
                valor_pis = float(
                    get_text(
                        pis,
                        "nfe:vPIS",
                        NS
                    ) or 0
                )
                
                cst_pis = get_text(
                    pis,
                    "nfe:CST",
                    NS
                )
                
                cofins = item.find(
                    ".//nfe:COFINS/*",
                    NS
                )
                
                valor_cofins = float(
                    get_text(
                        cofins,
                        "nfe:vCOFINS",
                        NS
                    ) or 0
                )
                
                cst_cofins = get_text(
                    cofins,
                    "nfe:CST",
                    NS
                )
                
                ibs = float(
                    get_text(
                        item,
                        ".//nfe:vIBS",
                        NS
                    ) or 0
                )

                cbs = float(
                    get_text(
                        item,
                        ".//nfe:vCBS",
                        NS
                    ) or 0
                )
                analise = ""

                ncm = get_text(
                    prod,
                    "nfe:NCM",
                    NS
                )

                codigo_produto = get_text(
                    prod,
                    "nfe:cProd",
                    NS
                )

                cfop_xml = get_text(
                    prod,
                    "nfe:CFOP",
                    NS
                )

                cfops_devolucao_venda = {
                    "1202",
                    "1411",
                    "2202",
                    "2411"

                }

                cfops_devolucao_compra = {
                    "5202",
                    "5411",
                    "6202",
                    "6411"
                }

                eh_devolucao_venda = cfop_xml in cfops_devolucao_venda
                eh_devolucao_compra = cfop_xml in cfops_devolucao_compra

                eh_devolucao = (
                    eh_devolucao_venda
                    or eh_devolucao_compra
                )

                cst_st = str(cst_icms).zfill(2) in {
                    "10",
                    "30",
                    "60",
                    "70"
                }

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

                quantidade = float(
                    get_text(
                        prod,
                        "nfe:qCom",
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
                
                vbc_fcp = float(
                    get_text(
                        icms_ufdest,
                        "nfe:vBCFCPUFDest",
                        NS
                    ) or 0
                )
                
                aliq_fcp = float(
                    get_text(
                        icms_ufdest,
                        "nfe:pFCPUFDest",
                        NS
                    ) or 0
                )
                
                fcp_calc = round(vbc_fcp * (aliq_fcp / 100), 2)

                aliq_inter = obter_aliquota_interestadual(
                    tabela_icms,
                    uf_origem,
                    uf_destino
                )
                
                aliq_interna = obter_aliquota_interna(
                    tabela_icms,
                    uf_destino
                )

                aliq_fcp_tabela = obter_fcp(
                    tabela_fcp,
                    uf_destino
                ) or 0

                difal_calc = 0
                
                if (
                    uf_origem != uf_destino
                    and not pj_com_ie
                    and not cst_st
                ):
                    difal_calc = calcular_difal_base_dupla(
                    base_icms if base_icms > 0 else valor_total,
                    aliq_inter,
                    aliq_interna,
                    aliq_fcp_tabela
                )
                
                # =========================
                # VALIDAÇÃO REGRA FISCAL
                # =========================
                
                analises = []

                cfops_devolucao = {
                    "1202",
                    "1411",
                    "2202",
                    "2411",
                    "5202",
                    "5411",
                    "6202",
                    "6411"
                }

                eh_devolucao = cfop_xml in cfops_devolucao

                cfops_entrada = {
                    "1101","1102","1113","1116",
                    "1201","1202",
                    "2101","2102","2113","2116",
                    "2201","2202"
                }

                eh_entrada = cfop_xml in cfops_entrada

                if eh_devolucao:
                    analises.append("Operação de devolução")

                regra = regras[
                    (regras["ncm"].astype(str) == str(ncm).strip())
                    &
                    (regras["origem"].astype(str).str.upper().str.strip()
                    == str(uf_origem).upper().strip())
                    &
                    (regras["destino"].astype(str).str.upper().str.strip()
                    == str(uf_destino).upper().strip())
                ]

                if regra.empty:
                    
                    analises.append(
                        f"Sem regra cadastrada para {ncm} {uf_origem}->{uf_destino}"
                    )
                    
                else:
                    
                    regra = regra.iloc[0]
                    
                    print("================================")
                    print("NF:", get_text(ide, "nfe:nNF", NS))
                    print("NCM:", ncm)
                    print("UF:", uf_origem, "->", uf_destino)
                    print("PJ_COM_IE:", pj_com_ie)
                    print("CST XML:", cst_icms)
                    print("CFOP XML:", cfop_xml)
                    print("CFOP PF:", regra["cfop_pf"])
                    print("CST PF:", regra["cst_icms_pf"])
                    print("CFOP PJ:", regra["cfop_pj"])
                    print("CST PJ:", regra["cst_icms_pj"])
                    print("================================")

                    cfop_esperado = (
                        str(regra["cfop_pj"])
                        if pj_com_ie
                        else str(regra["cfop_pf"])
                    )
                    
                    if (not eh_devolucao) and cfop_xml != cfop_esperado:
                        
                        analises.append(
                            f"CFOP esperado {cfop_esperado}"
                        )
                        
                    cst_esperado = (
                        str(regra["cst_icms_pj"])
                        if pj_com_ie
                        else str(regra["cst_icms_pf"])
                    )
                    
                    if str(cst_icms).zfill(2) != str(cst_esperado).zfill(2):
                        
                        analises.append(
                            f"CST ICMS esperado {cst_esperado}"
                        )
                    
                    cst_pis_ok = str(cst_pis).zfill(2)
                    cst_cofins_ok = str(cst_cofins).zfill(2)

                    if eh_devolucao_venda:

                        if cst_pis_ok != "98":
                            analises.append("CST PIS esperado 98")

                        if cst_cofins_ok != "98":
                            analises.append("CST COFINS esperado 98")

                    elif eh_devolucao_compra:

                        if cst_pis_ok != "49":
                            analises.append("CST PIS esperado 49")

                        if cst_cofins_ok != "49":
                            analises.append("CST COFINS esperado 49")

                    else:

                        if cst_pis_ok != str(regra["cst_pis"]).zfill(2):
                            analises.append("CST PIS divergente")

                        if cst_cofins_ok != str(regra["cst_cofins"]).zfill(2):
                            analises.append("CST COFINS divergente")

                    if (
                        pj_com_ie
                        and difal_xml > 0
                    ):

                        analises.append(
                            "DIFAL destacado para contribuinte"
                        )

                    if (
                        uf_origem != uf_destino
                        and not pj_com_ie
                        and difal_xml == 0
                    ):

                        analises.append(
                            "DIFAL não destacado"
                        )
                    
                    if (
                        uf_origem != uf_destino
                        and not pj_com_ie
                        and not cst_st
                        and abs(difal_xml - difal_calc) > 0.01
                    ):
                        analises.append(
                            f"DIFAL divergente (XML {difal_xml:.2f} x Calc {difal_calc:.2f})"
                        )

                    if abs(fcp_xml - fcp_calc) > 0.01:
                        analises.append(
                            f"FCP divergente (XML {fcp_xml:.2f} x Calc {fcp_calc:.2f})"
                        )
                    
                    if quantidade <= 0:
                        analises.append(
                            "Quantidade zerada"
                        )

                    if valor_total <= 0:
                        analises.append(
                            "Valor do produto zerado"
                        )

                # Resultado final
                if analises:
                    
                    analise = " | ".join(
                        analises
                    )
                
                else:
                                                           
                    analise = "OK"

                dados.append({

                    "NF": get_text(
                        ide,
                        "nfe:nNF",
                        NS
                    ),

                    "Status": status,

                    "SERIE": get_text(
                        ide,
                        "nfe:serie",
                        NS
                    ),

                    "CPF/CNPJ": documento,

                    "RAZÃO SOCIAL": razao_social,

                    "IE DESTINO": ie_dest,

                    "EMISSÃO": emissao,

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "MUNICÍPIO DESTINO": municipio_destino,

                    "CÓDIGO DO PRODUTO": codigo_produto,

                    "PRODUTO": produto,

                    "VALOR DO PRODUTO": valor_total,

                    "CFOP": cfop_xml,

                    "NCM": ncm,

                    "CST ICMS": cst_icms,

                    "ALIQUOTA ICMS": aliquota_icms,

                    "BASE ICMS": base_icms,

                    "ICMS": valor_icms,

                    "DIFAL XML": difal_xml,

                    "DIFAL CALCULADO": difal_calc,

                    "FCP XML": fcp_xml,

                    "PIS": valor_pis,

                    "CST PIS": cst_pis,

                    "COFINS": valor_cofins,

                    "CST COFINS": cst_cofins,
                    
                    "IBS": ibs,

                    "CBS": cbs,

                    "ANALISE": analise,

                    "Chave": chave,
                    
                    "FCP Calculado": round(
                        fcp_calc,
                        2
                    )

                })

        except Exception as e:

            print(f"ERRO NO XML: {e}")

            raise

    return pd.DataFrame(dados)