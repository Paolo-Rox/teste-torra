import streamlit as st 
import yaml
import base64
import requests
import re

#------------- FUNÇÕES

def github_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2026-03-10",
    }

def verificar_configs_yaml(owner, repo, branch, token):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/configs_yaml"

    response = requests.get(
        url,
        headers=github_headers(token),
        params={"ref": branch},
        timeout=20
    )

    if response.status_code == 200:
        return True

    if response.status_code == 404:
        return False

    raise RuntimeError(
        f"Erro ao verificar configs_yaml: "
        f"{response.status_code} - {response.text}"
    )

def salvar_yaml_github(
    yaml_string,
    owner,
    repo,
    branch,
    nome_arquivo,
    token
):
    caminho = f"configs_yaml/{nome_arquivo}"

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{caminho}"
    )

    headers = github_headers(token)

    # Verifica se o arquivo já existe
    response_get = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=20
    )

    sha = None

    if response_get.status_code == 200:
        sha = response_get.json()["sha"]

    elif response_get.status_code != 404:
        raise RuntimeError(
            f"Erro ao verificar arquivo: "
            f"{response_get.status_code} - {response_get.text}"
        )

    # Converte YAML para Base64
    conteudo_base64 = base64.b64encode(
        yaml_string.encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": f"feat: adicionar {nome_arquivo}",
        "content": conteudo_base64,
        "branch": branch
    }

    # Se já existe, GitHub exige o SHA
    if sha:
        payload["sha"] = sha

    response_put = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=20
    )

    if response_put.status_code not in (200, 201):
        raise RuntimeError(
            f"Erro ao salvar YAML no GitHub: "
            f"{response_put.status_code} - {response_put.text}"
        )

    return response_put.json()

def load_schema(caminho):

    with open(caminho,"r",encoding="utf-8")as arquivo:

        return yaml.safe_load(arquivo)

def create_field(field,prefix=""):

    nome = field["name"]

    label = field["label"]

    tipo = field["type"]

    default = field.get("default")

    description = field.get("description")
    placeholder = field.get("placeholder")

    key = f"{prefix}input_{nome}" if prefix else f"input_{nome}"
    val_atual = st.session_state.get(key, default)
    badge_html = get_badge_html(field, val_atual)
    label_html = f'<div style="font-size: 14px; font-weight: 500; margin-bottom: 12px;">{label} {badge_html}</div>'

    if tipo == "text":
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.text_input(
            label,
            value=default or "",
            help=description,
            placeholder=placeholder,
            key=key,
            label_visibility="collapsed")
        
    elif tipo == "text_list":
        st.markdown(label_html, unsafe_allow_html=True)
        texto = st.text_area(
            label,
            help=description,
            placeholder=placeholder or "Digite um item por linha",
            key=key,
            label_visibility="collapsed")
        valor = [
            linha.strip()
            for linha in texto.splitlines()
            if linha.strip()]
        
    elif tipo == "select":
        st.markdown(label_html, unsafe_allow_html=True)
        options = field.get("options", [])
        index = 0
        if default in options:
            index = options.index(default)
        valor = st.selectbox(
            label,
            options,
            index=index,
            help=description,
            placeholder=placeholder,
            key=key,
            label_visibility="collapsed")
    elif tipo == "number":
        minimo = field.get("min")
        maximo = field.get("max")
        default = field.get("default")

        if default is None:
            default = minimo if minimo is not None else 0
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.number_input(
            label,
            min_value=minimo,
            max_value=maximo,
            value=default,
            help=description,
            placeholder=placeholder,
            key=key,
            label_visibility="collapsed")

    elif tipo == "boolean":
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.checkbox(
            label,
            value=default if default is not None else False,
            help=description,
            key=key,
            label_visibility="collapsed")

    elif tipo == "date":
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.date_input(
            label,
            help=description,
            key=key,
            label_visibility="collapsed")

    elif tipo == "time":
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.time_input(
            label,
            help=description,
            key=key,
            label_visibility="collapsed")
    elif tipo == "object":
        valor = {}
        campos = field.get("fields", [])
        st.markdown(f"**{label}**")
        for subfield in campos:
            if not campo_visivel(subfield, valor):
                continue
            sub_nome, sub_valor = create_field(subfield)
            valor[sub_nome] = sub_valor
    elif tipo == "object_list":
        valor = []
        st.markdown(f"### **{label}**")
        item_fields = field.get("item_fields", [])
        quantidade = st.number_input(
            f"Quantidade de itens em {label}",
            min_value=0,
            value=0,
            step=1)
        for i in range(quantidade):
            st.markdown(f"#### Pipe {i + 1}")
            item = {}
            table_field = next(
                f for f in item_fields
                if f["name"] == "table")
            _, table = create_field(table_field, prefix=f"{key}_{i}_")
            item["table"] = table

            schema_field = next(
                f for f in item_fields
                if f["name"] == "schema")

            _, schema = create_field(schema_field,prefix=f"{key}_{i}_")
            item["schema"] = schema

            use_domain = st.checkbox(
                "Usar domínio",
                value=False,
                key=f"pipe_{i}_use_domain")

            item["use_domain"] = use_domain

            if use_domain:
                quantidade_dominios = st.number_input(
                    "Quantidade de domínios",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"pipe_{i}_domain_quantity")
                dominios = []
                for j in range(quantidade_dominios):

                    dominio = st.text_input(
                        f"Domínio {j + 1}",
                        key=f"pipe_{i}_domain_{j}"
                    )

                    if dominio.strip():
                        dominios.append(dominio.strip())

                item["domain"] = dominios

            item.pop("use_domain", None)

            valor.append(item)
    elif tipo == "command_list":
        valor = []
        minimo = field.get("min", 0)
        maximo = field.get("max", None)
        st.markdown(f"### **{label}**")

        quantidade = st.number_input(
            f"Quantidade de comandos em {label}",
            min_value=minimo,
            max_value=maximo,
            value=0,
            step=1
        )

        for i in range(quantidade):

            st.markdown(f" Comando {i + 1}")

            command_id = st.text_input(
                "id",
                key=f"{nome}_id_{i}"
            )

            command = st.text_input(
                "cmd",
                key=f"{nome}_cmd_{i}"
            )

            valor.append({
                "id": command_id,
                "cmd": command
            })
    elif tipo == "text_area":
        st.markdown(label_html, unsafe_allow_html=True)
        valor = st.text_area(
                    label,
                    value=default or "",
                    help=description,
                    placeholder=placeholder,
                    key=key,
            label_visibility="collapsed")
    else:
        st.warning(
            f"Tipo de campo não suportado: {tipo}")
        valor = st.text_input(label, key=key)

    return nome, valor

def validate_fields(schema,values):

    erros = []

    for field in schema["fields"]:
        if not campo_visivel(field, values):
            continue
        nome = field["name"]
        if nome not in values:
            continue
        label = field.get("label", nome)
        required = field.get("required", False)
        required_when = field.get("required_when")
        if required_when:
            condicao_atendida = True
            for campo, valor_esperado in required_when.items():
                valor_atual = values.get(campo)
                if isinstance(valor_esperado, list):
                    if valor_atual not in valor_esperado:
                        condicao_atendida = False
                else:
                    if valor_atual != valor_esperado:
                        condicao_atendida = False

            if condicao_atendida:
                required = True
        valor = values.get(nome)
        if required and not valor:
            erros.append(
                f"O campo '{label}' é obrigatório.")

    return erros

def campo_visivel(field, valores):
    regra = field.get("visible_when")
    if not regra:
        return True
    for campo, valor_esperado in regra.items():
        valor_atual = valores.get(campo)
        if isinstance(valor_esperado, list):
            if valor_atual not in valor_esperado:
                return False
        else:

            if valor_atual != valor_esperado:
                return False
    return True

def get_badge_html(field, value):
    required = field.get("required", False)
    
    is_filled = False
    if isinstance(value, bool):
        is_filled = value
    elif isinstance(value, list):
        is_filled = len(value) > 0
    elif value is not None and str(value).strip() != "":
        is_filled = True

    if required:
        if is_filled:
            return '<span class="badge badge-success">✓ Validado</span>'
        else:
            return '<span class="badge badge-danger">● Obrigatório</span>'
    else:
        if is_filled:
            return '<span class="badge badge-success">✓ Preenchido</span>'
        else:
            return '<span class="badge badge-optional">Opcional</span>'
def render_stepper(etapa_atual):
    cor_ativa = "#38bdf8"    
    cor_inativa = "#1e293b"  
    cor_texto_ativo = "#ffffff"
    cor_texto_inativo = "#64748b"
    def get_style(etapa_item):
        if etapa_atual >= etapa_item:
            return cor_ativa, cor_texto_ativo, cor_ativa
        return cor_inativa, cor_texto_inativo, cor_inativa
    bg1, txt1, line1 = get_style(1)
    bg2, txt2, line2 = get_style(2)
    bg3, txt3, line3 = get_style(3)
    html = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; margin: 10px 0 40px 0; font-family: sans-serif; position: relative;">
        <!-- Línea conectora de fondo -->
        <div style="position: absolute; top: 20px; left: 15%; right: 15%; height: 3px; background-color: {cor_inativa}; z-index: 0;"></div>
        <!-- Línea conectora de progreso activa -->
        <div style="position: absolute; top: 20px; left: 15%; width: { (etapa_atual - 1) * 35 }%; height: 3px; background-color: {cor_ativa}; z-index: 1; transition: width 0.4s ease;"></div>
        <!-- Etapa 1 -->
        <div style="display: flex; flex-direction: column; align-items: center; width: 33%; z-index: 2;">
            <div style="background-color: {bg1}; color: white; border-radius: 50%; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; margin-bottom: 10px; border: 4px solid var(--bg-color); box-shadow: 0 0 0 1px {bg1};">1</div>
            <div style="color: {txt1}; font-size: 14px; font-weight: 600;">Informações Iniciais</div>
        </div>
        <!-- Etapa 2 -->
        <div style="display: flex; flex-direction: column; align-items: center; width: 33%; z-index: 2;">
            <div style="background-color: {bg2}; color: white; border-radius: 50%; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; margin-bottom: 10px; border: 4px solid var(--bg-color); box-shadow: 0 0 0 1px {bg2};">2</div>
            <div style="color: {txt2}; font-size: 14px; font-weight: 600;">Configuração Técnica</div>
        </div>
        <!-- Etapa 3 -->
        <div style="display: flex; flex-direction: column; align-items: center; width: 33%; z-index: 2;">
            <div style="background-color: {bg3}; color: white; border-radius: 50%; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 16px; margin-bottom: 10px; border: 4px solid var(--bg-color); box-shadow: 0 0 0 1px {bg3};">3</div>
            <div style="color: {txt3}; font-size: 14px; font-weight: 600;">Revisão Final</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
#------------- CONFIGURAÇÕES
dbt_schema = load_schema("dbt_schema.yaml")

campos_basicos = [
    "name",
    "description",
    "execution_type",
    "owner",
    "schedule",
    "start_date",
    "tags"
]
MAPA_TIPO_EXECUCAO = {
    "Consolidado para Relatórios e BI (Datamarts)": "datamarts",
    "Camada de Staging / Raw": "staging",
    "Transformação Intermediária / Core": "intermediate"}

MAPA_FREQUENCIA_CRON = {
    "Diário (Madrugada)": "0 2 * * *",
    "Diário (Início do Dia)": "0 7 * * *",
    "De Hora em Hora": "0 * * * *",
    "Semanal (Segunda-feira)": "0 3 * * 1",
    "Mensal (Dia 1)": "0 3 1 * *"}
st.set_page_config(
    page_title="TORRA",
    layout="wide")

st.markdown("""
<div class="main-title">
    Factory Configurator
</div>

<div class="main-subtitle">
    Crie, valide e gere configurações para DBT Factory e File Factory
</div>
""", unsafe_allow_html=True)

if "theme" not in st.session_state:
    st.session_state["theme"] = "Escuro"

if "etapa_dbt" not in st.session_state or st.session_state["etapa_dbt"] == "":
    st.session_state["etapa_dbt"] = 1
    
if "dbt_values" not in st.session_state:
    st.session_state["dbt_values"] = {}
#-------------- FRONT

with st.sidebar:
    st.markdown("## Configuração")
    st.radio("Modo de Apariencia:", ["Escuro", "Claro"], horizontal=True, key="theme")
if st.session_state["theme"] == "Escuro":
    theme_css = """
    :root {
        --bg-color: #0e1117;
        --sidebar-bg: #161b22;
        --text-color: #f1f5f9;
        --subtitle-color: #94a3b8;
        --badge-succ-bg: #143823; --badge-succ-text: #4ade80;
        --badge-err-bg: #450a0a; --badge-err-text: #f87171;
        --badge-opt-bg: #27272a; --badge-opt-text: #a1a1aa;
        --alert-err-bg: linear-gradient(90deg, rgba(69, 10, 10, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
        --alert-succ-bg: linear-gradient(90deg, rgba(20, 56, 35, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
    }
    """
else:
    theme_css = """
    :root {
        --bg-color: #ffffff;
        --sidebar-bg: #f8fafc;
        --text-color: #0f172a;
        --subtitle-color: #475569;
        --badge-succ-bg: #dcfce7; --badge-succ-text: #166534;
        --badge-err-bg: #fee2e2; --badge-err-text: #991b1b;
        --badge-opt-bg: #f4f4f5; --badge-opt-text: #3f3f46;
        --alert-err-bg: linear-gradient(90deg, rgba(254, 226, 226, 0.9) 0%, rgba(248, 250, 252, 0.9) 100%);
        --alert-succ-bg: linear-gradient(90deg, rgba(220, 252, 231, 0.9) 0%, rgba(248, 250, 252, 0.9) 100%);
    }

    /* Reglas CSS aplicadas ÚNICAMENTE en modo claro */
    .stApp, header[data-testid="stHeader"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    [data-testid="stSidebar"] {
        background-color: #f8fafc !important;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label, [data-testid="stMarkdownContainer"] p {
        color: #0f172a !important;
    }
    input, [data-baseweb="select"] > div, [data-testid="stExpander"] {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    [data-baseweb="menu"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    """

st.markdown(f"""
<style>
    {theme_css}
    
    .main-title {{
        font-size: 38px;
        font-weight: 700;
        margin-bottom: 0;
    }}
    .main-subtitle {{
        color: var(--subtitle-color);
        font-size: 16px;
        margin-top: 4px;
        margin-bottom: 25px;
    }}
    .step-title {{
        font-size: 24px;
        font-weight: 650;
        margin-bottom: 2px;
    }}
    .step-description {{
        color: var(--subtitle-color);
        font-size: 14px;
        margin-bottom: 20px;
    }}
    .stepper {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 10px 0 25px 0;
        color: var(--stepper-color);
        font-size: 14px;
    }}
    .step-active {{
        font-weight: 700;
    }}
    .step-line {{
        color: var(--step-line-color);
    }}
    .badge {{
        display: inline-block;
        padding: 2px 10px;
        font-size: 11px;
        font-weight: 600;
        border-radius: 12px;
        margin-left: 8px;
        vertical-align: middle;
    }}
    .badge-success {{
        background-color: var(--badge-succ-bg);
        color: var(--badge-succ-text);
        border: 1px solid var(--badge-succ-border);
    }}
    .badge-danger {{
        background-color: var(--badge-err-bg);
        color: var(--badge-err-text);
        border: 1px solid var(--badge-err-border);
    }}
    .badge-optional {{
        background-color: var(--badge-opt-bg);
        color: var(--badge-opt-text);
        border: 1px solid var(--badge-opt-border);
    }}
</style>
""", unsafe_allow_html=True)
aba1 , aba2 = st.tabs(["Configuração de Dados","Configuração de Arquivos"])

#------------------- dbt_facotry

with aba1:
    etapa = st.session_state["etapa_dbt"]
    render_stepper(etapa)
    if st.session_state["etapa_dbt"] == 1:
        st.markdown(
            '<div class="step-title">Dados Gerais</div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div class="step-description">'
            'Configure as informações básicas desta automação .'
            '</div>',
            unsafe_allow_html=True)
        values = {}
        #fila 1
        col1, col2 = st.columns(2)
        with col1:
            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "name")

            nome, valor = create_field(field)
            values[nome] = valor
        with col2:
            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "execution_type"
            )

            nome, valor = create_field(field)
            values[nome] = valor
        #fila 2
        col1, col2 = st.columns(2)
        with col1:

            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "owner"
            )

            nome, valor = create_field(field)
            values[nome] = valor

        with col2:

            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "schedule"
            )

            nome, valor = create_field(field)
            values[nome] = valor
        #fila 3
        col1, col2 = st.columns(2)
        with col1:

            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "start_date"
            )

            nome, valor = create_field(field)
            values[nome] = valor

        with col2:

            field = next(
                f for f in dbt_schema["fields"]
                if f["name"] == "tags"
            )

            nome, valor = create_field(field)
            values[nome] = valor
        #fila 4 descrição
        field = next(
            f for f in dbt_schema["fields"]
            if f["name"] == "description"
        )

        nome, valor = create_field(field)
        values[nome] = valor

        erros = validate_fields(dbt_schema,values)

        if erros:
            itens_erro_html = "".join([f'<li style="margin-bottom: 6px;">{erro}</li>' for erro in erros])
            qtd_erros = len(erros)
            texto_badge = f"{qtd_erros} Erro" if qtd_erros == 1 else f"{qtd_erros} Erros"
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, rgba(69, 10, 10, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
                border: 1px solid #ef444440;
                border-left: 4px solid #ef4444;
                padding: 16px 20px;
                border-radius: 8px;
                margin: 15px 0;
            ">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                    <div style="color: #f87171; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>⚠️</span> Pendências Encontradas
                    </div>
                    <span class="badge badge-danger" style="padding: 6px 12px; font-size: 12px;">{texto_badge}</span>
                </div>
                <div style="color: #fca5a5; font-size: 13.5px;">
                    <ul style="margin: 0; padding-left: 20px;">
                        {itens_erro_html}
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style="
                    background: linear-gradient(90deg, rgba(20, 56, 35, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid #22c55e40;
                    border-left: 4px solid #22c55e;
                    padding: 16px 20px;
                    border-radius: 8px;
                    margin: 15px 0;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                ">
                    <div>
                        <div style="color: #4ade80; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                            <span>✓</span> Configuração Validada com Sucesso
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-top: 4px;">
                            Todos os campos obrigatórios foram preenchidos corretamente.
                        </div>
                    </div>
                    <span class="badge badge-success" style="padding: 6px 12px; font-size: 12px;">Pronto para Avançar</span>
                </div>
                """, unsafe_allow_html=True)
        continuar = st.button(
            "Continuar →",disabled=len(erros) > 0,type="primary",use_container_width=True)
        
        if continuar:
            st.session_state["etapa_dbt"] = 2
            st.rerun()

    elif st.session_state["etapa_dbt"] == 2:
            values = st.session_state["dbt_values"]
            tipo_execucao = values.get("execution_type", "")

            for f in dbt_schema["fields"]:
                k = f"input_{f['name']}"
                if k in st.session_state:
                    values[f["name"]] = st.session_state[k]
                elif f["name"] not in values:
                    values[f["name"]] = f.get("default")
            st.markdown(f"""
                <div style="margin-bottom: 24px;">
                    <div class="step-title">2. Seleção de Ferramentas Configuração de Execução</div>
                    <div style="color: #94a3b8; font-size: 14px; margin-top: 4px;">
                        Configure os parâmetros específicos para a execução: 
                        <span style="
                            background-color: #0f172a; 
                            color: #38bdf8; 
                            padding: 4px 10px; 
                            border-radius: 6px; 
                            font-weight: 600; 
                            border: 1px solid #0284c740;
                            font-size: 13px;
                            margin-left: 4px;
                        ">{tipo_execucao}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            campos_etapa_2 = [
                f for f in dbt_schema["fields"] 
                if f["name"] not in campos_basicos and campo_visivel(f, values)]
            campos_booleans = [f for f in campos_etapa_2 if f.get("type") == "boolean"]
            campos_regulares = [f for f in campos_etapa_2 if f.get("type") != "boolean"]
            tipos_largos = ["text_area", "text_list", "object_list", "command_list"]
            campo_avancadas = next((f for f in campos_booleans if["name"] == "avancadas"),None)
            if campos_booleans:
                col_bp1, col_bp2 = st.columns(2)

                for idx, field in enumerate(campos_booleans):

                    target_col = col_bp1 if idx % 2 == 0 else col_bp2

                    with target_col:
                        nome, valor = create_field(field)
                        values[nome] = valor
            if campo_avancadas:
                st.markdown("""
                <div style="
                    margin: 24px 0 12px 0;
                    border-top: 1px solid #334155;
                    padding-top: 16px;
                ">
                </div>
                """, unsafe_allow_html=True)

                nome, valor = create_field(campo_avancadas)
                values[nome] = valor
            
            if values.get("avancadas", False):
                st.markdown("""<div style="font-size: 30px; font-weight: 600; color: #cbd5e1; margin: 28px 0 28px 0; border-top: 1px solid #334155; padding-top: 16px;">Configuração de Execução</div>""",unsafe_allow_html=True)
                st.info("💡 Valores customizados: Edite os campos abaixo com os dados customizados.")
                col1, col2 = st.columns(2)
                usar_col1 = True
                for field in campos_regulares:
                    tipo = field.get("type")
                    nome_campo = field.get("name", "").lower()
                    is_header = tipo in ["header", "section", "title"] or "qlik" in nome_campo
                    is_largo = ((tipo in tipos_largos) or ("dataset" in nome_campo) or ("tabela" in nome_campo)or ("automation" in nome_campo)or ("token" in nome_campo))

                    if is_header:
                        usar_col1 = True
                    if is_largo:
                        nome, valor = create_field(field)
                        values[nome] = valor
                    else:
                        target_col = col1 if usar_col1 else col2
                        with target_col:
                            nome, valor = create_field(field)
                            values[nome] = valor
                        usar_col1 = not usar_col1
            tem_avancadas_activo = values.get("avancadas", False)
            campos_etapa_2_todos = [
                    f for f in dbt_schema["fields"] 
                    if f["name"] not in campos_basicos and campo_visivel(f, values)]
            if not tem_avancadas_activo:
                campos_para_validar = [
                    f for f in campos_etapa_2_todos 
                    if f.get("type") == "boolean" or f["name"] == "avancadas"]
            else:
                campos_para_validar = campos_etapa_2_todos
            esquema_etapa_2 = {"fields": campos_para_validar}
            erros_etapa_2 = validate_fields(esquema_etapa_2, values)

            if erros_etapa_2:
                itens_erro_html = "".join([f'<li style="margin-bottom: 6px;">{erro}</li>' for erro in erros_etapa_2])
                qtd_erros = len(erros_etapa_2)
                texto_badge = f"{qtd_erros} Erro" if qtd_erros == 1 else f"{qtd_erros} Erros"

                st.markdown(f"""
                <div style="
                    background: linear-gradient(90deg, rgba(69, 10, 10, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid #ef444440;
                    border-left: 4px solid #ef4444;
                    padding: 16px 20px;
                    border-radius: 8px;
                    margin: 24px 0 16px 0;
                ">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <div style="color: #f87171; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                            <span>⚠️</span> Pendências na Etapa 2
                        </div>
                        <span class="badge badge-danger" style="padding: 6px 12px; font-size: 12px;">{texto_badge}</span>
                    </div>
                    <div style="color: #fca5a5; font-size: 13.5px;">
                        <ul style="margin: 0; padding-left: 20px;">
                            {itens_erro_html}
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="
                    background: linear-gradient(90deg, rgba(20, 56, 35, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%);
                    border: 1px solid #22c55e40;
                    border-left: 4px solid #22c55e;
                    padding: 16px 20px;
                    border-radius: 8px;
                    margin: 24px 0 16px 0;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                ">
                    <div>
                        <div style="color: #4ade80; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                            <span>✓</span> Configuração da Etapa 2 Pronta
                        </div>
                        <div style="color: #94a3b8; font-size: 13px; margin-top: 4px;">
                            Todos os parâmetros de execução estão validados.
                        </div>
                    </div>
                    <span class="badge badge-success" style="padding: 6px 12px; font-size: 12px;">Pronto para Avançar</span>
                </div>
                """, unsafe_allow_html=True)

            # Botones de Navegação (Voltar e Continuar)
            col_nav1, col_nav2 = st.columns([1, 2])
            with col_nav1:
                if st.button("← Voltar à Etapa 1", use_container_width=True):
                    st.session_state["etapa_dbt"] = 1
                    st.rerun()

            with col_nav2:
                continuar_etapa_3 = st.button(
                    "Avançar para Análise Final →", 
                    key="continuar_etapa_3",
                    disabled=len(erros_etapa_2) > 0,
                    type="primary",
                    use_container_width=True
                )
                if continuar_etapa_3:
                    st.toast("Parâmetros salvos! Carregando Análise Final...", icon="🚀")
                    st.session_state["etapa_dbt"] = 3
                    st.rerun()

    #--------- step 3
    elif st.session_state["etapa_dbt"] == 3:
        values = st.session_state.get("dbt_values", {})
        detalhes_map = {
                    "schedule": "Agendamento",
                    "tags": "Tags",
                    "description": "Descrição",
                    "start_date": "Início",
                    "limit_time": "Tempo Limite",
                    "dbt_env": "Ambiente"}

        st.markdown("""
                <style>
                    .rev-header {
                        display: flex;
                        align-items: baseline;
                        justify-content: space-between;
                        margin-bottom: 4px;
                    }
                    .rev-title { font-size: 22px; font-weight: 650; margin: 0; }
                    .rev-subtitle { color: #94a3b8; font-size: 13.5px; margin: 4px 0 24px 0; }

                    /* Cartões principais (nome / tipo / owner) */
                    .rev-card {
                        background-color: #131c2e;
                        border: 1px solid #24304a;
                        border-radius: 10px;
                        padding: 16px 18px;
                        height: 100%;
                    }
                    .rev-card-label {
                        color: #64748b;
                        font-size: 10.5px;
                        font-weight: 600;
                        letter-spacing: 0.6px;
                        text-transform: uppercase;
                        margin-bottom: 6px;
                    }
                    .rev-card-value {
                        color: #f1f5f9;
                        font-size: 15px;
                        font-weight: 600;
                        margin: 0;
                        word-break: break-word;
                    }
                    .rev-card-value.accent { color: #38bdf8; }

                    .rev-section {
                        margin-top: 32px;
                        margin-bottom: 14px;
                        padding-bottom: 8px;
                        border-bottom: 1px solid #1e293b;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                    }
                    .rev-section-title {
                        color: #cbd5e1;
                        font-size: 13px;
                        font-weight: 650;
                        letter-spacing: 0.4px;
                        text-transform: uppercase;
                        margin: 0;
                    }
                    .rev-section-count {
                        color: #64748b;
                        font-size: 11.5px;
                        font-weight: 500;
                    }

                    /* "Informações Gerais" como lista tipo ficha técnica,
                       linha por linha, sem caixas — label à esquerda,
                       valor à direita, separados por um traço fino. */
                    .rev-dl-row {
                        display: flex;
                        justify-content: space-between;
                        align-items: baseline;
                        gap: 16px;
                        padding: 9px 2px;
                        border-bottom: 1px solid #1a2436;
                    }
                    .rev-dl-row:last-child { border-bottom: none; }
                    .rev-dl-label {
                        color: #64748b;
                        font-size: 13px;
                        font-weight: 500;
                        white-space: nowrap;
                    }
                    .rev-dl-value {
                        color: #e2e8f0;
                        font-size: 13.5px;
                        font-weight: 500;
                        text-align: right;
                    }

                    /* Títulos de bloco de execução — sem caixa, só uma
                       barrinha de cor + texto, tipo "kicker". O conteúdo
                       (st.code, tags) fica solto embaixo, sem fundo extra. */
                    .rev-exec-title {
                        display: flex;
                        align-items: center;
                        gap: 9px;
                        margin: 22px 0 10px 0;
                    }
                    .rev-exec-bar {
                        width: 4px;
                        height: 15px;
                        border-radius: 2px;
                        flex-shrink: 0;
                    }
                    .rev-exec-text {
                        font-size: 13px;
                        font-weight: 650;
                        letter-spacing: 0.3px;
                        text-transform: uppercase;
                        color: #e2e8f0;
                    }
                    .rev-exec-count {
                        color: #64748b;
                        font-size: 11.5px;
                        font-weight: 400;
                        text-transform: none;
                        letter-spacing: 0;
                    }

                    .rev-pill-row { display: flex; flex-wrap: wrap; gap: 8px; }
                    .rev-pill {
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        background-color: #131c2e;
                        border: 1px solid #1e293b;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 12.5px;
                        color: #cbd5e1;
                    }
                    .rev-pill-dot {
                        width: 7px;
                        height: 7px;
                        border-radius: 50%;
                        display: inline-block;
                    }
                    .rev-pill-dot.on { background-color: #4ade80; }
                    .rev-pill-dot.off { background-color: #64748b; }

                    .rev-tag {
                        display: inline-block;
                        background: #131c2e;
                        border: 1px solid #1e293b;
                        padding: 5px 11px;
                        margin: 0 6px 6px 0;
                        border-radius: 6px;
                        font-size: 12px;
                        color: #cbd5e1;
                    }

                    /* Blocos de execução (dbt_run, qlik_automation, etc.)
                       Cada tipo tem uma cor de destaque diferente via --accent,
                       aplicada na borda esquerda, para não ficar tudo igual. */
                    .rev-block {
                        background-color: #10182a;
                        border: 1px solid #1e293b;
                        border-left: 3px solid var(--accent, #334155);
                        border-radius: 8px;
                        padding: 14px 16px;
                        margin-bottom: 12px;
                    }
                    .rev-block.acc-dbt   { --accent: #38bdf8; }  /* dbt_run / dbt_test / dbt_profile */
                    .rev-block.acc-qlik  { --accent: #a78bfa; }  /* qlik_automation */
                    .rev-block.acc-files { --accent: #fbbf24; }  /* pipes / file_generation */
                    .rev-block.acc-tabs  { --accent: #34d399; }  /* tabelas_para_checar */

                    .rev-block-title {
                        color: #94a3b8;
                        font-size: 12px;
                        font-weight: 650;
                        letter-spacing: 0.3px;
                        text-transform: uppercase;
                        margin-bottom: 10px;
                    }
                    .rev-block-title .count {
                        color: #64748b;
                        font-weight: 400;
                        text-transform: none;
                        letter-spacing: 0;
                    }
                </style>
                """, unsafe_allow_html=True)

        st.markdown("""
                <div class="rev-header">
                    <p class="rev-title">Revisão e Confirmação</p>
                </div>
                <div class="rev-subtitle">Verifique os dados antes de gerar a DAG.</div>
                """, unsafe_allow_html=True)

        dados_finais = {}
        for f in dbt_schema["fields"]:
            if not campo_visivel(f, values):
                continue

            nome_campo = f["name"]
            tipo = f["type"]
            valor = values.get(nome_campo)

            if tipo == "text_list" and isinstance(valor, str):
                valor = [linha.strip() for linha in valor.splitlines() if linha.strip()]
            elif tipo in ["date", "time"] and valor is not None:
                valor = str(valor)

            if valor is not None and valor != "" and valor != [] and valor != {}:
                dados_finais[nome_campo] = valor
        if "name" in dados_finais:
            nome_seguro = re.sub(r"[^A-Za-z0-9_.-]+", "_", dados_finais["name"])
            dados_finais["name"] = f"app_executa_dbt_{nome_seguro}"
        tab_visao, tab_yaml = st.tabs(["Visão Consolidada", "Estrutura YAML"])
        with tab_visao:
            campos_principais = ["name", "execution_type", "owner"]
            cols_activas = [c for c in campos_principais if c in dados_finais]

            if cols_activas:
                cols = st.columns(len(cols_activas))
                labels_map = {
                            "name": "Nome da DAG",
                            "execution_type": "Tipo de Execução",
                            "owner": "Proprietário"}
                for idx, campo in enumerate(cols_activas):
                    with cols[idx]:
                        classe_valor = "rev-card-value accent" if campo == "execution_type" else "rev-card-value"
                        st.markdown(f"""
                                <div class="rev-card">
                                    <p class="rev-card-label">{labels_map.get(campo, campo.upper())}</p>
                                    <p class="{classe_valor}">{dados_finais[campo]}</p></div>
                                """, unsafe_allow_html=True)
            campos_complejos = ['tabelas_para_checar', 'dbt_run', 'dbt_test', 'dbt_profile', 'qlik_automation', 'pipes', 'file_generation']
            campos_ignorados = set(campos_principais + campos_complejos)
            detalhes_existentes = [
                        k for k, v in dados_finais.items()
                        if k not in campos_ignorados and not isinstance(v, bool)
                    ]

            if detalhes_existentes:
                st.markdown("""
                        <div class="rev-section">
                            <p class="rev-section-title">Informações Gerais</p>
                        </div>
                        """, unsafe_allow_html=True)

                linhas_html = ""
                for k in detalhes_existentes:
                    val = dados_finais[k]
                    val_str = ", ".join(str(x) for x in val) if isinstance(val, list) else str(val)
                    label_text = detalhes_map.get(k, k.replace('_', ' ').title())
                    linhas_html += f"""
                            <div class="rev-dl-row">
                                <span class="rev-dl-label">{label_text}</span>
                                <span class="rev-dl-value">{val_str}</span>
                            </div>
                            """
                st.markdown(linhas_html, unsafe_allow_html=True)

            bools = {k: v for k, v in dados_finais.items() if isinstance(v, bool)}
            if bools:
                st.markdown(f"""
                        <div class="rev-section">
                            <p class="rev-section-title">Parâmetros</p>
                            <span class="rev-section-count">{sum(bools.values())} de {len(bools)} ativos</span>
                        </div>
                        """, unsafe_allow_html=True)

                pills_html = ""
                for k, v in bools.items():
                    dot_class = "on" if v else "off"
                    status_str = "Ativo" if v else "Inativo"
                    pills_html += f"""<div class="rev-pill">
                                <span class="rev-pill-dot {dot_class}"></span>
                                {k} &middot; {status_str}
                            </div>
                            """
                st.markdown(f'<div class="rev-pill-row">{pills_html}</div>', unsafe_allow_html=True)
            tem_config_execucao = any(
                dados_finais.get(c) for c in
                ['tabelas_para_checar', 'dbt_run', 'dbt_test', 'dbt_profile', 'qlik_automation', 'pipes', 'file_generation']
                    )

            if tem_config_execucao:
                st.markdown("""
                        <div class="rev-section">
                            <p class="rev-section-title">Configuração de Execução</p>
                        </div>
                        """, unsafe_allow_html=True)

                def exec_title(texto, cor, contagem=None):
                    sufixo = f'<span class="rev-exec-count"> &middot; {contagem}</span>' if contagem is not None else ""
                    st.markdown(f"""
                            <div class="rev-exec-title">
                                <span class="rev-exec-bar" style="background:{cor};"></span>
                                <span class="rev-exec-text">{texto}{sufixo}</span>
                            </div>
                            """, unsafe_allow_html=True)

                tabelas = dados_finais.get('tabelas_para_checar', [])
                if tabelas:
                    exec_title("Tabelas Mapeadas", "#34d399", len(tabelas))
                    tabelas_html = "".join([f'<span class="rev-tag">{t}</span>' for t in tabelas])
                    st.markdown(f"<div>{tabelas_html}</div>", unsafe_allow_html=True)

                for cmd_key in ['dbt_run', 'dbt_test', 'dbt_profile']:
                    if cmd_key in dados_finais:
                        qtd = len(dados_finais[cmd_key])
                        exec_title(cmd_key.replace('_', ' ').title(), "#38bdf8", f"{qtd} comando(s)")
                        for item in dados_finais[cmd_key]:
                            st.code(f"id: {item.get('id', '')}\ncmd: {item.get('cmd', '')}", language="yaml")

                if 'qlik_automation' in dados_finais:
                    exec_title("Qlik Automation", "#a78bfa")
                    st.code(
                                yaml.dump(dados_finais['qlik_automation'], sort_keys=False, allow_unicode=True),
                                language="yaml"
                            )

                if 'pipes' in dados_finais:
                    qtd_pipes = len(dados_finais['pipes']) if isinstance(dados_finais['pipes'], list) else 1
                    exec_title("Pipes Configurados", "#fbbf24", qtd_pipes)
                    if isinstance(dados_finais['pipes'], list):
                        for pipe in dados_finais['pipes']:
                            st.code(yaml.dump(pipe, sort_keys=False, allow_unicode=True), language="yaml")
                    else:
                            st.code(yaml.dump(dados_finais['pipes'], sort_keys=False, allow_unicode=True), language="yaml")

                if 'file_generation' in dados_finais:
                    exec_title("Geração de Arquivos", "#fbbf24")
                    if isinstance(dados_finais['file_generation'], (dict, list)):
                        st.code(
                                    yaml.dump(dados_finais['file_generation'], sort_keys=False, allow_unicode=True),
                                    language="yaml"
                                )
                    else:
                        st.info(str(dados_finais['file_generation']))

        with tab_yaml:
            st.markdown('<div style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">Pré-visualização exata do arquivo a ser gerado:</div>', unsafe_allow_html=True)
            yaml_dados = dados_finais.copy()
            if "tags" in yaml_dados:
                if isinstance(yaml_dados["tags"], list):
                    elementos = yaml_dados["tags"]
                else:
                    texto_limpio = str(yaml_dados["tags"]).replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                    elementos = [t.strip() for t in texto_limpio.split(",") if t.strip()]
                yaml_dados["tags"] = f"[{','.join(elementos)}]"

            yaml_string = yaml.dump(yaml_dados, sort_keys=False, default_flow_style=False, allow_unicode=True)
            st.code(yaml_string, language="yaml")

        st.markdown("<hr style='margin: 30px 0 20px 0; border-color: #1e293b;'>", unsafe_allow_html=True)
        col_b1, col_b2, col_b3 = st.columns([1, 1, 2])

        with col_b1:
            if st.button("Voltar à Etapa 2", use_container_width=True):
                st.session_state["etapa_dbt"] = 2
                st.rerun()

        with col_b3:
            if st.button("Confirmar e Gerar DAG", type="primary", use_container_width=True):
                try:
                    owner = "Paolo-Rox"
                    repo = "teste-torra"
                    branch = "main"

                    token = st.secrets["GITHUB_TOKEN"]

                    configs_existe = verificar_configs_yaml(
                                owner=owner,
                                repo=repo,
                                branch=branch,
                                token=token
                            )

                    if configs_existe:
                        st.info("A pasta configs_yaml já existe. O arquivo será salvo nela.")
                    else:
                        st.info("A pasta configs_yaml não existe. Ela será criada automaticamente.")

                    nome_arquivo = f"dbt_config_{nome_seguro}.yaml"

                    dados_envio = dados_finais.copy()
                    if "tags" in dados_envio:
                        if isinstance(dados_envio["tags"], list):
                            elementos = dados_envio["tags"]
                        else:
                            texto_limpio = str(dados_envio["tags"]).replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                            elementos = [t.strip() for t in texto_limpio.split(",") if t.strip()]
                        dados_envio["tags"] = f"[{','.join(elementos)}]"

                    final_yaml_string = yaml.dump(
                                dados_envio,
                                sort_keys=False,
                                allow_unicode=True
                            )

                    resultado = salvar_yaml_github(
                                yaml_string=final_yaml_string,
                                owner=owner,
                                repo=repo,
                                branch=branch,
                                nome_arquivo=nome_arquivo,
                                token=token
                            )

                    arquivo_url = resultado["content"]["html_url"]
                    st.success("DAG gerada e enviada ao GitHub com sucesso.")
                    st.link_button("Abrir YAML no GitHub", arquivo_url)

                except Exception as e:
                    st.error(f"Não foi possível enviar o YAML para o GitHub: {e}")

with aba2:
    
    st.header("Configuração FILE",) 



