import streamlit as st 
import yaml

#------------- FUNÇÕES

def load_schema(caminho):

    with open(caminho,"r",encoding="utf-8")as arquivo:

        return yaml.safe_load(arquivo)

def create_field(field):

    nome = field["name"]

    label = field["label"]

    tipo = field["type"]

    default = field.get("default")

    description = field.get("description")

    if tipo == "text":

        valor = st.text_input(
            label,
            value=default or "",
            help=description)
        
    elif tipo == "text_list":
        texto = st.text_area(
            label,
            help=description,
            placeholder="Digite um item por linha")
        valor = [
            linha.strip()
            for linha in texto.splitlines()
            if linha.strip()]
        
    elif tipo == "select":
        options = field.get("options", [])
        index = 0
        if default in options:
            index = options.index(default)
        valor = st.selectbox(
            label,
            options,
            index=index,
            help=description)
    elif tipo == "number":
        minimo = field.get("min")
        maximo = field.get("max")
        default = field.get("default")

        if default is None:
            default = minimo if minimo is not None else 0

        valor = st.number_input(
            label,
            min_value=minimo,
            max_value=maximo,
            value=default,
            help=description)

    elif tipo == "boolean":
        valor = st.checkbox(
            label,
            value=default if default is not None else False,
            help=description)

    elif tipo == "date":
        valor = st.date_input(
            label,
            help=description)

    elif tipo == "time":
        valor = st.time_input(
            label,
            help=description)
    elif tipo == "object":
        valor = {}
        campos = field.get("fields", [])
        st.markdown(f"**{label}**")
        for subfield in campos:
            sub_nome, sub_valor = create_field(subfield)
            valor[sub_nome] = sub_valor
    elif tipo == "object_list":
        valor = []
        st.markdown(f"**{label}**")
        item_fields = field.get("item_fields", [])
        quantidade = st.number_input(
            f"Quantidade de itens em {label}",
            min_value=0,
            value=1,
            step=1)
        for i in range(quantidade):
            st.markdown(f"### Item {i + 1}")
            item = {}
            for subfield in item_fields:
                sub_nome, sub_valor = create_field(subfield)
                item[sub_nome] = sub_valor
            valor.append(item)
    elif tipo == "command_list":
        valor = []

        st.markdown(f"### **{label}**")

        quantidade = st.number_input(
            f"Quantidade de comandos em {label}",
            min_value=0,
            value=1,
            step=1
        )

        for i in range(quantidade):

            st.markdown(f" Comando {i + 1}")

            command_id = st.text_input(
                "id",
                key=f"{nome}_id_{i}"
            )

            command = st.text_area(
                "cmd",
                key=f"{nome}_cmd_{i}"
            )

            valor.append({
                "id": command_id,
                "cmd": command
            })
    else:
        st.warning(
            f"Tipo de campo não suportado: {tipo}")
        valor = None

    return nome, valor

def validate_fields(schema,values):

    erros = []

    for field in schema["fields"]:

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

    <h1 style='margin-bottom:0;'>Factory Configurator</h1>
    <p style='color: #64748b; font-size:16px;'>
    Crie, valide e gere configurações para DBT Factory e File Factory
    </p>""", unsafe_allow_html=True)

#-------------- FRONT

with st.sidebar:
    st.markdown("## ⚙️ Configuração")

aba1 , aba2 = st.tabs(["dbt_factory","file_factory"])

#------------------- dbt_facotry

with aba1:
    st.header("Configuração DBT",)
    values = {}
    #--------- step 1
    for field in dbt_schema["fields"]:
        if field["name"] not in campos_basicos:
            continue
        if not campo_visivel(field,values):
            continue

        nome, valor =  create_field(field)
        values[nome]=valor
    st.session_state["dbt_values"] = values
    if "etapa_dbt" not in st.session_state:
            st.session_state["etapa_dbt"] = 1

    erros = validate_fields(dbt_schema,values)

    if erros:
        for erro in erros:
            st.error(erro)
    else:
        st.success(
            "Configuração válida!")
    continuar = st.button(
        "Continuar →",disabled=len(erros) > 0)
    
    if continuar:
        st.session_state["etapa_dbt"] = 2
    #--------- step 2
    if st.session_state["etapa_dbt"] == 2:
        tipo_execucao = values.get("execution_type", "")
        st.header("Configuração execution_type")
        st.subheader(f"Execução: {tipo_execucao}")
        for field in dbt_schema["fields"]:
            if field["name"] in campos_basicos:
                continue
            if not campo_visivel(field, values):
                continue

            nome, valor = create_field(field)

            values[nome] = valor



with aba2:
    st.header("Configuração FILE",) 



