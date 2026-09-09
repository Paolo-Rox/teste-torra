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

        st.markdown(f"### **{label}**")

        quantidade = st.number_input(
            f"Quantidade de comandos em {label}",
            min_value=0,
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
aba1 , aba2 = st.tabs(["dbt_factory","file_factory"])

#------------------- dbt_facotry

with aba1:
    es_etapa1_activa = st.session_state["etapa_dbt"] == 1
    with st.expander("1. Informações gerais", expanded=es_etapa1_activa):
        st.markdown(
            '<div class="step-title">Dados Gerais</div>',
            unsafe_allow_html=True)
        st.markdown(
            '<div class="step-description">'
            'Configure as informações básicas da DAG.'
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

    es_etapa2_activa = st.session_state["etapa_dbt"] == 2
    with st.expander("2. Configuração de Execução", expanded=es_etapa2_activa):
        #--------- step 2
        if st.session_state["etapa_dbt"] < 2:
            st.info("🔒 Complete a Etapa 1 e clique em 'Continuar' para habilitar esta seção.")
        elif st.session_state["etapa_dbt"] >= 2:
            tipo_execucao = values.get("execution_type", "")

            for f in dbt_schema["fields"]:
                k = f"input_{f['name']}"
                if k in st.session_state:
                    values[f["name"]] = st.session_state[k]
                elif f["name"] not in values:
                    values[f["name"]] = f.get("default")
            st.markdown(f"""
                <div style="margin-bottom: 24px;">
                    <div class="step-title">2. Configuração de Execução</div>
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
            if campos_booleans:
                st.markdown("""
                <div style="font-size: 15px; font-weight: 600; color: #cbd5e1; margin: 28px 0 12px 0; border-top: 1px solid #334155; padding-top: 16px;">
                    ⚙️ Opções & Dependências
                </div>
                """, unsafe_allow_html=True)
                
                col_b1, col_b2 = st.columns(2)
                for idx, field in enumerate(campos_booleans):
                    target_col = col_b1 if idx % 2 == 0 else col_b2
                    with target_col:
                        nome, valor = create_field(field)
                        values[nome] = valor

            erros_etapa_2 = validate_fields(dbt_schema, values)

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
    es_etapa3_activa = st.session_state["etapa_dbt"] == 3
    with st.expander("3. Analise final", expanded=es_etapa3_activa):
        if st.session_state["etapa_dbt"] < 3:
            st.info("🔒 Complete a Etapa 1 , Etapa 2  e clique em 'Continuar' para habilitar esta seção.")
        elif st.session_state["etapa_dbt"] == 3:
            if st.session_state["etapa_dbt"] < 3:
                st.info("🔒 Complete a Etapa 1 e Etapa 2 para habilitar esta seção.")
            else:
                
                st.markdown('<div class="step-title">Revisão e Confirmação</div>', unsafe_allow_html=True)
                st.markdown('<div style="color: #94a3b8; font-size: 14px; margin-bottom: 20px;">Verifique os dados antes de gerar a DAG.</div>', unsafe_allow_html=True)

                dados_finais = {}
                for f in dbt_schema["fields"]:
                    if not campo_visivel(f, values):
                        continue

                    nome_campo = f["name"]
                    tipo = f["type"]
                    
                    # Tomamos el valor directamente del diccionario values
                    valor = values.get(nome_campo)

                    if tipo == "text_list" and isinstance(valor, str):
                        valor = [linha.strip() for linha in valor.splitlines() if linha.strip()]
                    elif tipo in ["date", "time"] and valor is not None:
                        valor = str(valor)
        
                    if valor is not None and valor != "" and valor != [] and valor != {}:
                        dados_finais[nome_campo] = valor

                yaml_dados = dados_finais.copy()

                # 3. Selector de visualización profissional
                opcao_visao = st.radio(
                    "Selecione a forma de visualização:",
                    ["Visão Consolidada", "Estrutura YAML"],
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                st.markdown("<hr style='margin: 10px 0 20px 0; border-color: #334155;'>", unsafe_allow_html=True)

                if opcao_visao == "Visão Consolidada":

                    campos_principais = ["name", "execution_type", "owner"]
                    cols_activas = [c for c in campos_principais if c in dados_finais]
                    
                    if cols_activas:
                        cols = st.columns(len(cols_activas))
                        labels_map = {
                            "name": "NOME DA DAG", 
                            "execution_type": "TIPO DE EXECUÇÃO", 
                            "owner": "PROPRIETÁRIO"
                        }
                        for idx, campo in enumerate(cols_activas):
                            with cols[idx]:
                                color_val = "#38bdf8" if campo == "execution_type" else "#f8fafc"
                                st.markdown(f"""
                                <div style="background-color: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #1e293b; height: 100%;">
                                    <p style="color: #94a3b8; font-size: 11px; margin-bottom: 5px; font-weight: 600;">{labels_map.get(campo, campo.upper())}</p>
                                    <p style="color: {color_val}; font-size: 15px; font-weight: 600; margin: 0;">{dados_finais[campo]}</p>
                                </div>
                                """, unsafe_allow_html=True)
                        st.write("")

                    detalles_map = {
                        "schedule": "Agendamento (Schedule)",
                        "tags": "Tags",
                        "description": "Descrição",
                        "start_date": "Início (Start Date)",
                        "limit_time": "Tempo Limite (Limit Time)",
                        "dbt_env": "Ambiente (Env)"
                    }

                    campos_complejos = ['tabelas_para_checar', 'dbt_run', 'dbt_test', 'dbt_profile', 'qlik_automation', 'pipes','file_generation']
                    campos_ignorados = set(campos_principais + campos_complejos)
                    detalhes_existentes = [
                        k for k, v in dados_finais.items() 
                        if k not in campos_ignorados and not isinstance(v, bool)
                    ]

                    if detalhes_existentes:
                        col_det1, col_det2 = st.columns(2)
                        mitad = (len(detalhes_existentes) + 1) // 2
                        
                        with col_det1:
                            for k in detalhes_existentes[:mitad]:
                                val = dados_finais[k]
                                val_str = ", ".join(str(x) for x in val) if isinstance(val, list) else str(val)
                                label_text = detalles_map.get(k, k.replace('_', ' ').title())
                                st.markdown(f"**{label_text}:** {val_str}")
                        
                        with col_det2:
                            for k in detalhes_existentes[mitad:]:
                                val = dados_finais[k]
                                val_str = ", ".join(str(x) for x in val) if isinstance(val, list) else str(val)
                                label_text = detalles_map.get(k, k.replace('_', ' ').title())
                                st.markdown(f"**{label_text}:** {val_str}")

                    tabelas = dados_finais.get('tabelas_para_checar', [])
                    if tabelas:
                        st.markdown("<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>Tabelas Mapeadas:</div>", unsafe_allow_html=True)
                        tabelas_html = "".join([f"<span style='display: inline-block; background: #1e293b; padding: 4px 10px; margin: 4px 4px 4px 0; border-radius: 4px; font-size: 12px; color: #94a3b8;'>{t}</span>" for t in tabelas])
                        st.markdown(f"<div>{tabelas_html}</div>", unsafe_allow_html=True)

                    for cmd_key in ['dbt_run', 'dbt_test', 'dbt_profile']:
                        if cmd_key in dados_finais:
                            st.markdown(f"<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>{cmd_key.upper().replace('_', ' ')}:</div>", unsafe_allow_html=True)
                            for item in dados_finais[cmd_key]:
                                st.code(f"id: {item.get('id', '')}\ncmd: {item.get('cmd', '')}", language="yaml")
                    
                    if 'qlik_automation' in dados_finais:
                        st.markdown("<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>Qlik Automation:</div>", unsafe_allow_html=True)
                        st.json(dados_finais['qlik_automation'])

                    if 'pipes' in dados_finais:
                        st.markdown("<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>Pipes Configurados:</div>", unsafe_allow_html=True)
                        if isinstance(dados_finais['pipes'], list):
                            for idx, pipe in enumerate(dados_finais['pipes']):
                                st.code(yaml.dump(pipe, sort_keys=False, allow_unicode=True), language="yaml")
                        else:
                            st.json(dados_finais['pipes'])
                    if 'file_generation' in dados_finais:
                        st.markdown("<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>Geração de Arquivos (File Generation):</div>", unsafe_allow_html=True)
                        if isinstance(dados_finais['file_generation'], (dict, list)):
                            st.json(dados_finais['file_generation'])
                        else:
                            st.info(str(dados_finais['file_generation']))

                    bools = {k: v for k, v in dados_finais.items() if isinstance(v, bool)}
                    if bools:
                        st.markdown("<div style='margin-top: 20px; color: #cbd5e1; font-weight: 600;'>Dependências e Parâmetros:</div>", unsafe_allow_html=True)
                        booleans_html = ""
                        for k, v in bools.items():
                            status_str = "Ativo" if v else "Inativo"
                            color = "#4ade80" if v else "#f87171"
                            booleans_html += f"<div style='margin: 4px 0;'><span style='color: {color}; font-weight: 600;'>[{status_str}]</span> <span style='color: #94a3b8; font-size: 14px;'>{k}</span></div>"
                        st.markdown(f"<div>{booleans_html}</div>", unsafe_allow_html=True)

                else:
                    nome_dag = dados_finais["name"]

                    nome_seguro = re.sub(
                                r"[^A-Za-z0-9_.-]+",
                                "_",
                                nome_dag
                            )
                    dados_finais["name"] = f"app_executa_dbt_{nome_seguro}"
                    yaml_string = yaml.dump(dados_finais, sort_keys=False, default_flow_style=False, allow_unicode=True)
                    st.markdown('<div style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">Configuração final compilada:</div>', unsafe_allow_html=True)
                    st.code(yaml_string, language="yaml")

                st.markdown("<hr style='margin: 20px 0; border-color: #334155;'>", unsafe_allow_html=True)
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

                            # --------------------------------
                            # 1. Verificar configs_yaml
                            # --------------------------------

                            configs_existe = verificar_configs_yaml(
                                owner=owner,
                                repo=repo,
                                branch=branch,
                                token=token
                            )

                            if configs_existe:
                                st.info(
                                    "A pasta configs_yaml já existe. "
                                    "O arquivo será salvo nela."
                                )
                            else:
                                st.info(
                                    "A pasta configs_yaml não existe. "
                                    "Ela será criada automaticamente."
                                )

                            # --------------------------------
                            # 2. Nome do arquivo
                            # --------------------------------

                        
                            dados_finais["name"] = f"app_executa_dbt_{nome_seguro}"
                            nome_arquivo = f"dbt_config_{nome_seguro}.yaml"
                            if "tags" in dados_finais:
                                if isinstance(dados_finais["tags"], list):
                                    elementos = dados_finais["tags"]
                                else:
                                    texto_limpio = str(dados_finais["tags"]).replace("[", "").replace("]", "").replace("'", "").replace('"', "")
                                    elementos = [t.strip() for t in texto_limpio.split(",") if t.strip()]
                                dados_finais["tags"] = f"[{','.join(elementos)}]"
                            yaml_string = yaml.dump(
                                dados_finais, 
                                sort_keys=False, 
                                allow_unicode=True)
                            # --------------------------------
                            # 3. Salvar no GitHub
                            # --------------------------------

                            resultado = salvar_yaml_github(
                                yaml_string=yaml_string,
                                owner=owner,
                                repo=repo,
                                branch=branch,
                                nome_arquivo=nome_arquivo,
                                token=token
                            )

                            # --------------------------------
                            # 4. Sucesso
                            # --------------------------------

                            arquivo_url = resultado["content"]["html_url"]
                            st.success(
                                "DAG gerada e enviada ao GitHub com sucesso!"
                            )

                            st.link_button(
                                "Abrir YAML no GitHub",
                                arquivo_url
                            )

                        except Exception as e:
                            st.error(
                                f"Não foi possível enviar o YAML para o GitHub: {e}"
                            )


with aba2:
    
    st.header("Configuração FILE",) 



