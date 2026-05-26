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
# CARREGA TABELA ICMS
# =========================
@st.cache_data
def carregar_tabela_icms():

    tabela_icms = pd.read_excel(
        "aliquotas.xlsx"
    )

    # PRIMEIRA COLUNA = INDEX
    tabela_icms = tabela_icms.set_index(
        tabela_icms.columns[0]
    )

    # LIMPA INDEX
    tabela_icms.index = (
        tabela_icms.index
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # LIMPA COLUNAS
    tabela_icms.columns = (
        tabela_icms.columns
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # CONVERTE PARA NUMEROS
    tabela_icms = tabela_icms.apply(
        pd.to_numeric,
        errors="coerce"
    )

    return tabela_icms


tabela_icms = carregar_tabela_icms()

# =========================
# FUNÇÃO XML
# =========================
def txt(elemento, tag):

    if elemento is None:
        return ""

    achou = elemento.find(tag, ns)

    return achou.text if achou is not None else ""


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

if xmls:

    total = len(xmls)

    st.success(
        f"📦 {total} XMLs encontrados"
    )

    barra = st.progress(0)

    # =========================
    # PROCESSA XML
    # =========================
    for i, arq in enumerate(xmls):

        try:

            arq.seek(0)

            conteudo = arq.read()

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

                produto = txt(
                    prod,
                    'nfe:xProd'
                )

                valor_produto = float(
                    txt(prod, 'nfe:vProd') or 0
                )

                # =========================
                # DIFAL XML
                # =========================
                icmsufdest = (
                    imposto.find(
                        './/nfe:ICMSUFDest',
                        ns
                    )
                    if imposto is not None
                    else None
                )

                try:

                    difal_xml = float(
                        txt(
                            icmsufdest,
                            'nfe:vICMSUFDest'
                        ) or 0
                    )

                except:

                    difal_xml = 0

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

                    # BASE DUPLA
                    if aliq_interna_origem > aliq_inter:

                        difal_calculado = round(
                            (
                                valor_produto *
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
                # VALIDACAO
                # =========================
                divergencias = []

                diferenca = abs(
                    difal_xml - difal_calculado
                )

                if diferenca > 1:

                    divergencias.append(
                        f"DIFAL XML ({difal_xml}) diferente do calculado ({difal_calculado})"
                    )

                # =========================
                # DADOS
                # =========================
                dados.append({

                    "Numero NF": txt(
                        ide,
                        'nfe:nNF'
                    ),

                    "UF Origem": uf_origem,

                    "UF Destino": uf_destino,

                    "Produto": produto,

                    "Valor Produto": round(
                        valor_produto,
                        2
                    ),

                    "Aliquota Interna Origem": round(
                        aliq_interna_origem * 100,
                        2
                    ),

                    "Aliquota Interestadual": round(
                        aliq_inter * 100,
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

                    "Validacao": (
                        "OK"
                        if len(divergencias) == 0
                        else "DIVERGENTE"
                    ),

                    "Divergencias": (
                        " | ".join(divergencias)
                    )

                })

            barra.progress((i + 1) / total)

        except Exception as e:

            st.error(
                f"Erro no XML: {e}"
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

    st.dataframe(df)

else:

    st.info(
        "Envie XMLs ou ZIPs para iniciar."
    )