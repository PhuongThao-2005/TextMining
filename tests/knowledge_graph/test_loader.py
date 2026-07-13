from __future__ import annotations


from pathlib import Path
import pytest

from knowledge_graph import GraphLoader, GraphLoaderPaths, GraphSourceBundle


def test_graph_loader_paths_validation(tmp_path: Path):
    """Test that GraphLoaderPaths validates the presence of required files."""
    paths = GraphLoaderPaths(data_dir=tmp_path)
    
    # Missing all files initially
    with pytest.raises(FileNotFoundError) as exc_info:
        paths.validate()
    assert "Missing graph loader inputs" in str(exc_info.value)
    
    # Create required files
    for name in ["documents.jsonl", "provisions.jsonl", "chunks.jsonl", "edges.jsonl", "external_stubs.jsonl"]:
        (tmp_path / name).touch()
        
    # Validation should now pass without raising
    paths.validate()


def test_graph_loader_loads_all(mock_dataset_dir: Path):
    """Test that GraphLoader loads and returns the expected generators and types."""
    paths = GraphLoaderPaths(data_dir=mock_dataset_dir)
    loader = GraphLoader(paths)
    
    bundle = loader.load_all()
    assert isinstance(bundle, GraphSourceBundle)
    
    # Test generators
    docs = list(bundle.documents)
    provisions = list(bundle.provisions)
    chunks = list(bundle.chunks)
    edges = list(bundle.edges)
    stubs = list(bundle.external_stubs)
    
    assert len(docs) == 2
    assert len(provisions) == 3
    assert len(chunks) == 3
    assert len(edges) == 3
    assert len(stubs) == 2
    
    # Check that they return raw dictionaries
    assert isinstance(docs[0], dict)
    assert docs[0]["id_str"] == "1"


def test_graph_loader_missing_individual_file(mock_dataset_dir: Path):
    """Test that individual loader methods raise FileNotFoundError when files are missing."""
    # Delete documents.jsonl
    (mock_dataset_dir / "documents.jsonl").unlink()
    
    paths = GraphLoaderPaths(data_dir=mock_dataset_dir)
    loader = GraphLoader(paths)
    
    with pytest.raises(FileNotFoundError):
        loader.load_documents()
        
    # The others should still load if they exist
    assert len(list(loader.load_provisions())) == 3


def test_graph_loader_handles_malformed_json(tmp_path: Path):
    """Test that the JSONL reader handles/raises on malformed JSON content."""
    # Create a malformed JSONL file
    docs_file = tmp_path / "documents.jsonl"
    with open(docs_file, "w", encoding="utf-8") as f:
        f.write('{"id_str": "1", "title": "Doc 1"}\n')
        f.write('{"id_str": "2", malformed_json_here}\n')
        
    for name in ["provisions.jsonl", "chunks.jsonl", "edges.jsonl", "external_stubs.jsonl"]:
        (tmp_path / name).touch()
        
    loader = GraphLoader(GraphLoaderPaths(data_dir=tmp_path))
    
    # Attempting to load the malformed file stream should fail during iteration
    docs_generator = loader.load_documents()
    
    # First record should yield successfully
    doc1 = next(docs_generator)
    assert doc1["id_str"] == "1"
    
    # Second record should raise ValueError due to the reader's exception wrapper
    with pytest.raises(ValueError):
        next(docs_generator)

