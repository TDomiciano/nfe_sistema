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
# TABELA ICMS
# =========================
@st.cache_data
def carregar_tabela_icms():

    tabela_icms = pd.read_excel(
        "aliquotas.xlsx"
    )

    tabela_icms = tabela_icms.set_index(
        tabela_icms.columns[0]
    )

    tabela_icms.columns = (
        tabela_icms.columns
        .astype(str)
        .str.upper()
        .str.strip()
    )

    tabela_icms.index = (
        tabela_icms.index
        .astype(str)
        .str.upper()
        .str.strip()
    )

    tabela_icms = tabela_icms.apply(
        pd.to_numeric,
        errors="coerce"
    )

    return tabela_icms


tabela_icms = carregar_tabela_icms()

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
# BUSCA ALIQUOTAS
# =========================
def buscar_aliquotas(origem, destino):

    origem = str(origem).upper().strip()
    destino = str(destino).upper().strip()

    # INTERNA ORIGEM
    aliq_interna_origem = float(
        tabela_icms.loc[origem, origem]
    )

    # INTERESTADUAL
    aliq_inter = float(
        tabela_icms.loc[origem, destino]
    )

    return aliq_interna_origem, aliq_inter


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

        # XML
        if upload.name.lower().endswith(".xml"):

            arquivos.append(upload)

        # ZIP
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

    st.write(
        f"📦 Total de arquivos encontrados: {total_arquivos}"
    )

    if total_arquivos > 5000:

        st.warning(
            "⚠️ Muitos XMLs detectados. "
            "O processamento pode demorar."
        )

    barra = st.progress(0)

    # =========================
    # LOOP CANCELAMENTO
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

            del tree
            del root

            gc.collect()

            barra.progress((i + 1) / total_arquivos)

        except:
            pass

    # =========================
    # LOOP XMLS
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
                # DIFAL XML
                # =========================
                icmsufdest = (
                    imposto.find('.//nfe:ICMSUFDest', ns)
                    if imposto is not None
                    else None
                )

                valor_difal_xml = get_text(
                    icmsufdest,
                    'nfe:vICMSUFDest',
                    ns
                )

                try:

                    difal_xml = float(
                        valor_difal_xml or 0
                    )

                except:

                    difal_xml = 0

                # =========================
                # FCP XML
                # =========================
                try:

                    fcp_xml = float(
                        get_text(
                            icmsufdest,
                            'nfe:vFCPUFDest',
                            ns
                        ) or 0
                    )

                except:

                    fcp_xml = 0

                # =========================
                # CALCULO DIFAL
                # =========================
                difal_calculado = 0

                aliq_interna_origem = 0
                aliq_inter = 0

                try:

                    aliq_interna_origem, aliq_inter = buscar_aliquotas(
                        uf_origem,
                        uf_destino
                    )

                    aliq_interna_origem = (
                        aliq_interna_origem / 100
                    )

                    aliq_inter = (
                        aliq_inter / 100
                    )

                    valor_base = float(
                        get_text(
                            prod,
                            'nfe:vProd',
                            ns
                        ) or 0
                    )

                    # BASE DUPLA
                    if aliq_interna_origem > aliq_inter:

                        difal_calculado = round(
                            (
                                valor_base *
                                (
                                    aliq_interna_origem -
                                    aliq_inter
                                )
                            )
                            /
                            (
                                1 - aliq_interna_origem
                            ),
                            2
                        )

                except Exception as e:

                    st.error(
                        f"Erro DIFAL {uf_origem}->{uf_destino}: {e}"
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

                # =========================
                # VALIDACAO DIFAL
                # =========================
                if abs(difal_xml - difal_calculado) > 1:

                    divergencias.append(
                        f"DIFAL XML ({difal_xml}) diferente do calculado ({difal_calculado})"
                    )

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

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Aliquota Interna Origem": round(
                        aliq_interna_origem * 100,
                        2
                    ),

                    "Aliquota Interestadual": round(
                        aliq_inter * 100,
                        2
                    ),

                    "Valor Produto": round(
                        float(
                            get_text(prod, 'nfe:vProd', ns) or 0
                        ),
                        2
                    ),

                    "DIFAL XML": round(
                        difal_xml,
                        2
                    ),

                    "DIFAL Calculado": round(
                        difal_calculado,
                        2
                    ),

                    "FCP XML": round(
                        fcp_xml,
                        2
                    ),

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