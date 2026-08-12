import streamlit as st

COR_FUNDO = "#FFFEFA"
COR_PAINEL = "#FAF6EA"
COR_VERDE_MUSGO = "#121509"
COR_ROSA_ACENTO = "#C6A9A0"
COR_TEXTO_CORPO = "#5A3E3E"
COR_TEXTO_SECUNDARIO = "#8A6B64"

FONT_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@"
    "0,9..144,300;0,9..144,400;0,9..144,500;1,9..144,400"
    "&family=Lora:ital,wght@0,400;0,500;1,400;1,500&display=swap"
)

st.set_page_config(page_title="Privacidade — Pausas e Palavras", page_icon="🌿", layout="centered")

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
    .bloco-privacidade {{
        background-color: {COR_PAINEL};
        border-left: 3px solid {COR_ROSA_ACENTO};
        padding: 0.9rem 1.1rem;
        margin-bottom: 1rem;
        border-radius: 4px;
        color: {COR_TEXTO_CORPO};
    }}
    .bloco-privacidade h3 {{
        margin-top: 0;
        font-size: 1.05rem;
    }}
    [data-testid="stCaptionContainer"], small {{
        color: {COR_TEXTO_SECUNDARIO} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="titulo-produto" style="font-size:2rem;">Privacidade</p>', unsafe_allow_html=True)
st.caption("O que guardamos, por quanto tempo, e como pedir para apagar tudo.")

st.markdown(
    """
    <div class="bloco-privacidade">
    <h3>O que é guardado</h3>
    <p>O texto de cada entrada de diário que você escreve, os capítulos
    semanais gerados a partir delas, e o e-mail que você usou para criar
    a conta. Nada além disso.</p>
    </div>

    <div class="bloco-privacidade">
    <h3>Por quanto tempo</h3>
    <p>Enquanto sua conta existir. Não apagamos entradas antigas
    automaticamente — elas ficam disponíveis pra você reler quando
    quiser, até você decidir excluir a conta.</p>
    </div>

    <div class="bloco-privacidade">
    <h3>Quem acessa o que você escreve</h3>
    <p>Só você, através do seu login. O sistema é construído para que
    nenhuma outra usuária consiga ver suas entradas. A equipe técnica não
    lê o conteúdo das entradas no uso normal do produto — só teria acesso
    ao banco de dados em uma situação técnica excepcional (ex: correção
    de um erro), nunca como parte do funcionamento normal.</p>
    <p>O texto que você escreve é enviado à API da Anthropic (Claude)
    só no momento de gerar a reflexão ou o capítulo da semana — é assim
    que a resposta é gerada. Fora desse processamento pontual, o texto
    não é compartilhado com mais ninguém.</p>
    </div>

    <div class="bloco-privacidade">
    <h3>Como pedir para apagar tudo</h3>
    <p>Dentro do app, em "Configurações da conta", tem o botão
    <strong>"Excluir minha conta e meus dados"</strong>. Ele apaga sua
    conta de login e todas as suas entradas e capítulos, de forma
    permanente — não é possível desfazer.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
