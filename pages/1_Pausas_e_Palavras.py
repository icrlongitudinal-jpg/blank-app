import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import anthropic
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client, ClientOptions, create_client

SYSTEM_PROMPT_RELATORIO_SEMANAL = """\
Você gera um relatório psicológico semanal breve a partir de entradas de \
diário pessoal de uma usuária. Escreva em português. Não inclua título, \
saudação, nem nenhum texto fora das três partes abaixo, nesta ordem exata:

1. Padrão observado (lente junguiana, fase intermediária): identifique \
repetições, temas recorrentes, ou possíveis sombras ou arquétipos que \
aparecem no que a usuária escreveu ao longo da semana. Use linguagem \
descritiva, nunca avaliativa — por exemplo "você trouxe X algumas vezes \
essa semana". Nunca use frases como "isso indica Y" ou qualquer formulação \
que soe como diagnóstico ou avaliação.

2. Sentido (lente frankliana): conecte o padrão observado a uma pergunta ou \
direção de propósito. Não ofereça solução pronta — apenas uma reflexão que \
ajude a pessoa a pensar para onde aquilo aponta.

3. Fecho: uma frase breve de acolhimento, sem prescrição.

Proibido em qualquer parte do texto:
- Termos clínicos ou de diagnóstico (transtorno, sintoma, quadro de, \
patologia, ou termos equivalentes)
- Conceitos junguianos de fase tardia (alquimia, sincronicidade, simbolismo \
esotérico)
- Qualquer frase que soe como avaliação profissional

Referência teórica permitida:
- Jung (sombra, persona, arquétipo, individuação, complexo) é a base \
principal.
- Frankl (logoterapia, busca de sentido) é a camada de propósito, usada na \
parte 2.
- Freud só pode aparecer como nota pontual e explícita, quando um conceito \
específico dele for diretamente aplicável (ex: mecanismo de defesa) — nunca \
como estrutura geral do relatório.
"""


def gerar_relatorio_semanal(entradas: list[dict]) -> str:
    corpo = "\n\n".join(
        f"[{datetime.fromisoformat(e['criado_em']).strftime('%d/%m/%Y')}] {e['texto']}"
        for e in entradas
    )
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT_RELATORIO_SEMANAL,
        messages=[{"role": "user", "content": f"Entradas da semana:\n\n{corpo}"}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo não conseguiu gerar o relatório desta vez.")
    return next(bloco.text for bloco in resposta.content if bloco.type == "text")

COR_FUNDO = "#FFFEFA"
COR_PAINEL = "#FAF6EA"
COR_VERDE_MUSGO = "#121509"
COR_VERDE_MUSGO_HOVER = "#080A04"
COR_MUSGO_VEIL = "rgba(18,21,9,0.20)"
COR_ROSA_ACENTO = "#C6A9A0"
COR_ROSA_VEIL = "rgba(198,169,160,0.20)"
COR_TEXTO_CORPO = "#5A3E3E"
COR_TEXTO_SECUNDARIO = "#8A6B64"

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
        background: {COR_MUSGO_VEIL};
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
        background: {COR_ROSA_VEIL};
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
        color: {COR_ROSA_ACENTO};
        font-weight: 500;
    }}

    p, span, div, label, textarea, input {{
        font-family: 'Lora', serif;
    }}

    textarea {{
        background-color: {COR_PAINEL} !important;
        color: {COR_TEXTO_CORPO} !important;
        border: 1px solid {COR_ROSA_ACENTO} !important;
        border-radius: 6px !important;
    }}

    .stButton > button, [data-testid="stLinkButton"] a, [data-testid="stFormSubmitButton"] button {{
        background-color: {COR_VERDE_MUSGO} !important;
        color: {COR_FUNDO} !important;
        border: none !important;
        border-radius: 6px;
        font-family: 'Lora', serif;
    }}
    .stButton > button:hover, [data-testid="stLinkButton"] a:hover, [data-testid="stFormSubmitButton"] button:hover {{
        background-color: {COR_VERDE_MUSGO_HOVER} !important;
        color: {COR_FUNDO} !important;
    }}

    .entrada-anterior {{
        background-color: {COR_PAINEL};
        border-left: 3px solid {COR_ROSA_ACENTO};
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        border-radius: 4px;
        color: {COR_TEXTO_CORPO};
    }}
    .entrada-data {{
        font-family: 'Fraunces', serif;
        font-style: italic;
        color: {COR_ROSA_ACENTO};
        font-size: 0.85rem;
    }}

    [data-testid="stCaptionContainer"], small {{
        color: {COR_TEXTO_SECUNDARIO} !important;
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
    return create_client(url, key, options=ClientOptions(flow_type="implicit"))


def google_oauth_url(app_url: str) -> str:
    params = urlencode({"provider": "google", "redirect_to": app_url})
    return f"{st.secrets['SUPABASE_URL']}/auth/v1/authorize?{params}"


# O OAuth do Supabase devolve o token no fragmento da URL (#access_token=...),
# que o servidor Python não enxerga. Esse script (rodando no navegador, dentro
# do iframe do componente — por isso usa window.top) move o token do fragmento
# para a query string e recarrega, aí sim visível para st.query_params.
components.html(
    """
    <script>
    (function() {
        const hash = window.top.location.hash;
        if (hash && hash.includes('access_token')) {
            const params = new URLSearchParams(hash.substring(1));
            const accessToken = params.get('access_token');
            const refreshToken = params.get('refresh_token');
            if (accessToken && refreshToken) {
                const url = new URL(window.top.location.href);
                url.hash = '';
                url.searchParams.set('access_token', accessToken);
                url.searchParams.set('refresh_token', refreshToken);
                window.top.location.replace(url.toString());
            }
        }
    })();
    </script>
    """,
    height=0,
)

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

qp = st.query_params
if "access_token" in qp and "refresh_token" in qp and not st.session_state.pp_user:
    try:
        resposta = base_client.auth.set_session(qp["access_token"], qp["refresh_token"])
        st.session_state.pp_user = resposta.user
        st.session_state.pp_access_token = resposta.session.access_token
    except Exception:
        st.error("Não foi possível completar o login com Google.")
    st.query_params.clear()
    limpo = json.dumps(st.secrets.get("APP_URL", ""))
    components.html(
        f"<script>window.top.history.replaceState(null, '', {limpo});</script>",
        height=0,
    )
    st.rerun()

if not st.session_state.pp_user:
    if "APP_URL" in st.secrets:
        st.link_button("Entrar com Google", google_oauth_url(st.secrets["APP_URL"]), use_container_width=True)
        st.caption("ou entre com e-mail e senha")

    aba_entrar, aba_criar_conta = st.tabs(["Entrar", "Criar conta"])

    with aba_entrar:
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

    with aba_criar_conta:
        with st.form("criar_conta_pausas_e_palavras"):
            novo_email = st.text_input("E-mail", key="novo_email")
            nova_senha = st.text_input("Senha", type="password", key="nova_senha")
            criar_conta = st.form_submit_button("Criar conta")

        if criar_conta:
            try:
                resposta = base_client.auth.sign_up({"email": novo_email, "password": nova_senha})
                if resposta.session:
                    st.session_state.pp_user = resposta.user
                    st.session_state.pp_access_token = resposta.session.access_token
                    st.rerun()
                else:
                    st.success("Conta criada. Confirme o e-mail (se solicitado) e entre na aba \"Entrar\".")
            except Exception as erro:
                st.error(f"Não foi possível criar a conta: {erro}")
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

st.markdown("---")
st.markdown('<p class="titulo-produto" style="font-size:1.3rem;">Relatório da semana</p>', unsafe_allow_html=True)

if "ANTHROPIC_API_KEY" not in st.secrets:
    st.caption("Configuração de IA ausente. Preencha ANTHROPIC_API_KEY em .streamlit/secrets.toml.")
else:
    uma_semana_atras = datetime.now(timezone.utc) - timedelta(days=7)
    entradas_da_semana = [
        e for e in resultado.data
        if datetime.fromisoformat(e["criado_em"]) >= uma_semana_atras
    ]

    if not entradas_da_semana:
        st.caption("Nenhuma entrada nos últimos 7 dias.")
    elif st.button("Gerar relatório da semana"):
        with st.spinner("Lendo a semana..."):
            try:
                texto_relatorio = gerar_relatorio_semanal(entradas_da_semana)
                st.markdown(
                    f'<div class="entrada-anterior">{texto_relatorio}</div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                st.error("Não foi possível gerar o relatório agora. Tente novamente em instantes.")
