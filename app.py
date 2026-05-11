import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

# =========================
# CONFIG PAGINA
# =========================
st.set_page_config(layout="wide")

# =========================
# CSS
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 3rem;
    padding-right: 3rem;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)

# =========================
# LEITURA DAS REGRAS
# =========================
regras = pd.read_excel(
    "conf_fiscais.xlsx",
    sheet_name="Config Fiscal"
)

regras_st = pd.read_excel(
    "conf_fiscais.xlsx",
    sheet_name="Config ST"
)

# =========================
# FUNÇÃO SEGURA XML
# =========================
def get_text(element, tag, ns):

    if element is None:
        return ""

    found = element.find(tag, ns)

    return found.text if found is not None else ""


# =========================
# BUSCA REGRA FISCAL
# =========================
def buscar_regra(ncm, origem, destino):

    ncm = str(ncm).replace(".0", "").strip()

    filtro = regras[
        (regras["ncm"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip() == ncm)

        &

        (regras["origem"]
            .astype(str)
            .str.upper()
            .str.strip() == str(origem).upper().strip())

        &

        (regras["destino"]
            .astype(str)
            .str.upper()
            .str.strip() == str(destino).upper().strip())
    ]

    if not filtro.empty:
        return filtro.iloc[0]

    return None


# =========================
# BUSCA REGRA ST
# =========================
def buscar_regra_st(ncm, origem, destino):

    ncm = str(ncm).replace(".0", "").strip()

    filtro = regras_st[
        (regras_st["ncm"]
            .astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip() == ncm)

        &

        (regras_st["origem"]
            .astype(str)
            .str.upper()
            .str.strip() == str(origem).upper().strip())

        &

        (regras_st["destino"]
            .astype(str)
            .str.upper()
            .str.strip() == str(destino).upper().strip())
    ]

    if not filtro.empty:
        return filtro.iloc[0]

    return None


# =========================
# INTERFACE
# =========================
st.title("📄 Leitor Fiscal NF-e")

arquivos = st.file_uploader(
    "Envie XMLs da NF-e",
    type=["xml"],
    accept_multiple_files=True
)

dados = []

# =========================
# CHAVES CANCELADAS
# =========================
chaves_canceladas = set()

# =========================
# PROCESSAMENTO
# =========================
if arquivos:

    # =========================
    # PRIMEIRO LOOP
    # IDENTIFICA CANCELAMENTOS
    # =========================
    for arq in arquivos:

        try:

            arq.seek(0)

            tree = ET.parse(arq)
            root = tree.getroot()

            ns = {
                'nfe': 'http://www.portalfiscal.inf.br/nfe'
            }

            xml_str = ET.tostring(
                root,
                encoding='unicode'
            ).upper()

            # EVENTO CANCELAMENTO
            if (
                "CANCELAMENTO" in xml_str
                and
                "110111" in xml_str
            ):

                chave_evento = ""

                # tenta retEvento
                ret_evento = root.find(
                    './/nfe:retEvento/nfe:infEvento',
                    ns
                )

                if ret_evento is not None:

                    chave_evento = get_text(
                        ret_evento,
                        'nfe:chNFe',
                        ns
                    )

                # fallback infEvento
                if chave_evento == "":

                    inf_evento = root.find(
                        './/nfe:infEvento',
                        ns
                    )

                    chave_evento = get_text(
                        inf_evento,
                        'nfe:chNFe',
                        ns
                    )

                if chave_evento != "":

                    chaves_canceladas.add(
                        chave_evento
                    )

        except:
            pass

    # =========================
    # SEGUNDO LOOP
    # PROCESSA NFS
    # =========================
    for arq in arquivos:

        try:

            arq.seek(0)

            tree = ET.parse(arq)
            root = tree.getroot()

            ns = {
                'nfe': 'http://www.portalfiscal.inf.br/nfe'
            }

            # IGNORA XML EVENTO
            if root.find('.//nfe:infEvento', ns) is not None:
                continue

            ide = root.find('.//nfe:ide', ns)

            emit = root.find('.//nfe:emit', ns)

            dest = root.find('.//nfe:dest', ns)

            # =========================
            # CHAVE ACESSO
            # =========================
            inf_nfe = root.find(
                './/nfe:infNFe',
                ns
            )

            chave_acesso = ""

            if inf_nfe is not None:

                chave_acesso = (
                    inf_nfe.attrib.get("Id", "")
                    .replace("NFe", "")
                )

            # =========================
            # STATUS NF
            # =========================
            status = "AUTORIZADA"

            if chave_acesso in chaves_canceladas:

                status = "CANCELADA"

            xml_str = ET.tostring(
                root,
                encoding='unicode'
            ).upper()

            if "DENEGADO" in xml_str:

                status = "DENEGADA"

            elif "REJEICAO" in xml_str:

                status = "REJEITADA"

            ender_emit = (
                emit.find('nfe:enderEmit', ns)
                if emit is not None
                else None
            )

            ender_dest = (
                dest.find('nfe:enderDest', ns)
                if dest is not None
                else None
            )

            # =========================
            # CLIENTE PF/PJ
            # =========================
            cnpj = get_text(dest, 'nfe:CNPJ', ns)

            cpf = get_text(dest, 'nfe:CPF', ns)

            tipo_cliente = (
                "PJ"
                if cnpj != ""
                else "PF"
            )

            # =========================
            # UF ORIGEM / DESTINO
            # =========================
            uf_origem = get_text(
                ender_emit,
                'nfe:UF',
                ns
            )

            uf_destino = get_text(
                ender_dest,
                'nfe:UF',
                ns
            )

            # =========================
            # LOOP ITENS
            # =========================
            itens = root.findall('.//nfe:det', ns)

            for item in itens:

                prod = item.find('nfe:prod', ns)

                imposto = item.find('nfe:imposto', ns)

                # =========================
                # ICMS ITEM
                # =========================
                icms_tag = (
                    imposto.find('.//nfe:ICMS/*', ns)
                    if imposto is not None
                    else None
                )

                valor_icms_xml = get_text(
                    icms_tag,
                    'nfe:vICMS',
                    ns
                )

                # =========================
                # PIS ITEM
                # =========================
                pis_tag = (
                    imposto.find('.//nfe:PIS/*', ns)
                    if imposto is not None
                    else None
                )

                pis_xml = get_text(
                    pis_tag,
                    'nfe:vPIS',
                    ns
                )

                # =========================
                # COFINS ITEM
                # =========================
                cofins_tag = (
                    imposto.find('.//nfe:COFINS/*', ns)
                    if imposto is not None
                    else None
                )

                cofins_xml = get_text(
                    cofins_tag,
                    'nfe:vCOFINS',
                    ns
                )

                # =========================
                # ICMS
                # =========================
                icms = (
                    imposto.find('.//nfe:ICMS/*', ns)
                    if imposto is not None
                    else None
                )

                # =========================
                # DADOS XML
                # =========================
                ncm_xml = get_text(
                    prod,
                    'nfe:NCM',
                    ns
                )

                cfop_xml = get_text(
                    prod,
                    'nfe:CFOP',
                    ns
                )

                cst_xml = ""

                if icms is not None:

                    cst_xml = (
                        get_text(icms, 'nfe:CST', ns)
                        or
                        get_text(icms, 'nfe:CSOSN', ns)
                    )

                aliquota_xml = get_text(
                    icms,
                    'nfe:pICMS',
                    ns
                )

                # =========================
                # BUSCA REGRAS
                # =========================
                regra = buscar_regra(
                    ncm_xml,
                    uf_origem,
                    uf_destino
                )

                regra_st = buscar_regra_st(
                    ncm_xml,
                    uf_origem,
                    uf_destino
                )

                # =========================
                # DADOS REGRA
                # =========================
                if regra is not None:

                    cfop_regra = (
                        str(regra["cfop_pj"])
                        if tipo_cliente == "PJ"
                        else str(regra["cfop_pf"])
                    ).replace(".0", "")

                    cst_regra = (
                        str(regra["cst_icms_pj"])
                        if tipo_cliente == "PJ"
                        else str(regra["cst_icms_pf"])
                    ).replace(".0", "")

                    aliquota_regra = str(
                        regra["aliquota_icms"]
                    ).replace(".0", "")

                else:

                    cfop_regra = ""
                    cst_regra = ""
                    aliquota_regra = ""

                # =========================
                # VALIDACOES
                # =========================
                divergencias = []

                if regra is None:

                    divergencias.append(
                        "SEM REGRA FISCAL"
                    )

                else:

                    # VALIDA CFOP
                    if cfop_xml != cfop_regra:

                        divergencias.append(
                            f"CFOP XML ({cfop_xml}) diferente da regra"
                        )

                    # VALIDA CST
                    if cst_regra != "" and cst_xml != "":

                        try:

                            if int(cst_xml) != int(cst_regra):

                                divergencias.append(
                                    f"CST XML ({cst_xml}) diferente da regra ({cst_regra})"
                                )

                        except:

                            divergencias.append(
                                "Erro ao validar CST"
                            )

                    # VALIDA ICMS
                    if aliquota_xml != "" and aliquota_regra != "":

                        try:

                            if float(aliquota_xml) != float(aliquota_regra):

                                divergencias.append(
                                    f"ICMS XML ({aliquota_xml}) diferente da regra ({aliquota_regra})"
                                )

                        except:

                            divergencias.append(
                                "Erro ao validar aliquota ICMS"
                            )

                # =========================
                # VALIDA ST
                # =========================
                csts_st = [
                    "10",
                    "30",
                    "60",
                    "70"
                ]

                tem_st_xml = False

                try:

                    if int(cst_xml) in [int(x) for x in csts_st]:

                        tem_st_xml = True

                except:
                    pass

                tem_regra_st = regra_st is not None

                if tem_regra_st and not tem_st_xml:

                    divergencias.append(
                        "Produto deveria ter ST"
                    )

                if tem_st_xml and not tem_regra_st:

                    divergencias.append(
                        "Produto possui ST sem regra configurada"
                    )

                # =========================
                # DADOS
                # =========================
                dados.append({

                    "Numero NF": get_text(
                        ide,
                        'nfe:nNF',
                        ns
                    ),

                    "Serie": get_text(
                        ide,
                        'nfe:serie',
                        ns
                    ),

                    "Emissao": get_text(
                        ide,
                        'nfe:dhEmi',
                        ns
                    ),

                    "Chave Acesso": chave_acesso,

                    "Status": status,

                    "Destinatario": get_text(
                        dest,
                        'nfe:xNome',
                        ns
                    ),

                    "CPF/CNPJ": (
                        cnpj if cnpj != ""
                        else cpf
                    ),

                    "Tipo Cliente": tipo_cliente,

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Produto": get_text(
                        prod,
                        'nfe:xProd',
                        ns
                    ),

                    "Codigo": get_text(
                        prod,
                        'nfe:cProd',
                        ns
                    ),

                    "NCM": ncm_xml,

                    "CFOP XML": cfop_xml,

                    "Quantidade": get_text(
                        prod,
                        'nfe:qCom',
                        ns
                    ),
                  
                    "CST XML": cst_xml,

                    "Aliquota ICMS XML": aliquota_xml,

                    "Aliquota ICMS Regra": aliquota_regra,

                    "Valor ICMS": valor_icms_xml,

                    "PIS": pis_xml,

                    "COFINS": cofins_xml,

                    "Tem Regra ST": (
                        "SIM"
                        if regra_st is not None
                        else "NAO"
                    ),

                    "Validacao": (
                        "OK"
                        if len(divergencias) == 0
                        else "DIVERGENTE"
                    ),

                    "Divergencias": (
                        " | ".join(divergencias)
                    ),

                    "Valor Produto Total": get_text(
                        prod,
                        'nfe:vProd',
                        ns
                    )

                })

        except Exception as e:

            st.error(
                f"Erro no arquivo {arq.name}: {e}"
            )

# =========================
# DATAFRAME
# =========================
df = pd.DataFrame(dados)

if not df.empty:

    st.subheader("📊 Resultado Fiscal")

    st.dataframe(
        df,
        use_container_width=True
    )

    csv = df.to_csv(
        index=False,
        sep=';'
    ).encode('utf-8-sig')

    st.download_button(
        "⬇️ Baixar CSV",
        csv,
        "relatorio_fiscal.csv",
        "text/csv"
    )

else:

    st.info(
        "Envie XMLs para iniciar."
    )