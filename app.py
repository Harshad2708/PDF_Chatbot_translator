import streamlit as st
from streamlit_chat import message
from langchain.chains import ConversationalRetrievalChain
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import CTransformers
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import os
from dotenv import load_dotenv
import tempfile
import fitz 
from fpdf import FPDF
from googletrans import Translator
import warnings
import torch

warnings.filterwarnings("ignore", category=FutureWarning)
load_dotenv()

# ---------------- Session State ----------------
def initialize_session_state():
    if 'history' not in st.session_state:
        st.session_state['history'] = []
    if 'generated' not in st.session_state:
        st.session_state['generated'] = ["Hello! Ask me anything about 🤗"]
    if 'past' not in st.session_state:
        st.session_state['past'] = ["Hey! 👋"]

# ---------------- Chat Function ----------------
def conversation_chat(query, chain, history):
    result = chain({"question": query, "chat_history": history})
    history.append((query, result["answer"]))
    return result["answer"]

def display_chat_history(chain):
    reply_container = st.container()
    container = st.container()

    with container:
        with st.form(key='my_form', clear_on_submit=True):
            user_input = st.text_input("Question:", placeholder="Ask about your Documents", key='input')
            submit_button = st.form_submit_button(label='Send')

        if submit_button and user_input:
            with st.spinner('Generating response...'):
                output = conversation_chat(user_input, chain, st.session_state['history'])

            st.session_state['past'].append(user_input)
            st.session_state['generated'].append(output)

    if st.session_state['generated']:
        with reply_container:
            for i in range(len(st.session_state['generated'])):
                message(st.session_state["past"][i], is_user=True, key=str(i) + '_user', avatar_style="fun-emoji")
                message(st.session_state['generated'][i], key=str(i), avatar_style="bottts")

# ---------------- LLM Chain ----------------
def create_conversational_chain(vector_store):
    # detect device
    device = "cuda" 

    llm = CTransformers(
        model=r"llama-2-7b-chat.ggmlv3.q4_0.bin",  
        model_type="llama",  
        device=device,
        streaming=True, 
        callbacks=[StreamingStdOutCallbackHandler()],
        config={
            'max_new_tokens': 512,
            'temperature': 0.3,
            'context_length': 2048
        }  
    )

    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm, 
        chain_type='stuff',
        retriever=vector_store.as_retriever(search_kwargs={"k": 3}),
        memory=memory
    )
    return chain

# ---------------- PDF Extraction ----------------
def extract_text_from_pdf(pdf_path):
    document = ""
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            document += page.get_text()
    return document

def create_text_file(content, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

# ---------------- Main App ----------------
def main():
    initialize_session_state()
    st.set_page_config(layout="wide", page_title="Multi-Docs ChatBot and PDF Translator :books: 🤖")
    
    st.sidebar.title("Document Processing")
    option = st.sidebar.selectbox("Choose an option", ("ChatBot", "PDF Translator"))
    uploaded_files = st.sidebar.file_uploader("Upload files", accept_multiple_files=True)

    document_text = ""  

    if uploaded_files:
        text = []
        for file in uploaded_files:
            file_extension = os.path.splitext(file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name

            loader = None
            if file_extension == ".pdf":
                loader = PyPDFLoader(temp_file_path)
                document_text = extract_text_from_pdf(temp_file_path) 
            elif file_extension in [".docx", ".doc"]:
                loader = Docx2txtLoader(temp_file_path)
            elif file_extension == ".txt":
                loader = TextLoader(temp_file_path)

            if loader:
                text.extend(loader.load())

            os.remove(temp_file_path)

        if option == "ChatBot":
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,  # SAFE for embeddings
                chunk_overlap=50
            )
            text_chunks = text_splitter.split_documents(text)

            embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2", 
                model_kwargs={'device': 'cpu'}
            )

            vector_store = FAISS.from_documents(text_chunks, embedding=embeddings)

            chain = create_conversational_chain(vector_store)

            display_chat_history(chain)

        elif option == "PDF Translator":
            st.header("Translate Document")
            languages = {
                "English": "en", "Hindi": "hi", "Marathi": "mr", "Bengali": "bn", "Telugu": "te",
                "Tamil": "ta", "Urdu": "ur", "Gujarati": "gu", "Malayalam": "ml", "Kannada": "kn", 
                "Odia": "or", "Punjabi": "pa", "Nepali": "ne"
            }

            target_language = st.selectbox("Select target language", list(languages.keys()))
            if st.button("Translate"):
                target_lang_code = languages[target_language]
                translator = Translator()
                translated_text = translator.translate(document_text, dest=target_lang_code).text
                st.write(translated_text)
 
                output_text_path = "translated_text.txt"
                create_text_file(translated_text, output_text_path)
                
                with open(output_text_path, "rb") as f:
                    st.download_button("Download Translated Text", f, file_name=output_text_path, mime="text/plain")

if __name__ == "__main__":
    main()  
