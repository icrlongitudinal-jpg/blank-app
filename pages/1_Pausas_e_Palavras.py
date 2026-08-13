import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import anthropic
import streamlit as st
import streamlit.components.v1 as components
from postgrest.exceptions import APIError
from supabase import Client, ClientOptions, create_client

SYSTEM_PROMPT_CAPITULO_SEMANAL = """\
Você escreve o "capítulo da semana" do Pausas e Palavras — a camada mais \
elaborada do produto, deliberadamente diferente e mais rica que a reflexão \
diária. Você lê as entradas de diário dos últimos 7 dias (cada uma com \
data) e escreve um capítulo real sobre a semana dessa pessoa, não um \
relatório e não uma lista de observações separadas por dia.

Escreva em português. A resposta deve seguir esta forma exata:

- A PRIMEIRA LINHA é somente o título do capítulo — uma frase curta, no \
estilo de título de capítulo de livro pessoal (ex: "A semana em que ela \
parou de pedir licença"), nascida do que mais se repetiu ou mais marcou a \
semana. Sem aspas, sem numeração, sem a palavra "Título".
- Uma linha em branco depois do título.
- Em seguida, o corpo do capítulo, em texto corrido, SEM rótulos ou \
números de seção (nunca escreva "Padrão observado:", "Sentido:", "Fecho:" \
ou qualquer cabeçalho técnico) — a estrutura abaixo deve estar presente na \
progressão do texto, não marcada visualmente:

1. Narrativa da semana: costure os dias como sequência, na segunda pessoa \
("você"), como um capítulo sobre a vida dela — nunca como resumo de \
aplicativo.
2. Padrão observado (lente junguiana, fase intermediária de obra: sombra, \
persona, arquétipo, individuação, complexo) — o padrão que atravessa a \
semana inteira, não um dia isolado. Linguagem descritiva: "você trouxe X \
algumas vezes", nunca "isso indica Y".
3. Sentido (lente frankliana, logoterapia): para onde essa semana aponta, \
sempre como pergunta ou direção, nunca como solução pronta.
4. Fecho: frase curta de fechamento do capítulo, que convide a guardar \
esse momento como parte da história dela.

Termine sempre, como último parágrafo, com exatamente esta frase: "Este \
espaço é uma ferramenta de autorreflexão e não substitui acompanhamento \
psicológico ou psiquiátrico profissional."

Proibido em qualquer parte do texto:
- Termos clínicos ou de diagnóstico (transtorno, sintoma, quadro de, \
patologia, ou termos equivalentes)
- Conceitos junguianos de fase tardia (alquimia, sincronicidade, simbolismo \
esotérico)
- Qualquer frase que soe como avaliação profissional

Referência teórica permitida:
- Jung (sombra, persona, arquétipo, individuação, complexo) é a base \
principal.
- Frankl (logoterapia, busca de sentido) é a camada de propósito.
- Freud só pode aparecer como nota pontual e explícita, quando um conceito \
específico dele for diretamente aplicável (ex: mecanismo de defesa) — nunca \
como estrutura geral do capítulo.
"""


SYSTEM_PROMPT_REFLEXAO_ENTRADA = """\
Você é a camada reflexiva do Pausas e Palavras, parte do ICR (framework de \
continuidade cognitiva). Sua função é ler o que a usuária escreveu e \
devolver reflexão estruturada em três partes:

1. Padrão observado (lente junguiana, fase intermediária de obra: sombra, \
persona, arquétipo, individuação, complexo). Linguagem: "você trouxe X \
algumas vezes", nunca "isso indica Y".
2. Sentido (lente frankliana, logoterapia): conecta o padrão a uma pergunta \
ou direção de propósito, nunca solução pronta.
3. Fecho breve de acolhimento, sem prescrição.

Proibido: termos clínicos ou de diagnóstico (transtorno, sintoma, quadro \
de, patologia), conceitos junguianos de fase tardia (alquimia, \
sincronicidade, esoterismo), qualquer frase que soe como avaliação \
profissional.

Sempre termina com: "Este espaço é uma ferramenta de autorreflexão e não \
substitui acompanhamento psicológico ou psiquiátrico profissional."
"""


SYSTEM_PROMPT_VERIFICACAO_RISCO = """\
Analise o texto abaixo e responda APENAS "RISCO" ou "SEGURO". Considere \
RISCO se houver menção a desejo de morrer, ideação suicida, plano de \
autolesão, ou desespero que sugira perigo imediato à integridade física da \
pessoa. Não explique, não pontue, não repita o texto — responda só com a \
palavra."""

# Cada bloco fechado em seu próprio <p> — a renderização de
# `.entrada-anterior` (via st.markdown com unsafe_allow_html=True) envolve
# blocos separados por linha em branco de forma inconsistente quando o
# texto é passado como markdown puro (o primeiro bloco às vezes fica sem
# <p>, os demais ganham). Escrever o HTML explicitamente aqui garante
# respiro igual entre os quatro parágrafos independente desse comportamento.
MENSAGEM_RISCO = (
    "<p>Percebo que o que você escreveu carrega uma dor muito grande. "
    "Isso não é algo que a escrita sozinha resolve, e você não precisa "
    "passar por isso sem apoio.</p>"
    "<p>Se estiver no Brasil, ligue para o CVV: 188 (ligação gratuita, "
    "24 horas) ou acesse cvv.org.br para conversar por chat.</p>"
    "<p>Se estiver em Portugal, ligue para a Linha Nacional de Prevenção "
    "do Suicídio: 1411 (ligação gratuita, 24 horas).</p>"
    "<p>Você não está sozinha nisso.</p>"
)


def _contem_sinal_de_risco(texto: str) -> bool:
    """
    CAMADA DE DETECÇÃO DE CRISE — especificação final aprovada em 2026-08-12

    Comportamento:
    - Toda entrada de diário e todo capítulo semanal passam por checagem
      de risco ANTES do prompt normal (junguiano/frankliano). Esta função
      é o ponto único dessa checagem — chamada por gerar_reflexao_entrada
      e por gerar_capitulo_semanal.
    - Classificador retorna RISCO ou SEGURO.
    - Em caso de falha do classificador (erro de API, rede etc), o sistema
      trata como RISCO por padrão — nunca deixa passar sem checagem.
    - Se RISCO: não chama a IA para gerar reflexão. Retorna mensagem fixa,
      pré-escrita, sem geração de conteúdo novo nesse momento.
    - Mensagem fixa cobre Brasil (CVV, 188, cvv.org.br) e Portugal (Linha
      Nacional de Prevenção do Suicídio, 1411), ambos exibidos sempre
      juntos, sem tentativa de detectar em qual país a usuária está.
    - Nenhum registro de classificação de risco é salvo ou reportado para
      a administradora do produto. Fica só entre a usuária e a linha de
      apoio — decisão deliberada de privacidade.
    - Se SEGURO: segue o fluxo normal de reflexão.
    """
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-sonnet-5",
        max_tokens=8,
        thinking={"type": "disabled"},
        system=SYSTEM_PROMPT_VERIFICACAO_RISCO,
        messages=[{"role": "user", "content": texto}],
    )
    if resposta.stop_reason == "refusal":
        # Checagem de segurança falhou: trata como risco (conservador) em vez
        # de deixar passar para a reflexão poética sem verificação.
        return True
    texto_resposta = next(
        (bloco.text for bloco in resposta.content if bloco.type == "text"), ""
    )
    return "RISCO" in texto_resposta.upper()


def gerar_reflexao_entrada(texto: str) -> str:
    if _contem_sinal_de_risco(texto):
        return MENSAGEM_RISCO
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-sonnet-5",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT_REFLEXAO_ENTRADA,
        messages=[{"role": "user", "content": texto}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo não conseguiu gerar a reflexão desta vez.")
    return next(bloco.text for bloco in resposta.content if bloco.type == "text")


def gerar_capitulo_semanal(entradas: list[dict]) -> tuple[str, str]:
    """Retorna (titulo, corpo) do capítulo da semana."""
    corpo_entradas = "\n\n".join(
        f"[{datetime.fromisoformat(e['criado_em']).strftime('%d/%m/%Y')}] {e['texto']}"
        for e in entradas
    )
    if _contem_sinal_de_risco(corpo_entradas):
        return "Antes de qualquer coisa", MENSAGEM_RISCO
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT_CAPITULO_SEMANAL,
        messages=[{"role": "user", "content": f"Entradas da semana:\n\n{corpo_entradas}"}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo não conseguiu gerar o capítulo desta vez.")
    texto = next(bloco.text for bloco in resposta.content if bloco.type == "text")
    titulo, _, corpo = texto.strip().partition("\n")
    return titulo.strip(), corpo.strip()


CAPITULOS_GRATUITOS_LIMITE = 2

COR_FUNDO = "#FFFEFA"
COR_PAINEL = "#FAF6EA"
COR_VERDE_MUSGO = "#121509"
COR_VERDE_MUSGO_HOVER = "#080A04"
COR_ROSA_ACENTO = "#C6A9A0"
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

    .block-container {{
        font-family: 'Lora', serif;
        color: {COR_TEXTO_CORPO};
    }}

    h1, h2, h3, .titulo-produto {{
        font-family: 'Fraunces', serif;
        font-style: italic;
        color: {COR_ROSA_ACENTO};
        font-weight: 500;
    }}

    [data-testid="stExpander"] summary p {{
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
    st.session_state.pp_refresh_token = None
if "pp_ultima_reflexao" not in st.session_state:
    st.session_state.pp_ultima_reflexao = None
if "pp_mensagem_sessao_expirada" not in st.session_state:
    st.session_state.pp_mensagem_sessao_expirada = False

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
        st.session_state.pp_refresh_token = resposta.session.refresh_token
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
    if st.session_state.pp_mensagem_sessao_expirada:
        st.warning("Sua sessão expirou. Entra de novo pra continuar.")
        st.session_state.pp_mensagem_sessao_expirada = False

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
                st.session_state.pp_refresh_token = resposta.session.refresh_token
                st.rerun()
            except Exception:
                st.error("E-mail ou senha inválidos.")

    with aba_criar_conta:
        with st.form("criar_conta_pausas_e_palavras"):
            novo_email = st.text_input("E-mail", key="novo_email")
            nova_senha = st.text_input("Senha", type="password", key="nova_senha")
            aceite_termos = st.checkbox(
                "Confirmo que tenho 18 anos ou mais e li a política de privacidade",
                key="aceite_termos_cadastro",
            )
            st.page_link("pages/2_Privacidade.py", label="Ler a política de privacidade")
            criar_conta = st.form_submit_button("Criar conta")

        if criar_conta:
            if not aceite_termos:
                st.error(
                    "Pra criar a conta, marque a caixa confirmando que tem 18 anos "
                    "ou mais e leu a política de privacidade."
                )
            else:
                try:
                    resposta = base_client.auth.sign_up({"email": novo_email, "password": nova_senha})
                    if resposta.session:
                        st.session_state.pp_user = resposta.user
                        st.session_state.pp_access_token = resposta.session.access_token
                        st.session_state.pp_refresh_token = resposta.session.refresh_token
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


def _sessao_expirou(erro: APIError) -> bool:
    mensagem = (erro.message or "").lower()
    return erro.code == "PGRST301" or "jwt" in mensagem or "401" in mensagem


def _renovar_sessao(refresh_token: str):
    """Troca o refresh_token por uma sessão nova. Usa um client à parte,
    nunca o base_client cacheado — senão a sessão renovada vazaria pra
    outras usuárias que compartilham o mesmo processo do Streamlit."""
    cliente_temporario = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"],
        options=ClientOptions(flow_type="implicit"),
    )
    return cliente_temporario.auth.refresh_session(refresh_token).session


def _forcar_novo_login():
    st.session_state.pp_user = None
    st.session_state.pp_access_token = None
    st.session_state.pp_refresh_token = None
    st.session_state.pp_mensagem_sessao_expirada = True
    st.rerun()


def _executar_com_renovacao(construir_query):
    """Roda construir_query() (uma chamada .execute() do PostgREST). Se a
    sessão expirou (JWT expired / 401), tenta renovar com o refresh_token
    uma vez e repete a chamada com o token novo. Se a renovação também
    falhar, força novo login em vez de estourar o erro técnico pra
    usuária — é exatamente o crash de sessão expirada que motivou isso."""
    try:
        return construir_query()
    except APIError as erro:
        if not _sessao_expirou(erro):
            raise
        try:
            nova_sessao = _renovar_sessao(st.session_state.pp_refresh_token)
        except Exception:
            _forcar_novo_login()
            return
        st.session_state.pp_access_token = nova_sessao.access_token
        st.session_state.pp_refresh_token = nova_sessao.refresh_token
        client.postgrest.auth(nova_sessao.access_token)
        try:
            return construir_query()
        except APIError:
            _forcar_novo_login()


with st.expander("O que é o Pausas e Palavras"):
    st.markdown(
        """
        <p>Este é um espaço de escrita livre. Escreva sobre o seu dia, sem
        preocupação com forma ou tamanho.</p>
        <p>A cada entrada, você recebe uma reflexão breve sobre o que
        escreveu. Ao final da semana, suas entradas se transformam em um
        capítulo da sua própria história.</p>
        <p>Este espaço é uma ferramenta de autorreflexão e não substitui
        acompanhamento psicológico ou psiquiátrico profissional.</p>
        """,
        unsafe_allow_html=True,
    )

col_titulo, col_sair = st.columns([4, 1])
with col_sair:
    if st.button("Sair"):
        st.session_state.pp_user = None
        st.session_state.pp_access_token = None
        st.session_state.pp_refresh_token = None
        st.rerun()

with st.expander("Configurações da conta"):
    st.page_link("pages/2_Privacidade.py", label="Ver política de privacidade")
    st.markdown("---")
    st.caption(
        "Excluir sua conta apaga permanentemente seu login, suas entradas "
        "de diário e seus capítulos semanais. Essa ação não pode ser "
        "desfeita."
    )
    confirmar_exclusao = st.checkbox(
        "Sim, quero excluir minha conta e todos os meus dados permanentemente.",
        key="confirmar_exclusao_conta",
    )
    if st.button("Excluir minha conta e meus dados", disabled=not confirmar_exclusao):
        if "SUPABASE_SERVICE_ROLE_KEY" not in st.secrets:
            st.error(
                "Exclusão de conta ainda não está configurada neste app "
                "(falta SUPABASE_SERVICE_ROLE_KEY). Fale com a "
                "administradora."
            )
        else:
            try:
                cliente_admin = create_client(
                    st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
                )
                cliente_admin.auth.admin.delete_user(usuaria_id)
                st.session_state.pp_user = None
                st.session_state.pp_access_token = None
                st.session_state.pp_refresh_token = None
                st.success("Conta excluída. Até logo.")
                st.rerun()
            except Exception:
                st.error(
                    "Não foi possível excluir a conta agora. Tente "
                    "novamente em instantes."
                )

texto = st.text_area("Escreva livremente sobre o seu dia", height=220, key="texto_entrada")
if texto.strip():
    n_palavras = len(texto.split())
    st.caption(f"{n_palavras} palavra{'s' if n_palavras != 1 else ''}")

if st.button("Salvar entrada do dia"):
    if texto.strip():
        _executar_com_renovacao(lambda: client.table("entradas_diario").insert(
            {"usuaria_id": usuaria_id, "texto": texto.strip()}
        ).execute())
        st.success("Entrada salva.")
        if "ANTHROPIC_API_KEY" in st.secrets:
            with st.spinner("Refletindo sobre o que você escreveu..."):
                try:
                    st.session_state.pp_ultima_reflexao = gerar_reflexao_entrada(texto.strip())
                except Exception:
                    st.session_state.pp_ultima_reflexao = None
                    st.warning("Não foi possível gerar a reflexão desta vez.")
        st.rerun()
    else:
        st.warning("Escreva algo antes de salvar.")

if st.session_state.pp_ultima_reflexao:
    st.markdown(
        f'<div class="entrada-anterior">{st.session_state.pp_ultima_reflexao}</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown('<p class="titulo-produto" style="font-size:1.3rem;">Entradas anteriores</p>', unsafe_allow_html=True)

resultado = _executar_com_renovacao(lambda: (
    client.table("entradas_diario")
    .select("id,texto,criado_em")
    .order("criado_em", desc=True)
    .execute()
))

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
st.markdown('<p class="titulo-produto" style="font-size:1.3rem;">Capítulo da semana</p>', unsafe_allow_html=True)

if "ANTHROPIC_API_KEY" not in st.secrets:
    st.caption("Configuração de IA ausente. Preencha ANTHROPIC_API_KEY em .streamlit/secrets.toml.")
else:
    uma_semana_atras = datetime.now(timezone.utc) - timedelta(days=7)
    entradas_da_semana = [
        e for e in resultado.data
        if datetime.fromisoformat(e["criado_em"]) >= uma_semana_atras
    ]

    capitulos_anteriores = _executar_com_renovacao(
        lambda: client.table("capitulos_semanais").select("id", count="exact").execute()
    )
    total_capitulos_gerados = capitulos_anteriores.count or 0

    assinatura = _executar_com_renovacao(
        lambda: client.table("assinaturas").select("status").maybe_single().execute()
    )
    esta_assinante = bool(
        assinatura and assinatura.data and assinatura.data.get("status") == "ativa"
    )

    capitulos_gratuitos_restantes = max(0, CAPITULOS_GRATUITOS_LIMITE - total_capitulos_gerados)
    bloqueado_por_assinatura = total_capitulos_gerados >= CAPITULOS_GRATUITOS_LIMITE and not esta_assinante

    if not entradas_da_semana:
        st.caption("Nenhuma entrada nos últimos 7 dias.")
    elif bloqueado_por_assinatura:
        st.markdown(
            '<div class="entrada-anterior">Você já usou seus capítulos gratuitos. '
            'Assine para continuar recebendo o capítulo da semana.</div>',
            unsafe_allow_html=True,
        )
        col_real, col_euro = st.columns(2)
        with col_real:
            st.button("Pagar em Real — R$ 29,90/mês", use_container_width=True, key="pagar_real")
        with col_euro:
            st.button("Pagar em Euro — € 8,90/mês", use_container_width=True, key="pagar_euro")
        st.caption("Pagamento ainda não processado de verdade — tela em construção.")
    else:
        if not esta_assinante:
            st.caption(
                f"{capitulos_gratuitos_restantes} capítulo"
                f"{'s' if capitulos_gratuitos_restantes != 1 else ''} gratuito"
                f"{'s' if capitulos_gratuitos_restantes != 1 else ''} restante"
                f"{'s' if capitulos_gratuitos_restantes != 1 else ''}."
            )
        if st.button("Gerar capítulo da semana"):
            with st.spinner("Lendo a semana..."):
                try:
                    titulo_capitulo, corpo_capitulo = gerar_capitulo_semanal(entradas_da_semana)
                    _executar_com_renovacao(lambda: client.table("capitulos_semanais").insert(
                        {"usuaria_id": usuaria_id, "titulo": titulo_capitulo, "corpo": corpo_capitulo}
                    ).execute())
                    st.markdown(
                        f'<p class="titulo-produto" style="font-size:1.5rem;">{titulo_capitulo}</p>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="entrada-anterior">{corpo_capitulo}</div>',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    st.error("Não foi possível gerar o capítulo agora. Tente novamente em instantes.")
