import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode

import anthropic
import streamlit as st
import streamlit.components.v1 as components
from postgrest.exceptions import APIError
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
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


SYSTEM_PROMPT_RELATORIO_MENSAL = """\
Você escreve o "relatório do mês" do Pausas e Palavras — uma síntese mais \
ampla e elaborada que o capítulo semanal, que costura os capítulos \
semanais já gerados ao longo do mês num único relatório, em formato de \
pequeno livro. Você recebe os capítulos semanais do mês (cada um já é \
uma leitura junguiana/frankliana daquela semana) e escreve, a partir \
deles, uma análise de autorreflexão sobre o mês inteiro.

Escreva em português. A resposta deve seguir esta forma exata:

- A PRIMEIRA LINHA é somente o título do relatório — estilo título de \
livro ou capítulo de livro pessoal, nascido do que atravessou o mês \
inteiro. Sem aspas, sem numeração, sem a palavra "Título".
- Uma linha em branco depois do título.
- Em seguida, o corpo do relatório, em texto corrido, SEM rótulos ou \
números de seção (nunca escreva "Padrão do mês:", "Sentido:", "Fecho:" \
ou qualquer cabeçalho técnico) — a estrutura abaixo deve estar presente \
na progressão do texto, não marcada visualmente:

1. Uma abertura breve que situa o leitor: isto é uma análise de \
autorreflexão, embasada em referências consagradas da psicologia (Jung \
e Frankl), escrita a partir do que ela mesma escreveu ao longo do mês \
— não um diagnóstico nem uma avaliação clínica.
2. Arco do mês, na segunda pessoa ("você"): como as semanas se conectam, \
o que se manteve e o que mudou — nunca como lista semana a semana.
3. Padrão do mês (lente junguiana: sombra, persona, arquétipo, \
individuação, complexo) — o que atravessou o mês inteiro, mais amplo do \
que qualquer padrão semanal isolado. Linguagem descritiva, nunca "isso \
indica Y".
4. Sentido do mês (lente frankliana, logoterapia): para onde esse mês \
aponta, sempre como pergunta ou direção, nunca como solução pronta.
5. Fecho: frase de fechamento que convide a guardar esse mês como \
capítulo da história dela.

Termine sempre, como último parágrafo, com exatamente esta frase: "Este \
relatório é uma análise de autorreflexão embasada em referências \
consagradas da psicologia — como Jung e Frankl — e não substitui \
avaliação, diagnóstico ou acompanhamento de um especialista médico ou \
psicológico."

Proibido em qualquer parte do texto:
- Termos clínicos ou de diagnóstico (transtorno, sintoma, quadro de, \
patologia, laudo, CID, ou termos equivalentes)
- Conceitos junguianos de fase tardia (alquimia, sincronicidade, simbolismo \
esotérico)
- Qualquer frase que soe como avaliação profissional real

Referência teórica permitida:
- Jung (sombra, persona, arquétipo, individuação, complexo) é a base \
principal.
- Frankl (logoterapia, busca de sentido) é a camada de propósito.
- Freud só pode aparecer como nota pontual e explícita, quando um conceito \
específico dele for diretamente aplicável — nunca como estrutura geral \
do relatório.
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


SYSTEM_PROMPT_VERIFICACAO_RISCO = """Você é um classificador de risco. Analise o texto e responda APENAS com uma palavra: RISCO ou SEGURO.

Responda RISCO somente se o texto contiver afirmação explícita e em primeira pessoa de:
- vontade de morrer
- intenção de se matar ou tirar a própria vida
- intenção de se machucar ou praticar autolesão
- plano ou método para se machucar

Responda SEGURO em todos os outros casos, incluindo:
- dor, tristeza, luto, raiva, desespero, mesmo que intensos
- ruptura familiar ou relacional
- sofrimento antigo ou trauma já vivido
- relato reflexivo ou narrativo sem intenção declarada
- linguagem metafórica ou vaga
- quando a pessoa diz que está bem, lúcida, estável ou em acompanhamento profissional
- recuperação, relato do dia, desabafo sem intenção de se machucar

Se não houver afirmação explícita de intenção de se machucar ou morrer, responda SEGURO."""

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

# Mensagem fixa de acolhimento — exibida sempre, antes da reflexão diária.
# Substitui o antigo gate condicional pelo classificador de risco no fluxo
# de salvamento de entrada.
MENSAGEM_ACOLHIMENTO = (
    "<p>Obrigada por compartilhar isso aqui. Antes de continuar, quero "
    "lembrar que você não precisa carregar nada sozinha — se em algum "
    "momento sentir que precisa de apoio, esses canais estão disponíveis:</p>"
    "<p>No Brasil: CVV 188 (gratuito, 24h) ou cvv.org.br<br>"
    "Em Portugal: Linha Nacional de Prevenção do Suicídio 1411 "
    "(gratuita, 24h)</p>"
)


def _contem_sinal_de_risco(texto: str) -> bool:
    """
    NOTA (2026-09-01): mantida no código mas NÃO é mais chamada no fluxo de
    salvamento de entrada / reflexão diária — substituída por uma mensagem
    fixa de acolhimento (MENSAGEM_ACOLHIMENTO), exibida sempre. Ainda
    referenciada por gerar_capitulo_semanal e gerar_relatorio_mensal.

    CAMADA DE DETECÇÃO DE CRISE — especificação final aprovada em 2026-08-12

    Comportamento:
    - Toda entrada de diário e todo capítulo semanal passam por checagem
      de risco ANTES do prompt normal (junguiano/frankliano). Esta função
      é o ponto único dessa checagem — chamada por gerar_reflexao_entrada
      e por gerar_capitulo_semanal.
    - Classificador retorna RISCO ou SEGURO.
    - QUALQUER exceção na chamada da API (rede, timeout, erro HTTP,
      resposta malformada, recusa do modelo — sem distinguir tipo) é
      capturada por um try/except amplo e tratada como RISCO. Só cai em
      SEGURO quando a API responde normalmente E o classificador diz
      explicitamente "SEGURO" (correção de 2026-08-16: antes só o
      stop_reason "refusal" caía em RISCO — uma falha de rede, por
      exemplo, subia sem tratamento até a página, que mostrava "não foi
      possível gerar a reflexão desta vez" em vez da mensagem de crise.
      Nunca mais deixar passar sem checagem por falha técnica).
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
    try:
        cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
        resposta = cliente_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8,
            system=SYSTEM_PROMPT_VERIFICACAO_RISCO,
            messages=[{"role": "user", "content": texto}],
        )
        if resposta.stop_reason == "refusal":
            # Checagem de segurança falhou: trata como risco (conservador) em
            # vez de deixar passar para a reflexão poética sem verificação.
            return True
        texto_resposta = next(
            (bloco.text for bloco in resposta.content if bloco.type == "text"), ""
        )
        return texto_resposta.strip().upper().startswith("RISCO")
    except Exception:
        # Qualquer falha na chamada (rede, timeout, erro da API, resposta
        # malformada) é tratada como risco — conservador por padrão, nunca
        # deixa passar sem checagem por causa de um problema técnico.
        return True


def gerar_reflexao_entrada(texto: str) -> str:
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
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
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT_CAPITULO_SEMANAL,
        messages=[{"role": "user", "content": f"Entradas da semana:\n\n{corpo_entradas}"}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo não conseguiu gerar o capítulo desta vez.")
    texto = next(bloco.text for bloco in resposta.content if bloco.type == "text")
    titulo, _, corpo = texto.strip().partition("\n")
    return titulo.strip(), corpo.strip()


def gerar_relatorio_mensal(capitulos: list[dict]) -> tuple[str, str]:
    """Retorna (titulo, corpo) do relatório do mês, a partir dos capítulos
    semanais já gerados naquele mês (não relê as entradas diárias brutas)."""
    corpo_capitulos = "\n\n".join(
        f"[Semana de {datetime.fromisoformat(c['criado_em']).strftime('%d/%m/%Y')}] "
        f"{c['titulo']}\n{c['corpo']}"
        for c in capitulos
    )
    if _contem_sinal_de_risco(corpo_capitulos):
        return "Antes de qualquer coisa", MENSAGEM_RISCO
    cliente_anthropic = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    resposta = cliente_anthropic.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT_RELATORIO_MENSAL,
        messages=[{"role": "user", "content": f"Capítulos semanais do mês:\n\n{corpo_capitulos}"}],
    )
    if resposta.stop_reason == "refusal":
        raise RuntimeError("O modelo não conseguiu gerar o relatório desta vez.")
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

MESES_PT = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

# app.py fica na raiz do repo, então parent (não parent.parent) é a raiz.
DIRETORIO_FONTES_PDF = Path(__file__).resolve().parent / "assets" / "fonts"


@st.cache_resource
def _registrar_fontes_pdf() -> bool:
    """Registra as fontes da identidade visual (Fraunces/Lora, baixadas do
    Google Fonts e commitadas em assets/fonts/) no reportlab, uma única vez
    por processo. Sem isso o PDF cairia numa fonte genérica do sistema."""
    pdfmetrics.registerFont(
        TTFont("Fraunces-Italic", str(DIRETORIO_FONTES_PDF / "Fraunces-Italic.ttf"))
    )
    pdfmetrics.registerFont(TTFont("Lora", str(DIRETORIO_FONTES_PDF / "Lora-Regular.ttf")))
    pdfmetrics.registerFont(
        TTFont("Lora-Italic", str(DIRETORIO_FONTES_PDF / "Lora-Italic.ttf"))
    )
    return True


def _fundo_pagina_pdf(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(HexColor(COR_FUNDO))
    canvas.rect(0, 0, doc.pagesize[0], doc.pagesize[1], stroke=0, fill=1)
    canvas.restoreState()


def gerar_pdf_relatorio_mensal(titulo: str, corpo: str, mes: int, ano: int) -> bytes:
    """Monta o relatório do mês como PDF, com a tipografia da identidade
    visual (Fraunces itálico pro título, Lora pro corpo) embutida no
    arquivo — não depende de fonte instalada em quem for abrir."""
    _registrar_fontes_pdf()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A5,
        topMargin=2.2 * cm,
        bottomMargin=2.2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    estilo_titulo_capa = ParagraphStyle(
        "TituloCapa", fontName="Fraunces-Italic", fontSize=26, leading=32,
        textColor=HexColor(COR_ROSA_ACENTO), alignment=TA_CENTER,
    )
    estilo_subtitulo_capa = ParagraphStyle(
        "SubtituloCapa", fontName="Fraunces-Italic", fontSize=13, leading=18,
        textColor=HexColor(COR_ROSA_ACENTO), alignment=TA_CENTER,
    )
    estilo_mes_capa = ParagraphStyle(
        "MesCapa", fontName="Lora-Italic", fontSize=11, leading=16,
        textColor=HexColor(COR_TEXTO_SECUNDARIO), alignment=TA_CENTER,
    )
    estilo_corpo = ParagraphStyle(
        "Corpo", fontName="Lora", fontSize=10.5, leading=17,
        textColor=HexColor(COR_TEXTO_CORPO), alignment=TA_JUSTIFY,
        spaceAfter=12,
    )
    estilo_disclaimer = ParagraphStyle(
        "Disclaimer", fontName="Lora-Italic", fontSize=8.5, leading=13,
        textColor=HexColor(COR_TEXTO_SECUNDARIO), alignment=TA_JUSTIFY,
        spaceBefore=18,
    )

    story = [
        Spacer(1, 6 * cm),
        Paragraph(titulo, estilo_titulo_capa),
        Spacer(1, 1 * cm),
        Paragraph("Pausas e Palavras", estilo_subtitulo_capa),
        Paragraph(f"{MESES_PT[mes - 1].capitalize()} de {ano}", estilo_mes_capa),
        PageBreak(),
    ]

    paragrafos = [p.strip() for p in corpo.split("\n\n") if p.strip()]
    # O último parágrafo é sempre o disclaimer (frase fixa exigida no
    # system prompt) — renderiza separado, em itálico e menor.
    corpo_paragrafos, disclaimer = paragrafos[:-1], paragrafos[-1]
    for paragrafo in corpo_paragrafos:
        story.append(Paragraph(paragrafo, estilo_corpo))
    story.append(Paragraph(disclaimer, estilo_disclaimer))

    doc.build(story, onFirstPage=_fundo_pagina_pdf, onLaterPages=_fundo_pagina_pdf)
    return buffer.getvalue()


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

def get_base_client() -> Client | None:
    """Cliente Supabase (anon key), isolado por sessão de navegador via
    st.session_state — NÃO usar st.cache_resource aqui.

    Mais abaixo, o client é mutado com o access_token da usuária logada
    (client.postgrest.auth(...) sobrescreve o header Authorization do
    client em si, não uma cópia). st.cache_resource cacheia por
    PROCESSO, compartilhado entre TODAS as sessões concorrentes — em
    produção (Streamlit Cloud), múltiplas usuárias rodam no mesmo
    processo ao mesmo tempo. Um client cacheado por processo faria o
    header de autenticação de uma usuária sobrescrever o de outra
    sempre que as duas tivessem uma chamada em andamento ao mesmo
    tempo — uma usuária podia acabar recebendo dados de outra numa
    corrida entre threads (correção de 2026-08-18, mesma falha
    encontrada e corrigida no Casa da Maria). st.session_state é por
    sessão de navegador — nunca compartilhado entre usuárias — então
    cada uma tem seu próprio client, sem essa corrida.
    """
    if "pp_base_client" not in st.session_state:
        try:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_ANON_KEY"]
        except (FileNotFoundError, KeyError):
            st.session_state.pp_base_client = None
        else:
            st.session_state.pp_base_client = create_client(
                url, key, options=ClientOptions(flow_type="implicit")
            )
    return st.session_state.pp_base_client


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
if "pp_erro_reflexao" not in st.session_state:
    st.session_state.pp_erro_reflexao = None
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

# base_client já é isolado por sessão (get_base_client, acima) — seguro
# mutar o header de auth aqui, não afeta outras usuárias.
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
        capítulo da sua própria história — uma leitura inspirada nas
        ideias de Carl Jung sobre autoconhecimento e nas de Viktor Frankl
        sobre encontrar sentido, mesmo nos dias mais difíceis.</p>
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

if "entrada_key_version" not in st.session_state:
    st.session_state.entrada_key_version = 0

texto = st.text_area(
    "Escreva livremente sobre o seu dia",
    height=220,
    key=f"entrada_texto_{st.session_state.entrada_key_version}"
)
if texto.strip():
    n_palavras = len(texto.split())
    st.caption(f"{n_palavras} palavra{'s' if n_palavras != 1 else ''}")

if st.button("Salvar entrada do dia"):
    if texto.strip():
        _executar_com_renovacao(lambda: client.table("entradas_diario").insert(
            {"usuaria_id": usuaria_id, "texto": texto.strip()}
        ).execute())
        st.success("Entrada salva.")
        st.session_state.pp_ultima_reflexao = None
        st.session_state.pp_erro_reflexao = None
        if "ANTHROPIC_API_KEY" in st.secrets:
            with st.spinner("Refletindo sobre o que você escreveu..."):
                try:
                    st.session_state.pp_ultima_reflexao = gerar_reflexao_entrada(texto.strip())
                except Exception as e:
                    st.session_state.pp_erro_reflexao = repr(e)
        st.session_state.entrada_key_version += 1
        st.rerun()
    else:
        st.warning("Escreva algo antes de salvar.")

if st.session_state.pp_ultima_reflexao or st.session_state.pp_erro_reflexao:
    st.markdown(
        f'<div class="entrada-anterior">{MENSAGEM_ACOLHIMENTO}</div>',
        unsafe_allow_html=True,
    )
if st.session_state.pp_ultima_reflexao:
    st.markdown(
        f'<div class="entrada-anterior">{st.session_state.pp_ultima_reflexao}</div>',
        unsafe_allow_html=True,
    )
elif st.session_state.pp_erro_reflexao:
    st.warning("Não foi possível gerar a reflexão desta vez.")

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

st.markdown("---")
st.markdown('<p class="titulo-produto" style="font-size:1.3rem;">Relatório do mês</p>', unsafe_allow_html=True)

MINIMO_CAPITULOS_RELATORIO_MENSAL = 2

if "ANTHROPIC_API_KEY" not in st.secrets:
    st.caption("Configuração de IA ausente. Preencha ANTHROPIC_API_KEY em .streamlit/secrets.toml.")
elif bloqueado_por_assinatura:
    st.caption("O relatório do mês está incluído na mesma assinatura do capítulo semanal.")
else:
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    capitulos_do_mes_resultado = _executar_com_renovacao(
        lambda: client.table("capitulos_semanais")
        .select("id,titulo,corpo,criado_em")
        .gte("criado_em", inicio_mes.isoformat())
        .order("criado_em")
        .execute()
    )
    capitulos_do_mes = capitulos_do_mes_resultado.data or []

    if len(capitulos_do_mes) < MINIMO_CAPITULOS_RELATORIO_MENSAL:
        st.caption(
            f"Ainda não há capítulos semanais suficientes neste mês "
            f"(mínimo {MINIMO_CAPITULOS_RELATORIO_MENSAL}). Volte depois de "
            f"mais algumas semanas escrevendo."
        )
    else:
        st.caption(
            f"{len(capitulos_do_mes)} capítulos semanais disponíveis "
            f"este mês."
        )
        if st.button("Gerar relatório do mês em PDF"):
            with st.spinner("Lendo o mês inteiro..."):
                try:
                    titulo_relatorio, corpo_relatorio = gerar_relatorio_mensal(capitulos_do_mes)
                    pdf_bytes = gerar_pdf_relatorio_mensal(
                        titulo_relatorio, corpo_relatorio, agora.month, agora.year
                    )
                    st.success("Relatório pronto.")
                    st.download_button(
                        "Baixar relatório do mês (PDF)",
                        data=pdf_bytes,
                        file_name=f"pausas-e-palavras-relatorio-{agora.year}-{agora.month:02d}.pdf",
                        mime="application/pdf",
                    )
                except Exception:
                    st.error("Não foi possível gerar o relatório agora. Tente novamente em instantes.")
