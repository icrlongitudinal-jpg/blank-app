import streamlit as st

LABELS = {
    "pt": {
        "app_title": "ICR",
        "language": "Idioma",
        "pinned": "Conversas fixadas",
        "no_pinned": "Nenhuma conversa fixada ainda.",
        "pin_current": "Fixar esta conversa",
        "chat_placeholder": "Escreva aqui...",
        "greeting": "Oi, eu sou o ICR. Estou aqui para conversar com você.",
    },
    "en": {
        "app_title": "ICR",
        "language": "Language",
        "pinned": "Pinned conversations",
        "no_pinned": "No pinned conversations yet.",
        "pin_current": "Pin this conversation",
        "chat_placeholder": "Type here...",
        "greeting": "Hi, I'm ICR. I'm here to talk with you.",
    },
    "es": {
        "app_title": "ICR",
        "language": "Idioma",
        "pinned": "Conversaciones fijadas",
        "no_pinned": "Todavía no hay conversaciones fijadas.",
        "pin_current": "Fijar esta conversación",
        "chat_placeholder": "Escribe aquí...",
        "greeting": "Hola, soy ICR. Estoy aquí para conversar contigo.",
    },
}

st.set_page_config(page_title="ICR", page_icon="💬", layout="centered")

if "language" not in st.session_state:
    st.session_state.language = "pt"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pinned_conversations" not in st.session_state:
    st.session_state.pinned_conversations = []

t = LABELS[st.session_state.language]

with st.sidebar:
    st.session_state.language = st.selectbox(
        t["language"], options=list(LABELS.keys()),
        format_func=lambda code: {"pt": "Português", "en": "English", "es": "Español"}[code],
        index=list(LABELS.keys()).index(st.session_state.language),
    )
    t = LABELS[st.session_state.language]

    st.divider()
    st.subheader(t["pinned"])
    if not st.session_state.pinned_conversations:
        st.caption(t["no_pinned"])
    else:
        for title in st.session_state.pinned_conversations:
            st.button(title, use_container_width=True, disabled=True)

st.title(t["app_title"])

if not st.session_state.messages:
    st.chat_message("assistant").write(t["greeting"])

for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

user_input = st.chat_input(t["chat_placeholder"])
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
