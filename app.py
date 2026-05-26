import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

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
# TITULO
# =========================
st.title("📄 Leitor Fiscal NF-e")

st.info(
    "⚠️ O sistema suporta XML e ZIP contendo XMLs."
)

# =========================
# NAMESPACE XML
# =========================
ns = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

# =========================
# CARREGA REGRAS
# =========================
@st.cache_data
def carregar_regras():

    regras = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config Fiscal"
    )

    regras_st = pd.read_excel(
        "conf_fiscais.xlsx",
        sheet_name="Config ST"
    )

    regras_dict = {}
    regras_st_dict = {}

    # =========================
    # REGRAS FISCAIS
    # =========================
    for _, row in regras.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_dict[chave] = row.to_dict()

    # =========================
    # REGRAS ST
    # =========================
    for _, row in regras_st.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_st_dict[chave] = row.to_dict()

    return regras_dict, regras_st_dict


regras_dict, regras_st_dict = carregar_regras()

# =========================
# FUNÇÃO SEGURA XML
# =========================
def txt(elemento, tag):

    if elemento is None:
        return ""

    achou = elemento.find(tag, ns)

    return achou.text if achou is not None else ""


# =========================
# BUSCA REGRA
# =========================
def buscar_regra(dicionario, ncm, origem, destino):

    chave = (
        str(ncm).replace(".0", "").strip(),
        str(origem).upper().strip(),
        str(destino).upper().strip()
    )

    return dicionario.get(chave)


# =========================
# UPLOAD
# =========================
arquivos = st.file_uploader(
    "Envie XML ou ZIP",
    type=["xml", "zip"],
    accept_multiple_files=True
)

# =========================
# LISTA XMLS
# =========================
xmls = []

if arquivos:

    for arq in arquivos:

        # XML
        if arq.name.lower().endswith(".xml"):

            xmls.append(arq)

        # ZIP
        elif arq.name.lower().endswith(".zip"):

            try:

                zip_file = zipfile.ZipFile(arq)

                for nome in zip_file.namelist():

                    if nome.lower().endswith(".xml"):

                        xml_bytes = zip_file.read(nome)

                        xmls.append(
                            io.BytesIO(xml_bytes)
                        )

            except Exception as e:

                st.error(
                    f"Erro ao abrir ZIP {arq.name}: {e}"
                )

# =========================
# PROCESSAMENTO
# =========================
dados = []

canceladas = set()

if xmls:

    total = len(xmls)

    st.success(
        f"📦 {total} XMLs encontrados"
    )

    barra = st.progress(0)

    # =========================
    # IDENTIFICA CANCELADAS
    # =========================
    for i, arq in enumerate(xmls):

        try:

            arq.seek(0)

            conteudo = arq.read()

            texto = conteudo.decode(
                "utf-8",
                errors="ignore"
            ).upper()

            if (
                "CANCELAMENTO" in texto
                and
                "110111" in texto
            ):

                root = ET.fromstring(conteudo)

                inf_evento = root.find(
                    ".//nfe:infEvento",
                    ns
                )

                chave = txt(
                    inf_evento,
                    "nfe:chNFe"
                )

                if chave != "":

                    canceladas.add(chave)

            barra.progress((i + 1) / total)

        except:
            pass

    # =========================
    # PROCESSA XML
    # =========================
    for i, arq in enumerate(xmls):

        try:

            arq.seek(0)

            conteudo = arq.read()

            texto = conteudo.decode(
                "utf-8",
                errors="ignore"
            ).upper()

            root = ET.fromstring(conteudo)

            # IGNORA EVENTOS
            if root.find('.//nfe:infEvento', ns) is not None:
                continue

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            emit_end = (
                emit.find('nfe:enderEmit', ns)
                if emit is not None
                else None
            )

            dest_end = (
                dest.find('nfe:enderDest', ns)
                if dest is not None
                else None
            )

            uf_origem = txt(
                emit_end,
                'nfe:UF'
            )

            uf_destino = txt(
                dest_end,
                'nfe:UF'
            )

            cnpj = txt(dest, 'nfe:CNPJ')
            cpf = txt(dest, 'nfe:CPF')

            tipo_cliente = (
                "PJ"
                if cnpj != ""
                else "PF"
            )

            inf_nfe = root.find(
                './/nfe:infNFe',
                ns
            )

            chave = ""

            if inf_nfe is not None:

                chave = (
                    inf_nfe.attrib.get("Id", "")
                    .replace("NFe", "")
                )

            status = "AUTORIZADA"

            if chave in canceladas:

                status = "CANCELADA"

            itens = root.findall(
                './/nfe:det',
                ns
            )

            for item in itens:

                prod = item.find(
                    'nfe:prod',
                    ns
                )

                imposto = item.find(
                    'nfe:imposto',
                    ns
                )

                icms = (
                    imposto.find(
                        './/nfe:ICMS/*',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                # =========================
                # DADOS XML
                # =========================
                ncm = txt(prod, 'nfe:NCM')

                cfop = txt(prod, 'nfe:CFOP')

                produto = txt(prod, 'nfe:xProd')

                codigo = txt(prod, 'nfe:cProd')

                quantidade = txt(prod, 'nfe:qCom')

                cst = (
                    txt(icms, 'nfe:CST')
                    or
                    txt(icms, 'nfe:CSOSN')
                )

                aliquota = txt(
                    icms,
                    'nfe:pICMS'
                )

                valor_icms = txt(
                    icms,
                    'nfe:vICMS'
                )

                # =========================
                # PIS
                # =========================
                pis_tag = (
                    imposto.find(
                        './/nfe:PIS/*',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                valor_pis = txt(
                    pis_tag,
                    'nfe:vPIS'
                )

                # =========================
                # COFINS
                # =========================
                cofins_tag = (
                    imposto.find(
                        './/nfe:COFINS/*',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                valor_cofins = txt(
                    cofins_tag,
                    'nfe:vCOFINS'
                )

                # =========================
                # DIFAL / FCP
                # =========================
                icmsufdest = (
                    imposto.find(
                        './/nfe:ICMSUFDest',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                valor_difal = txt(
                    icmsufdest,
                    'nfe:vICMSUFDest'
                )

                valor_fcp = txt(
                    icmsufdest,
                    'nfe:vFCPUFDest'
                )

                # =========================
                # REGRAS
                # =========================
                regra = buscar_regra(
                    regras_dict,
                    ncm,
                    uf_origem,
                    uf_destino
                )

                regra_st = buscar_regra(
                    regras_st_dict,
                    ncm,
                    uf_origem,
                    uf_destino
                )

                # =========================
                # DIVERGENCIAS
                # =========================
                divergencias = []

                # =========================
                # DIFAL
                # =========================
                difal_calculado = 0

                try:

                    base_difal = float(
                        txt(icmsufdest, 'nfe:vBCUFDest') or 0
                    )

                    aliq_inter = float(
                        txt(icmsufdest, 'nfe:pICMSInter') or 0
                    )

                    aliq_interna = float(
                        txt(icmsufdest, 'nfe:pICMSUFDest') or 0
                    )

                    diferenca_aliquota = (
                        aliq_interna - aliq_inter
                    )

                    perc_partilha = float(
                        txt(icmsufdest, 'nfe:pICMSInterPart') or 100
                    )

                    if diferenca_aliquota > 0:

                        difal_total = (
                            base_difal *
                            (diferenca_aliquota / 100)
                        )

                        difal_calculado = round(
                            difal_total *
                            (perc_partilha / 100),
                            2
                        )

                except:
                    pass

                # =========================
                # DIFAL XML
                # =========================
                try:

                    difal_xml = float(
                        valor_difal or 0
                    )

                except:

                    difal_xml = 0

                # =========================
                # VALIDACAO DIFAL
                # =========================
                if difal_calculado > 0:

    diferenca = abs(
        difal_xml - difal_calculado
    )

    # tolerancia arredondamento
    if diferenca > 1:

        divergencias.append(
            f"DIFAL XML ({difal_xml}) diferente do calculado ({difal_calculado})"
        )

                # =========================
                # VALOR PRODUTO
                # =========================
                valor_final = float(
                    txt(prod, 'nfe:vProd') or 0
                )

                # =========================
                # DADOS
                # =========================
                dados.append({

                    "Numero NF": txt(
                        ide,
                        'nfe:nNF'
                    ),

                    "Serie": txt(
                        ide,
                        'nfe:serie'
                    ),

                    "Emissao": txt(
                        ide,
                        'nfe:dhEmi'
                    ),

                    "Chave Acesso": f"'{chave}",

                    "Status": status,

                    "Destinatario": txt(
                        dest,
                        'nfe:xNome'
                    ),

                    "CPF/CNPJ": (
                        cnpj if cnpj != ""
                        else cpf
                    ),

                    "Tipo Cliente": tipo_cliente,

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Produto": produto,

                    "Codigo": codigo,

                    "Quantidade": quantidade,

                    "NCM": ncm,

                    "CFOP XML": cfop,

                    "CST XML": cst,

                    "Aliquota ICMS XML": aliquota,

                    "Valor ICMS": valor_icms,

                    "PIS": valor_pis,

                    "COFINS": valor_cofins,

                    "Valor DIFAL": valor_difal,

                    "DIFAL Calculado": difal_calculado,

                    "Valor FCP": valor_fcp,

                    "Validacao": (
                        "OK"
                        if len(divergencias) == 0
                        else "DIVERGENTE"
                    ),

                    "Divergencias": (
                        " | ".join(divergencias)
                    ),

                    "Valor Produto Total": round(
                        valor_final,
                        2
                    )

                })

            barra.progress((i + 1) / total)

        except Exception as e:

            st.error(
                f"Erro no arquivo: {e}"
            )

# =========================
# RESULTADO
# =========================
if dados:

    df = pd.DataFrame(dados)

    st.success(
        f"✅ {len(df)} registros processados"
    )

    csv = df.to_csv(
        index=False,
        sep=";"
    ).encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar CSV",
        csv,
        "relatorio_fiscal.csv",
        "text/csv"
    )

    st.dataframe(
        df.head(500)
    )

else:

    st.info(
        "Envie XMLs ou ZIPs para iniciar."
    )