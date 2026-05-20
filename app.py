import streamlit as st
import pandas as pd
from lxml import etree as ET
import zipfile
import io

# =========================
# CONFIG
# =========================
st.set_page_config(layout="wide")

st.title("📄 Leitor Fiscal NF-e")

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

    for _, row in regras.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_dict[chave] = row

    for _, row in regras_st.iterrows():

        chave = (
            str(row["ncm"]).replace(".0", "").strip(),
            str(row["origem"]).upper().strip(),
            str(row["destino"]).upper().strip()
        )

        regras_st_dict[chave] = row

    return regras_dict, regras_st_dict


regras_dict, regras_st_dict = carregar_regras()

# =========================
# FUNÇÕES
# =========================
ns = {
    "nfe": "http://www.portalfiscal.inf.br/nfe"
}

def txt(elemento, tag):

    if elemento is None:
        return ""

    achou = elemento.find(tag, ns)

    return achou.text if achou is not None else ""


def buscar_regra(dicionario, ncm, origem, destino):

    chave = (
        str(ncm).strip(),
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

dados = []

# =========================
# EXTRAI XMLS
# =========================
xmls = []

if arquivos:

    for arq in arquivos:

        # =========================
        # XML NORMAL
        # =========================
        if arq.name.lower().endswith(".xml"):

            xmls.append(arq)

        # =========================
        # ZIP
        # =========================
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
                    f"Erro ZIP {arq.name}: {e}"
                )

# =========================
# PROCESSAMENTO
# =========================
if xmls:

    total = len(xmls)

    st.info(f"📦 {total} XMLs encontrados")

    barra = st.progress(0)

    canceladas = set()

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

                chave = txt(
                    root.find(".//nfe:infEvento", ns),
                    "nfe:chNFe"
                )

                if chave:
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

            root = ET.fromstring(conteudo)

            if root.find('.//nfe:infEvento', ns) is not None:
                continue

            ide = root.find('.//nfe:ide', ns)
            emit = root.find('.//nfe:emit', ns)
            dest = root.find('.//nfe:dest', ns)

            emit_end = emit.find(
                'nfe:enderEmit',
                ns
            ) if emit is not None else None

            dest_end = dest.find(
                'nfe:enderDest',
                ns
            ) if dest is not None else None

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
                "PJ" if cnpj else "PF"
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

                ncm = txt(prod, 'nfe:NCM')
                cfop = txt(prod, 'nfe:CFOP')

                cst = (
                    txt(icms, 'nfe:CST')
                    or
                    txt(icms, 'nfe:CSOSN')
                )

                aliquota = txt(
                    icms,
                    'nfe:pICMS'
                )

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

                divergencias = []

                if regra is None:

                    divergencias.append(
                        "SEM REGRA"
                    )

                else:

                    cfop_regra = (
                        str(regra["cfop_pj"])
                        if tipo_cliente == "PJ"
                        else str(regra["cfop_pf"])
                    ).replace(".0", "")

                    aliquota_regra = str(
                        regra["aliquota_icms"]
                    ).replace(".0", "")

                    if cfop != cfop_regra:

                        divergencias.append(
                            f"CFOP {cfop} diferente da regra"
                        )

                    try:

                        if (
                            aliquota
                            and
                            float(aliquota)
                            !=
                            float(aliquota_regra)
                        ):

                            divergencias.append(
                                f"ICMS {aliquota} diferente da regra"
                            )

                    except:
                        pass

                tem_st = cst in [
                    "10",
                    "30",
                    "60",
                    "70"
                ]

                if regra_st and not tem_st:

                    divergencias.append(
                        "Deveria ter ST"
                    )

                dados.append({

                    "NF": txt(
                        ide,
                        'nfe:nNF'
                    ),

                    "Produto": txt(
                        prod,
                        'nfe:xProd'
                    ),

                    "NCM": ncm,

                    "CFOP": cfop,

                    "CST": cst,

                    "ICMS": aliquota,

                    "Status": status,

                    "Validação": (
                        "OK"
                        if not divergencias
                        else "DIVERGENTE"
                    ),

                    "Divergências": (
                        " | ".join(divergencias)
                    )

                })

            barra.progress((i + 1) / total)

        except Exception as e:

            st.error(
                f"Erro: {e}"
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
        "relatorio.csv",
        "text/csv"
    )

    st.dataframe(
        df.head(500)
    )

    if len(df) > 500:

        st.warning(
            "Mostrando apenas 500 linhas."
        )