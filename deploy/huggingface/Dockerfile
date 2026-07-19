# Hugging Face Space (Docker SDK) — Genome Firewall, E. coli bundle with live AMRFinderPlus.
#
# Streamlit Community Cloud cannot install AMRFinderPlus, so the strong E. coli
# backend is hosted here instead. The image bakes in AMRFinderPlus and its reference
# database, clones the public app repo, and launches the Streamlit UI in bundle mode.
FROM mambaorg/micromamba:1.5.10

USER root

# Git (to clone the app) and small runtime utilities.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates procps && \
    rm -rf /var/lib/apt/lists/*

# AMRFinderPlus + a pinned Python interpreter from bioconda / conda-forge.
RUN micromamba install -y -n base -c conda-forge -c bioconda \
        python=3.11 ncbi-amrfinderplus && \
    micromamba clean --all --yes
ENV PATH=/opt/conda/bin:$PATH

# Download the AMRFinderPlus reference database at build time so the running
# container never needs network access to predict.
RUN amrfinder -u

# Application code (public repo) and Python dependencies.
WORKDIR /app
RUN git clone --depth 1 https://github.com/justenm25/HackNation-6th.git .
RUN pip install --no-cache-dir -r genome-firewall/requirements-ecoli.txt

# Hugging Face runs the container as uid 1000; give that user a writable home
# and ownership of the app tree so Streamlit can write its cache.
RUN useradd -m -u 1000 appuser && \
    chown -R 1000:1000 /app /home/appuser
USER 1000
ENV HOME=/home/appuser

# Select the E. coli backend and configure the Streamlit server.
ENV GF_MODEL_BUNDLE=/app/genome-firewall/models/ecoli-bundle \
    GF_AMRFINDER=amrfinder \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

EXPOSE 7860
WORKDIR /app/genome-firewall
CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.port=7860", "--server.address=0.0.0.0"]
