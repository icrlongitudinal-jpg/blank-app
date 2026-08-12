from datetime import datetime

import streamlit as st
from supabase import Client, create_client

# TODO(usuária): hex exato do "rosa antigo/nude" de acento não foi enviado ainda.
# Placeholder abaixo — trocar assim que o valor exato chegar.
COR_FUNDO = "#FFFEFA"
COR_PAINEL = "#FAF6EA"
COR_VERDE_MUSGO = "#121509"
COR_VERDE_MUSGO_HOVER = "#080A04"
COR_ACENTO_ROSA_PLACEHOLDER = "#C9A0A6"
COR_TEXTO_CORPO = "#5A3E3E"

FONT_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@"
    "0,9..144,300;0,9..144,400;0,9..144,500;1,9..144,400"
    "&family=Lora:ital,wght@0,400;0,500;1,400;1,500&display=swap"
)

st.set_page_config(page_title="Pausas e Palavras", page_icon="🌿", layout="centered")

st.markdown(
    f"""
    <style>
    @import url('{FONT_IMPORT_URL}');

    [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
        background-color: {COR_FUNDO};
    }}

    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: fixed;
        top: -10%;
        right: -10%;
        width: 40vw;
        height: 40vw;
        background: {COR_VERDE_MUSGO};
        opacity: 0.06;
        border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
        z-index: 0;
        pointer-events: none;
    }}

    [data-testid="stAppViewContainer"]::after {{
        content: "";
        position: fixed;
        bottom: -15%;
        left: -10%;
        width: 35vw;
        height: 35vw;
        background: {COR_ACENTO_ROSA_PLACEHOLDER};
        opacity: 0.08;
        border-radius: 40% 60% 70% 30% / 40% 70% 30% 60%;
        z-index: 0;
        pointer-events: none;
    }}

    .block-container {{
        position: relative;
        z-index: 1;
        font-family: 'Lora', serif;
        color: {COR_TEXTO_CORPO};
    }}

    h1, h2, h3, .titulo-produto {{
        font-family: 'Fraunces', serif;
        font-style: italic;
        color: {COR_ACENTO_ROSA_PLACEHOLDER};
        font-weight: 500;
    }}

    p, span, div, label, textarea, input {{
        font-family: 'Lora', serif;
    }}

    textarea {{
        background-color: {COR_PAINEL} !important;
        color: {COR_TEXTO_CORPO} !important;
        border: 1px solid {COR_ACENTO_ROSA_PLACEHOLDER} !important;
        border-radius: 6px !important;
    }}

    .stButton > button {{
        background-color: {COR_VERDE_MUSGO};
        color: {COR_FUNDO};
        border: none;
        border-radius: 6px;
        font-family: 'Lora', serif;
    }}
    .stButton > button:hover {{
        background-color: {COR_VERDE_MUSGO_HOVER};
        color: {COR_FUNDO};
    }}

    .entrada-anterior {{
        background-color: {COR_PAINEL};
        border-left: 3px solid {COR_ACENTO_ROSA_PLACEHOLDER};
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        border-radius: 4px;
        color: {COR_TEXTO_CORPO};
    }}
    .entrada-data {{
        font-family: 'Fraunces', serif;
        font-style: italic;
        color: {COR_ACENTO_ROSA_PLACEHOLDER};
        font-size: 0.85rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_base_client() -> Client | None:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except (FileNotFoundError, KeyError):
        return None
    return create_client(url, key)


if "pp_user" not in st.session_state:
    st.session_state.pp_user = None
    st.session_state.pp_access_token = None

st.markdown('<p class="titulo-produto" style="font-size:2rem;">Pausas e Palavras</p>', unsafe_allow_html=True)

base_client = get_base_client()
if base_client is None:
    st.error(
        "Configuração do Supabase ausente. Preencha SUPABASE_URL e "
        "SUPABASE_ANON_KEY em .streamlit/secrets.toml (veja secrets.toml.example)."
    )
    st.stop()

if not st.session_state.pp_user:
    with st.form("login_pausas_e_palavras"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        try:
            resposta = base_client.auth.sign_in_with_password({"email": email, "password": senha})
            st.session_state.pp_user = resposta.user
            st.session_state.pp_access_token = resposta.session.access_token
            st.rerun()
        except Exception:
            st.error("E-mail ou senha inválidos.")
    st.stop()

# Cliente autenticado como a usuária logada, isolado nesta sessão de navegador
# (não usar st.cache_resource aqui — vazaria o token entre usuárias).
client = base_client
client.postgrest.auth(st.session_state.pp_access_token)
usuaria_id = st.session_state.pp_user.id

col_titulo, col_sair = st.columns([4, 1])
with col_sair:
    if st.button("Sair"):
        st.session_state.pp_user = None
        st.session_state.pp_access_token = None
        st.rerun()

texto = st.text_area("Escreva livremente sobre o seu dia", height=220, key="texto_entrada")
if texto.strip():
    n_palavras = len(texto.split())
    st.caption(f"{n_palavras} palavra{'s' if n_palavras != 1 else ''}")

if st.button("Salvar entrada do dia"):
    if texto.strip():
        client.table("entradas_diario").insert(
            {"usuaria_id": usuaria_id, "texto": texto.strip()}
        ).execute()
        st.success("Entrada salva.")
        st.rerun()
    else:
        st.warning("Escreva algo antes de salvar.")

st.markdown("---")
st.markdown('<p class="titulo-produto" style="font-size:1.3rem;">Entradas anteriores</p>', unsafe_allow_html=True)

resultado = (
    client.table("entradas_diario")
    .select("id,texto,criado_em")
    .order("criado_em", desc=True)
    .execute()
)

if not resultado.data:
    st.caption("Nenhuma entrada ainda.")
else:
    for entrada in resultado.data:
        data_formatada = datetime.fromisoformat(entrada["criado_em"]).strftime("%d/%m/%Y")
        trecho = entrada["texto"][:140] + ("…" if len(entrada["texto"]) > 140 else "")
        st.markdown(
            f'<div class="entrada-anterior"><div class="entrada-data">{data_formatada}</div>{trecho}</div>',
            unsafe_allow_html=True,
        )
