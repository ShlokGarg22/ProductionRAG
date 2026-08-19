try:
    from fastembed import SparseTextEmbedding
    print("fastembed SparseTextEmbedding is available")
except ImportError as e:
    print("Import error:", e)
