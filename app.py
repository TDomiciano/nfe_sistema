import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import gc
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
# LEITURA DAS REGRAS
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

    return regras, regras_st


regras, regras_st = carregar_regras()

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

st.info(
    "📦 Envie XMLs individuais ou ZIP contendo XMLs."
)

# =========================
# UPLOAD XML E ZIP
# =========================
uploads = st.file_uploader(
    "Envie XMLs ou ZIP com XMLs",
    type=["xml", "zip"],
    accept_multiple_files=True
)

arquivos = []

if uploads:

    for upload in uploads:

        # =========================
        # XML NORMAL
        # =========================
        if upload.name.lower().endswith(".xml"):

            arquivos.append(upload)

        # =========================
        # ARQUIVO ZIP
        # =========================
        elif upload.name.lower().endswith(".zip"):

            try:

                with zipfile.ZipFile(upload, 'r') as zip_ref:

                    for nome_arquivo in zip_ref.namelist():

                        if nome_arquivo.lower().endswith(".xml"):

                            xml_file = io.BytesIO(
                                zip_ref.read(nome_arquivo)
                            )

                            xml_file.name = nome_arquivo

                            arquivos.append(xml_file)

            except Exception as e:

                st.error(
                    f"Erro ao ler ZIP {upload.name}: {e}"
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

    total_arquivos = len(arquivos)

    st.write(f"📦 Total de arquivos encontrados: {total_arquivos}")

    # =========================
    # ALERTA MUITOS XMLS
    # =========================
    if total_arquivos > 5000:

        st.warning(
            "⚠️ Muitos XMLs detectados. "
            "O processamento pode demorar."
        )

    barra = st.progress(0)

    # =========================
    # PRIMEIRO LOOP
    # IDENTIFICA CANCELAMENTOS
    # =========================
    for i, arq in enumerate(arquivos):

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

            # =========================
            # EVENTO CANCELAMENTO
            # =========================
            if (
                "CANCELAMENTO" in xml_str
                and
                "110111" in xml_str
            ):

                chave_evento = ""

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

            # =========================
            # LIMPA MEMÓRIA
            # =========================
            del tree
            del root

            gc.collect()

            barra.progress((i + 1) / total_arquivos)

        except:
            pass

    # =========================
    # SEGUNDO LOOP
    # PROCESSA NFS
    # =========================
    for i, arq in enumerate(arquivos):

        try:

            arq.seek(0)

            tree = ET.parse(arq)
            root = tree.getroot()

            ns = {
                'nfe': 'http://www.portalfiscal.inf.br/nfe'
            }

            # IGNORA EVENTOS
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

                icms = (
                    imposto.find('.//nfe:ICMS/*', ns)
                    if imposto is not None
                    else None
                )

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
                # BUSCA REGRA
                # =========================
                regra = buscar_regra(
                    ncm_xml,
                    uf_origem,
                    uf_destino
                )

                divergencias = []

                if regra is not None:

                    cfop_regra = (
                        str(regra["cfop_pj"])
                        if tipo_cliente == "PJ"
                        else str(regra["cfop_pf"])
                    ).replace(".0", "")

                    aliquota_regra = str(
                        regra["aliquota_icms"]
                    ).replace(".0", "")

                    if cfop_xml != cfop_regra:

                        divergencias.append(
                            f"CFOP XML ({cfop_xml}) diferente da regra"
                        )

                    try:

                        if (
                            aliquota_xml != ""
                            and
                            float(aliquota_xml) != float(aliquota_regra)
                        ):

                            divergencias.append(
                                f"ICMS XML ({aliquota_xml}) diferente da regra ({aliquota_regra})"
                            )

                    except:
                        pass

                else:

                    divergencias.append(
                        "SEM REGRA FISCAL"
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

                    "Chave Acesso": f"'{chave_acesso}",

                    "Produto": get_text(
                        prod,
                        'nfe:xProd',
                        ns
                    ),

                    "NCM": ncm_xml,

                    "CFOP XML": cfop_xml,

                    "CST XML": cst_xml,

                    "Aliquota ICMS XML": aliquota_xml,

                    "Status": status,

                    "Validacao": (
                        "OK"
                        if len(divergencias) == 0
                        else "DIVERGENTE"
                    ),

                    "Divergencias": (
                        " | ".join(divergencias)
                    )

                })

            # =========================
            # LIMPA MEMÓRIA
            # =========================
            del tree
            del root
            del itens

            gc.collect()

            barra.progress((i + 1) / total_arquivos)

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

    st.success(
        f"✅ {len(df)} registros processados"
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

    # =========================
    # LIMITA EXIBIÇÃO
    # =========================
    st.dataframe(
        df.head(500)
    )

    if len(df) > 500:

        st.warning(
            "⚠️ Mostrando apenas os primeiros 500 registros "
            "para evitar travamentos."
        )

else:

    st.info(
        "Envie XMLs ou ZIP para iniciar."
    )
