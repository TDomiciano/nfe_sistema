import pandas as pd
import xml.etree.ElementTree as ET

from modules.xml_utils import get_text, NS

def processar_entradas(
    arquivos,
    regras,
    regras_st,
    cfops
):

    # Força a padronização exata das colunas da tabela de CFOPs enviada
    cfops.columns = ["CFOP SAÍDA", "CFOP ENTRADA", "TIPO OPERAÇÃO", "DESCRIÇÃO"]

    registros = []

    for arquivo in arquivos:
        try:

            tree = ET.parse(arquivo)
            root = tree.getroot()

            inf_nfe = root.find('.//nfe:infNFe', NS)

            if inf_nfe is None:
                continue

            ide = inf_nfe.find('nfe:ide', NS)
            emit = inf_nfe.find('nfe:emit', NS)
            dest = inf_nfe.find('nfe:dest', NS)
            total = inf_nfe.find('nfe:total/nfe:ICMSTot', NS)

            valor_nf = float(
                get_text(
                    total,
                    'nfe:vNF',
                    NS
                ) or 0
            )

            chave = inf_nfe.attrib.get('Id', '').replace('NFe', '')

            nf = get_text(ide, 'nfe:nNF', NS)
            serie = get_text(ide, 'nfe:serie', NS)
            emissao = (
                get_text(ide, 'nfe:dhEmi', NS)
                or get_text(ide, 'nfe:dEmi', NS)
            )

            emit_cnpj = get_text(emit, 'nfe:CNPJ', NS)
            
            emit_ie = get_text(
                emit,
                'nfe:IE',
                NS
            )

            emit_nome = get_text(
                emit,
                'nfe:xNome',
                NS
            )
            
            emit_uf = get_text(
                emit,
                'nfe:enderEmit/nfe:UF',
                NS
            )

            dest_cnpj = (
                get_text(dest, 'nfe:CNPJ', NS)
                or get_text(dest, 'nfe:CPF', NS)
            )

            dest_ie = get_text(
                dest,
                'nfe:IE',
                NS
            )

            dest_uf = get_text(
                dest,
                'nfe:enderDest/nfe:UF',
                NS
            )

            for det in inf_nfe.findall('nfe:det', NS):

                prod = det.find('nfe:prod', NS)
                imposto = det.find('nfe:imposto', NS)

                c_prod = get_text(prod, 'nfe:cProd', NS)
                x_prod = get_text(prod, 'nfe:xProd', NS)
                ncm = get_text(prod, 'nfe:NCM', NS)
                cfop = get_text(prod, 'nfe:CFOP', NS)
                
                valor_prod = float(
                    get_text(prod, 'nfe:vProd', NS) or 0
                )

                desconto = float(
                    get_text(prod, 'nfe:vDesc', NS) or 0
                )

                #ICMS
                icms = imposto.find('nfe:ICMS', NS)

                cst_icms = ''
                base_icms = 0.0
                valor_icms = 0.0
                aliquota_icms = 0.0

                base_st = 0.0
                valor_st = 0.0

                if icms is not None and len(icms):

                    icms_tag = list(icms)[0]

                    cst_icms = (
                        get_text(icms_tag, 'nfe:CST', NS)
                        or get_text(icms_tag, 'nfe:CSOSN', NS)
                    )

                    base_icms = float(
                        get_text(icms_tag, 'nfe:vBC', NS) or 0
                    )

                    valor_icms = float(
                        get_text(icms_tag, 'nfe:vICMS', NS) or 0
                    )

                    aliquota_icms = float(
                        get_text(icms_tag, 'nfe:pICMS', NS) or 0
                    )

                    base_st = float(
                        get_text(icms_tag, "nfe:vBCST", NS) or 0
                    )

                    valor_st = float(
                        get_text(icms_tag, "nfe:vICMSST", NS) or 0
                    )
                
                # IBS / CBS
                ibs = float(
                    get_text(imposto, './/nfe:vIBS', NS) or 0
                )

                cbs = float(
                    get_text(imposto, './/nfe:vCBS', NS) or 0
                )

                tipo_operacao = ""
                cfop_entrada = ""

                # Filtra a regra comparando o CFOP do XML com o "CFOP SAÍDA" padronizado
                regra = cfops.loc[
                    cfops["CFOP SAÍDA"].astype(str).str.strip() == str(cfop).strip()
                ]

                if not regra.empty:
                    tipo_operacao = regra.iloc[0]["TIPO OPERAÇÃO"]
                    cfop_entrada = regra.iloc[0]["CFOP ENTRADA"]
                    descricao = regra.iloc[0]["DESCRIÇÃO"]

                registros.append({

                    'Chave': chave,
                    'NF': nf,
                    'SERIE': serie,
                    'EMISSÃO': emissao,

                    'CNPJ EMITENTE': emit_cnpj,
                    'IE EMITENTE': emit_ie,
                    'EMITENTE': emit_nome,
                    'UF EMITENTE': emit_uf,

                    'CPF/CNPJ DESTINO': dest_cnpj,
                    'IE DESTINO': dest_ie,
                    'UF DESTINO': dest_uf,

                    'CÓDIGO DO PRODUTO': c_prod,
                    'PRODUTO': x_prod,
                    'NCM': ncm,
                    
                    # CORREÇÃO CRUCIAL: Modificado de 'CFOP SAÍDA' para 'CFOP NOTA'
                    # para alinhar com a auditoria e com a interface visual.
                    'CFOP NOTA': cfop,
                    'CFOP SAÍDA': cfop,

                    'VALOR DO PRODUTO': valor_prod,
                    'DESCONTO': desconto,
                    'VALOR NF': valor_nf,

                    'CST ICMS': cst_icms,
                    'BASE ICMS': base_icms,
                    'ALIQUOTA ICMS': aliquota_icms,
                    'ICMS': valor_icms,

                    'BASE ST': base_st,
                    'ICMS ST': valor_st,

                    'IBS': ibs,
                    'CBS': cbs,

                    'Status': 'AUTORIZADA',

                    'TIPO OPERAÇÃO': tipo_operacao,
                    'CFOP ENTRADA': cfop_entrada,
                    'DESCRIÇÃO': descricao,

                    'ANALISE': ''
                })
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise            
            
    df_final = pd.DataFrame(registros)
    return df_final
