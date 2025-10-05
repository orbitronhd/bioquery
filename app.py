import streamlit as st
import pandas as pd
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import semantic_search
from transformers import pipeline
import os
import nltk
import base64 # New import for encoding the image

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NASA Bioscience Explorer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STYLING FUNCTIONS ---
def local_css(file_name):
    """Loads a local CSS file into the Streamlit app."""
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

@st.cache_data 
def get_base64_of_bin_file(bin_file):
    """Reads a binary file and returns its base64 encoded string."""
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_bg_from_local(file_path):
    """
    Sets the background of the entire app from a local file.
    """
    if os.path.exists(file_path):
        encoded_string = get_base64_of_bin_file(file_path)
        style = f"""
        <style>
        [data-testid="stApp"] > div {{
            background-image: linear-gradient(rgba(14, 17, 23, 0.8), rgba(14, 17, 23, 0.8)), url("data:image/jpg;base64,{encoded_string}");
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}
        </style>
        """
        st.markdown(style, unsafe_allow_html=True)
    else:
        st.warning(f"Background image '{file_path}' not found. Please make sure it's in the same folder as the script.")


# --- NLTK DATA SETUP ---
@st.cache_resource
def setup_nltk():
    """Downloads necessary NLTK data if not already present."""
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

# --- MODEL & DATA LOADING ---
@st.cache_resource
def load_models():
    """Loads the sentence transformer and summarization models."""
    search_model = SentenceTransformer('all-MiniLM-L6-v2')
    summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")
    return search_model, summarizer

@st.cache_data
def load_data():
    """Loads the publication data and pre-computed embeddings."""
    try:
        df = pd.read_csv('publications.csv', encoding='latin-1')
        embeddings = np.load('embeddings.npy')
        embeddings_tensor = torch.from_numpy(embeddings)
        return df, embeddings_tensor
    except FileNotFoundError:
        return None, None

# --- BACKEND FUNCTIONS ---
def search(query, search_model, embeddings_tensor, top_k=10):
    """Performs semantic search."""
    if not query:
        return []
    query_embedding = search_model.encode(query, convert_to_tensor=True)
    hits = semantic_search(query_embedding, embeddings_tensor, top_k=top_k)
    return hits[0]

def get_summary(text, _summarizer):
    """Generates a summary for a given text."""
    if not text or len(text.split()) < 50:
        return "The abstract is too short to generate a meaningful summary."
    summary = _summarizer(text[:1024], max_length=150, min_length=40, do_sample=False)
    return summary[0]['summary_text']


# --- MAIN APPLICATION ---
def main():
    """The main function to run the Streamlit app."""
    setup_nltk()
    local_css("style.css")
    set_bg_from_local("background.jpg") # This now loads your local image for the whole page

    with st.spinner("Loading AI models and data... This may take a moment."):
        search_model, summarizer_pipeline = load_models()
        df, embeddings_tensor = load_data()

    if 'df' not in st.session_state:
        st.session_state.df = df

    if df is None or embeddings_tensor is None:
        st.error("Critical files not found! Please make sure `publications.csv` and `embeddings.npy` are in the same directory.")
        return

    # --- SIDEBAR ---
    st.sidebar.image("Frame 1.png")
    st.sidebar.header("About")
    st.sidebar.markdown("This tool uses AI to help you search and understand NASA's extensive library of bioscience research publications. Enter a topic to find relevant papers and generate quick summaries.")
    st.sidebar.markdown("---")
    st.sidebar.info(f"Loaded {len(df)} publications.")
    st.sidebar.markdown("---")
    st.sidebar.markdown("Built for the NASA Space Apps Challenge.")
    st.sidebar.markdown(f"Kochi, India | 2025-10-05")

    # --- MAIN CONTENT & SEARCH AREA ---
    st.markdown("<h1 style='text-align: center; color: white;'>NASA Bio-Query</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #FAFAFA;'>An AI-powered dashboard to search and summarize NASA's bioscience research.</p>", unsafe_allow_html=True)
    st.write("") 

    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        query = st.text_area("Search Query", "", height=100, placeholder="Search Here", label_visibility="collapsed")
        search_button = st.button("Search for Articles", use_container_width=True)
    
    st.write("")

    # --- SEARCH RESULTS ---
    st.markdown("<h3 style='color: white;'> Search Results</h3>", unsafe_allow_html=True)
    
    if not search_button and 'hits' not in st.session_state:
        st.info("Enter a query and click 'Search' to see results.")

    if search_button:
        with st.spinner("Searching through publications..."):
            hits = search(query, search_model, embeddings_tensor)
            st.session_state.hits = hits
    
    if 'hits' in st.session_state:
        if st.session_state.hits:
            st.success(f"Found {len(st.session_state.hits)} relevant results for your query.")
            for hit in st.session_state.hits:
                paper_index = hit['corpus_id']
                paper_score = hit['score']
                paper_data = df.iloc[paper_index]
                
                with st.expander(f"**{paper_data['Title']}** (Relevance Score: {paper_score:.2f})"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**👨‍🚀 Authors:** {paper_data.get('Authors', 'N/A')}")
                    with col2:
                        st.markdown(f"**🗓️ Year:** {paper_data.get('Year', 'N/A')}")
                    
                    st.subheader("Abstract")
                    st.write(paper_data['Abstract'])

                    summary_button_key = f"summary_{paper_index}"
                    if st.button("Generate AI Summary", key=summary_button_key):
                        with st.spinner("Generating summary with AI..."):
                            summary = get_summary(paper_data['Abstract'], summarizer_pipeline)
                            st.info(f"**AI Summary:** {summary}")
        else:
            st.warning("No relevant results found. Please try a different query.")

if __name__ == "__main__":
    main()