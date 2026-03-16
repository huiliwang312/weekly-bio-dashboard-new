# ============================================================================
#  Weekly Bio Dashboard — Configuration
# ============================================================================
#
#  HOW TO CUSTOMIZE FOR YOUR RESEARCH
#  -----------------------------------
#  This file is the ONLY file you need to edit to tailor the dashboard to
#  your own research interests. Everything else (app.py, scoring.py, etc.)
#  reads from here automatically.
#
#  Step 1: Edit JOURNALS / JOURNAL_ISSN — pick the journals you follow.
#  Step 2: Edit CORE_KEYWORDS — define keyword categories that matter to you.
#          Each category becomes a "tag" on matched papers and feeds into scoring.
#  Step 3: Edit TECH_KEYS / BIO_KEYS — assign your categories to Tech vs Bio
#          buckets so the Must-read list can split them.
#  Step 4: Edit the two FOCUS_*_KEYS lists — these power the dedicated Focus
#          sections in the dashboard. Replace them with your own niche terms.
#  Step 5: Edit TREND_LEXICON — groups of keywords for trend detection.
#
#  The examples below use "gene regulation / epigenetics" and
#  "stem cells / regenerative medicine" as sample focus areas. Replace them
#  with whatever fits your lab.
# ============================================================================


# ========================
# Journal whitelist
# ========================
# Add or remove journals here. Each entry must match the journal name as it
# appears in Crossref. Use JOURNAL_ISSN below to map ambiguous names to ISSNs.
JOURNALS = [
    "Cell",
    "Nature",
    "Science",
    "Cancer Cell",
    "Nature Biotechnology",
    "Nature Methods",
    "Immunity",
    "Nature Immunology",
    "Science Advances",
    "Science Immunology",
    "Science Translational Medicine",
    "Nature Cancer",
    "Nature Genetics",
    "Nature Medicine",
    "Nature Biomedical Engineering",
    "Cell Systems",
    "Cell Reports Methods",
    "PNAS",
    "Nature Chemical Biology",
    "Nature Communications",
    "eLife",
]
INCLUDE_BIORXIV_DEFAULT = True
INCLUDE_MEDRXIV_DEFAULT = False

# ISSN look-up speeds up Crossref queries and avoids false matches.
# Find ISSNs at https://portal.issn.org
JOURNAL_ISSN = {
    "Cell": ['0092-8674', '1097-4172'],
    "Nature": ['0028-0836', '1476-4687'],
    "Science": ['0036-8075', '1095-9203'],
    "Cancer Cell": ['1535-6108', '1878-3686'],
    "Nature Biotechnology": ['1087-0156', '1546-1696'],
    "Nature Methods": ['1548-7091', '1548-7105'],
    "Immunity": ['1074-7613', '1097-4180'],
    "Nature Immunology": ['1529-2908', '1529-2916'],
    "Science Advances": ['2375-2548'],
    "Science Immunology": ['2470-9468'],
    "Science Translational Medicine": ['1946-6234'],
    "Nature Cancer": ['2662-1347'],
    "Nature Genetics": ['1061-4036', '1546-1718'],
    "Nature Medicine": ['1078-8956', '1546-170X'],
    "Nature Biomedical Engineering": ['2157-846X'],
    "Cell Systems": ['2405-4712'],
    "Cell Reports Methods": ['2667-2375'],
    "PNAS": ['0027-8424', '1091-6490'],
    "Nature Chemical Biology": ['1552-4450', '1552-4469'],
    "Nature Communications": ['2041-1723'],
    "eLife": ['2050-084X'],
}

# Must-read list size
MUST_READ_N = 20

# Cap how many papers from the same journal can appear in each Must-read list
MAX_PER_JOURNAL_MUST_READ = 3


# ========================
# Tech vs Bio tag buckets
# ========================
# These must match keys in CORE_KEYWORDS below.
# Papers tagged with a TECH key go into the "Must-read Tech" list;
# papers tagged with a BIO key go into "Must-read Bio".
# A paper can appear in both if it hits keywords from both sides.
TECH_KEYS = ["genomics", "sequencing", "imaging", "proteomics", "computational"]
BIO_KEYS  = ["cell_biology", "development", "neuroscience", "cancer", "therapeutics"]


# ========================
# Core keyword lexicon
# ========================
# Each key becomes a tag. The list of strings are search terms (case-insensitive
# substring match in title + abstract). Longer phrases are matched first to
# avoid double-counting (e.g. "spatial transcriptomics" won't also count
# "spatial"). Short acronyms (<=3 chars) use word-boundary matching.
#
# >>> CUSTOMIZE THESE to match your research interests <<<
CORE_KEYWORDS = {
    # --- Technology categories ---
    "genomics": [
        "genomics",
        "genome-wide",
        "genome wide",
        "whole genome",
        "exome",
        "gwas",
        "genome sequencing",
        "chromatin",
        "epigenome",
        "methylome",
        "chip-seq",
        "cut&run",
        "cut&tag",
    ],
    "sequencing": [
        "sequencing",
        "single-cell",
        "single cell",
        "scrna",
        "rna-seq",
        "atac-seq",
        "multiome",
        "cite-seq",
        "perturb-seq",
        "crispr screen",
        "guide rna",
        "long-read",
        "nanopore",
    ],
    "imaging": [
        "imaging",
        "microscopy",
        "fluorescence",
        "confocal",
        "light-sheet",
        "super-resolution",
        "live imaging",
        "spatial transcriptomics",
        "spatial proteomics",
        "merfish",
        "seqfish",
        "visium",
        "codex",
        "expansion microscopy",
    ],
    "proteomics": [
        "proteomics",
        "mass spectrometry",
        "mass-spec",
        "lc-ms",
        "lc-ms/ms",
        "phosphoproteomics",
        "protein profiling",
        "olink",
        "somalogic",
        "cytof",
    ],
    "computational": [
        "deep learning",
        "machine learning",
        "artificial intelligence",
        "neural network",
        "foundation model",
        "large language model",
        "transformer",
        "graph neural network",
        "cell segmentation",
        "image analysis",
        "computational",
        "bioinformatics",
        "algorithm",
        "dimensionality reduction",
        "clustering",
        "trajectory inference",
        "batch correction",
        "data integration",
    ],

    # --- Biology / application categories ---
    "cell_biology": [
        "cell cycle",
        "cell division",
        "mitosis",
        "apoptosis",
        "autophagy",
        "cell migration",
        "cell adhesion",
        "cytoskeleton",
        "organelle",
        "membrane trafficking",
        "endocytosis",
        "exocytosis",
        "signal transduction",
        "cell polarity",
    ],
    "development": [
        "development",
        "embryo",
        "embryonic",
        "morphogenesis",
        "organogenesis",
        "differentiation",
        "stem cell",
        "progenitor",
        "lineage",
        "fate decision",
        "gastrulation",
        "patterning",
        "regeneration",
    ],
    "neuroscience": [
        "neuron",
        "neural",
        "brain",
        "cortex",
        "hippocampus",
        "synapse",
        "synaptic",
        "neurotransmitter",
        "glia",
        "astrocyte",
        "microglia",
        "axon",
        "dendrite",
        "neural circuit",
        "electrophysiology",
    ],
    "cancer": [
        "cancer",
        "tumor",
        "tumour",
        "oncology",
        "neoplasm",
        "malignant",
        "metastasis",
        "oncogene",
        "tumor suppressor",
        "tumor microenvironment",
    ],
    "therapeutics": [
        "drug",
        "therapy",
        "therapeutic",
        "treatment",
        "inhibitor",
        "small molecule",
        "antibody",
        "immunotherapy",
        "clinical trial",
        "pharmacology",
        "drug resistance",
        "combination therapy",
    ],
}


# ========================
# Focus 1: Gene regulation & epigenetics  (example — replace with your niche)
# ========================
# This list powers a dedicated Focus section in the dashboard.
# Add terms specific to your first focus area.
FOCUS_AREA_1_KEYS = [
    "gene regulation",
    "transcription factor",
    "enhancer",
    "promoter",
    "chromatin remodeling",
    "histone modification",
    "histone acetylation",
    "histone methylation",
    "dna methylation",
    "epigenetic",
    "epigenetics",
    "epigenome",
    "non-coding rna",
    "lncrna",
    "mirna",
    "chromatin accessibility",
    "3d genome",
    "topologically associating domain",
    "tad",
    "super-enhancer",
    "gene silencing",
    "polycomb",
    "trithorax",
]


# ========================
# Focus 2: Stem cells & regenerative medicine  (example — replace with your niche)
# ========================
FOCUS_AREA_2_KEYS = [
    "stem cell",
    "stem cells",
    "pluripotent",
    "ipsc",
    "induced pluripotent",
    "embryonic stem cell",
    "adult stem cell",
    "hematopoietic stem cell",
    "mesenchymal stem cell",
    "organoid",
    "organoids",
    "regeneration",
    "regenerative medicine",
    "tissue engineering",
    "cell therapy",
    "cell transplantation",
    "reprogramming",
    "self-renewal",
    "niche",
    "stem cell niche",
    "differentiation",
    "lineage tracing",
]


# ========================
# Focus 3: AI/ML in biological data analysis  (broadly useful — keep or customize)
# ========================
FOCUS_AI_KEYS = [
    "deep learning",
    "machine learning",
    "artificial intelligence",
    "neural network",
    "convolutional neural network",
    "graph neural network",
    "transformer",
    "foundation model",
    "large language model",
    "generative model",
    "variational autoencoder",
    "diffusion model",
    "self-supervised",
    "self supervised",
    "contrastive learning",
    "transfer learning",
    "representation learning",
    "cell segmentation",
    "image segmentation",
    "image analysis",
    "computational pathology",
    "digital pathology",
    "spatial deconvolution",
    "cell type annotation",
    "cell type classification",
    "automated annotation",
    "multimodal integration",
    "imputation",
    "trajectory inference",
    "gene regulatory network",
    "cell-cell communication",
    "cell cell communication",
]


# ========================
# Big-deal hints (broad advances)
# ========================
BIG_DEAL_HINTS = [
    "first-in-class",
    "breakthrough",
    "paradigm",
    "unexpected",
    "previously unknown",
    "landmark",
    "fundamental",
]


# ========================
# Trend lexicon
# ========================
# Each key is a trend name shown in the UI; its value is a list of keywords.
# Papers matching many keywords in a group signal a "hot trend".
#
# >>> CUSTOMIZE THESE to reflect the trends you care about <<<
TREND_LEXICON = {
    "Gene regulation & chromatin": [
        "gene regulation",
        "transcription factor",
        "enhancer",
        "chromatin",
        "epigenetic",
        "histone",
    ],
    "Single-cell & spatial omics": [
        "single-cell",
        "single cell",
        "spatial transcriptomics",
        "spatial proteomics",
        "multiome",
        "cell atlas",
    ],
    "Stem cells & organoids": [
        "stem cell",
        "organoid",
        "regeneration",
        "reprogramming",
        "pluripotent",
    ],
    "Cancer biology & therapy": [
        "cancer",
        "tumor",
        "metastasis",
        "immunotherapy",
        "tumor microenvironment",
        "oncogene",
    ],
    "Neuroscience & circuits": [
        "neural circuit",
        "synapse",
        "brain",
        "cortex",
        "hippocampus",
        "neuron",
    ],
    "AI/ML in bio data analysis": [
        "deep learning",
        "machine learning",
        "neural network",
        "foundation model",
        "transformer",
        "cell segmentation",
        "computational pathology",
        "spatial deconvolution",
        "automated annotation",
    ],
}
